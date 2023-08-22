import asyncio
from typing import Any
from asyncio import get_running_loop
from aioimaplib import IMAP4_SSL, AioImapException
from email_validator import validate_email, EmailNotValidError
from nonebot.typing import overrides
from nonebot.drivers import Driver

from nonebot.adapters import Adapter as BaseAdapter
from nonebot.utils import escape_tag
from nonemail import EmailClient, ConnectReq, ImapResponse, Command

from .log import log
from .bot import Bot
from .event import Event
from .config import Config, ADAPTER_NAME
from .message import Message, MessageSegment


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
                    res = await client.impl.select(req.mailbox)  # 选择需要监听的邮箱
                    log("TRACE", f"{res}")

                    amail = await client.impl.fetch("3085", "BODY[HEADER]")
                    log("TRACE", f"{escape_tag(repr(amail))}")
                    try:
                        while True:
                            idle = await client.idle_start(timeout=req.timeout)
                            if not bot:
                                self.email_clients[req.username] = client
                                bot = Bot(self, req.username)
                                self.bot_connect(bot)
                                log("INFO", f"Bot {bot.self_id} connected")

                            resp = await client.receive(
                                timeout=req.timeout + 5
                            )  # FIXME: 时间不大于idle_start的timeout就会不进行循环
                            log("TRACE", f"imap client received: {resp}")

                            event = self.convert_to_event(resp)
                            log("TRACE", f"convert to event: {event}")

                            if event is None:
                                log("TRACE", "event is None")
                                # 不直接continue的原因是需要发送 idle_done消息， 否则会一直idle
                            else:
                                log("TRACE", f"event is not None: {event}")
                                asyncio.create_task(bot.handle_event(event))

                            log("TRACE", "will done idle")
                            client.idle_done()

                            log("TRACE", "imap client wait for next loop...")
                            await asyncio.wait_for(idle, req.timeout + 5)  # 懒得试了， 同样+5
                            log("TRACE", "imap client wait for next loop... done")
                    except asyncio.TimeoutError:
                        log("WARNING", "imap client timeout")

                    except AioImapException as e:
                        log("ERROR", "IMAP4 Receive Error", exception=e)
                        await asyncio.sleep(5)
                    finally:
                        if bot:
                            old = self.email_clients.pop(bot.self_id)
                            await old.close()
                            self.bot_disconnect(bot)
                            bot = None
            except Exception as e:
                log("ERROR", "IMAP4 Error", exception=e)
                await asyncio.sleep(10)

    async def shutdown(self) -> None:
        """关闭IMAP4连接"""
        for task in self.tasks:
            if not task.done():
                task.cancel()
        await asyncio.gather(*self.tasks, return_exceptions=True)

    @overrides(BaseAdapter)
    async def _call_api(self, bot: Bot, api: str, *data: str) -> ImapResponse:
        """或者使用`mailbox_operate`方法获取EmailClient实例后调用其封装好的方法"""
        return await self.email_clients[bot.self_id].impl.uid(api, *data)

    async def mailbox_operate(self, bot: Bot):
        """获取EmailClient实例, 用于调用其封装好的方法"""
        return self.email_clients[bot.self_id].impl

    def convert_to_event(self, resp: Any):
        if not resp:
            return None

        if isinstance(resp, list):
            for r in resp:
                if r == b"stop_wait_server_push":
                    return None
                if r.endswith(b"EXISTS"):
                    return Event.new_message(
                        message_id=r.split(b" ")[0].decode("utf-8")
                    )
