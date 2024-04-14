import asyncio
from typing import Any
from aioimaplib import AioImapException, Command
from nonebot.typing import overrides
from nonebot.drivers import Driver

from nonebot.adapters import Adapter as BaseAdapter
from nonebot.utils import escape_tag
from nonemail import EmailClient, ConnectReq, ImapResponse, SendReq

from .utils import email_parser

from .log import log
from .bot import Bot
from .event import Event
from .message import Message
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
                    log("TRACE", f"{req.username} pre connecting...")

                    while True:
                        if not bot:
                            self.email_clients[req.username] = client
                            bot = Bot(self, req.username)
                            self.bot_connect(bot)
                            log("SUCCESS", f"<blue>Bot {bot.self_id} connected</blue>")
                        try:
                            await client.idle_start(timeout=req.timeout)
                            log("TRACE", "imap client idle start")
                            resp = await client.receive(
                                timeout=req.timeout + 5
                            )  # FIXME: 时间不大于idle_start的timeout就会不进行循环
                            log("TRACE", f"imap client received: {resp}")

                            event = await self.convert_to_event(bot, resp)

                            if event is None:
                                log("TRACE", "event is None")
                                log("TRACE", "will done idle")
                                client.idle_done()
                            else:
                                log("DEBUG", f"event: {escape_tag(event.json(indent=4, ensure_ascii=False))}")
                                asyncio.create_task(bot.handle_event(event))

                            log("TRACE", "imap client wait for next loop...")
                        except asyncio.TimeoutError:
                            log("WARNING", "imap client timeout")
                            client.idle_done()
                            continue
                        except AioImapException as e:
                            log("ERROR", "IMAP4 Receive Error", exception=e)
                            await asyncio.sleep(5)
                            self._pop(bot)
                            bot = None
                            log("DEBUG", f"bot now is {bot}")
                            break

            except Exception as e:
                log("ERROR", "IMAP4 Error", exception=e)
                await asyncio.sleep(10)
            finally:
                self._pop(bot)
                bot = None
                log("DEBUG", f"Now bot is {bot}")

    def _pop(self, bot: Bot | None):
        if not bot:
            return
        self.email_clients.pop(bot.self_id)
        self.bot_disconnect(bot)
        log("WARNING", f"<red>Bot {bot.self_id} disconnect!</red>")

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

    async def send_to(self, bot_id: str, message: Message, **kwargs: Any) -> None:
        email_client = self.email_clients.get(bot_id, None)
        if email_client is None:
            log("ERROR", f"<red>Bot {bot_id}'s email client not found</red>")
            return
        return await self._send(email_client, message, **kwargs)

    async def _send(self, email_client: EmailClient, message: Message, **kwargs: Any):
        log(
            "TRACE",
            f"send:\n{message.email}\n\nserver: {self.adapter_config.smtp_host}:{self.adapter_config.smtp_port}",
        )
        # FIXME: 没有显式指定用户名
        send_req = SendReq(
            server=self.adapter_config.smtp_host,
            port=self.adapter_config.smtp_port,
            message=message.email,
            password=self.adapter_config.password,
            use_tls=self.adapter_config.smtp_use_tls,
            **kwargs,
        )
        return await email_client.send(send_req)

    async def convert_to_event(self, bot: Bot, resp: Any):
        if not resp:
            return None

        log("TRACE", f"convert_to_event: {resp}")
        assert isinstance(resp, list)
        match resp[0].lower():
            case b"stop_wait_server_push":
                log("DEBUG", "resp is stop_wait_server_push, ignore")
                return None
            case exists if exists.endswith(b"exists"):
                msg_id, _ = exists.decode("utf-8").split()
                log("DEBUG", f"new mail: {msg_id}")
                try:
                    client_impl = self.mailbox_operate(bot)
                    # FIXME:对邮箱进行操作前需要idle_done, 这潜在的会导致外面那个循环重复idle_done
                    # 不结束idle会一直卡在fetch
                    client_impl.idle_done()

                    raw_mail_header = await client_impl.fetch(msg_id, "BODY[HEADER]")
                    log("DEBUG", f"Fetch result: {raw_mail_header.result}")
                    log("TRACE", f"{escape_tag(str(raw_mail_header.lines))}")
                    parsed_mail = email_parser(raw_mail_header)
                    event = Event(
                        self_id=bot.self_id,
                        date=parsed_mail.date,
                        subject=parsed_mail.subject,
                        mail_id=msg_id,
                        headers=parsed_mail.headers,
                        mime_types=[part.mimetype for part in parsed_mail.attachments],
                    )
                    log("DEBUG", "<green><b>new mail</b></green>\n" + escape_tag(str(event)))
                except Exception as e:
                    log("ERROR", "Parse Mail Error", exception=e)
                    return None
                else:
                    return event
            case unknown:
                log("WARNING", f"unknown resp: {unknown}")
                return None
