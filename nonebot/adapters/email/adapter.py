import asyncio
from typing import Any
from asyncio import Future
from aioimaplib import AioImapException, Command
from nonebot.typing import overrides
from nonebot.drivers import Driver

from nonebot.adapters import Adapter as BaseAdapter
from nonemail import EmailClient, ConnectReq, ImapResponse

from .utils import email_parser

from .log import log
from .bot import Bot
from .event import Event
from .config import Config, ADAPTER_NAME


class Adapter(BaseAdapter):
    @overrides(BaseAdapter)
    def __init__(self, driver: Driver, **kwargs: Any):
        super().__init__(driver, **kwargs)
        self.adapter_config = Config(**self.config.dict())
        # setup adapter
        log("DEBUG", f"Adapter config: {self.adapter_config}")
        self.setup()

    @classmethod
    @overrides(BaseAdapter)
    def get_name(cls) -> str:
        return ADAPTER_NAME

    def setup(self) -> None:
        # on NoneBot startup
        self.driver.on_startup(self.startup)
        # on NoneBot shutdown
        self.driver.on_shutdown(self.shutdown)

    async def startup(self) -> None:
        connect_req = ConnectReq(
            self.adapter_config.imap_host,
            self.adapter_config.imap_port,
            self.adapter_config.user,
            self.adapter_config.password,
        )
        log("INFO", f"Connecting to {connect_req.server}:{connect_req.port}...")
        # TODO: 多账号支持(还没想好怎么安排账号和密码在配置里的对应问题)
        self.tasks = [asyncio.create_task(self._start_imap(connect_req))]

    async def _start_imap(self, req: ConnectReq) -> None:
        bot: Bot | None = None
        self.email_clients: dict[str, EmailClient] = {}
        while True:
            log("TRACE", "loop imap")
            try:
                async with EmailClient(req) as client:
                    log("TRACE", f"{req.username} pre connecting, protocol is xxx")

                    while True:
                        idle: Future[Any] | None = None
                        if not bot:
                            self.email_clients[req.username] = client
                            bot = Bot(self, req.username)
                            self.bot_connect(bot)
                            log("INFO", f"<blue>Bot {bot.self_id} connected</blue>")
                        try:
                            idle = await client.idle_start(timeout=req.timeout)
                            log("TRACE", "imap client idle start")
                            resp = await client.receive(
                                timeout=req.timeout + 5
                            )  # FIXME: 时间不大于idle_start的timeout就会不进行循环
                            log("TRACE", f"imap client received: {resp}")

                            event = await self.convert_to_event(bot, resp)
                            log("TRACE", f"convert to event: {event}")

                            if event is None:
                                log("TRACE", "event is None")
                                log("TRACE", "will done idle")
                                client.idle_done()
                            else:
                                log("TRACE", f"event: {event.json(indent=4, ensure_ascii=False)}")
                                asyncio.create_task(bot.handle_event(event))

                            log("TRACE", "imap client wait for next loop...")
                            await asyncio.wait_for(idle, req.timeout + 5)  # 懒得试了， 同样+5
                            log("TRACE", "imap client wait for next loop... done")

                        except asyncio.TimeoutError:
                            log("WARNING", "imap client timeout")
                            if idle and not idle.done():
                                idle.cancel()
                                idle = None
                            client.idle_done()
                            continue
                        except AioImapException as e:
                            log("ERROR", "IMAP4 Receive Error", exception=e)
                            await asyncio.sleep(5)
                            self._pop_bot(bot)
                            break

            except Exception as e:
                log("ERROR", "IMAP4 Error", exception=e)
                await asyncio.sleep(10)
            finally:
                self._pop_bot(bot)

    def _pop_bot(self, bot: Bot | None):
        if not bot:
            return
        self.email_clients.pop(bot.self_id)
        self.bot_disconnect(bot)
        log("WARNING", f"<red>Bot {bot.self_id} disconnect!</red>")
        bot = None

    async def shutdown(self) -> None:
        """关闭IMAP4连接"""
        for task in self.tasks:
            if not task.done():
                task.cancel()
        await asyncio.gather(*self.tasks, return_exceptions=True)

    @overrides(BaseAdapter)
    async def _call_api(self, bot: Bot, api: str, *data: str) -> ImapResponse | None:
        """或者使用`mailbox_operate`方法获取EmailClient实例后调用其封装好的方法"""
        if impl_procotol := self.email_clients[bot.self_id].impl.protocol:
            return await impl_procotol.execute(Command(api, *data))

    def mailbox_operate(self, bot: Bot):
        """获取EmailClient实例, 用于调用其封装好的方法"""
        return self.email_clients[bot.self_id].impl

    async def convert_to_event(self, bot: Bot, resp: Any):
        if not resp:
            return None

        def bytes_to_str(b: bytes | str):
            if isinstance(b, str):
                return b
            return b.decode("utf-8")

        resp_strs = [bytes_to_str(r) for r in resp]
        log("DEBUG", f"resp_strs: {resp_strs}")

        if resp_strs[0].lower() == "stop_wait_server_push":
            log("DEBUG", "resp is stop_wait_server_push, ignore")
            return None
        elif resp_strs[0].lower().endswith("exists"):
            msg_id, _ = resp_strs[0].split(" ")
            log("DEBUG", f"new mail: {msg_id}")
            try:
                client_impl = self.mailbox_operate(bot)
                # FIXME:对邮箱进行操作前需要idle_done, 这潜在的会导致外面那个循环重复idle_done
                # 不结束idle会一直卡在fetch
                client_impl.idle_done()

                raw_mail_header = await client_impl.fetch(msg_id, "BODY[HEADER]")
                log("DEBUG", f"Fetch result: {raw_mail_header.result}")
                parsed_mail = email_parser(raw_mail_header)
                event = Event(
                    self_id=bot.self_id,
                    date=parsed_mail.date,
                    subject=parsed_mail.subject,
                    mail_id=msg_id,
                    headers=parsed_mail.headers,
                    mime_types=[part.mimetype for part in parsed_mail.attachments],
                )
                log("SUCCESS", "<green><b>new mail</b></green>\n" + str(event))
            except Exception as e:
                log("ERROR", "Parse Mail Error", exception=e)
                return None
            else:
                return event
        else:
            log("WARNING", f"unknown resp: {resp_strs}")
            return None
