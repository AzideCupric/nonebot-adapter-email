import asyncio
from typing import Any
from asyncio import get_running_loop
from aioimaplib import IMAP4_SSL, AioImapException
from email_validator import validate_email, EmailNotValidError
from nonebot.typing import overrides
from nonebot.exception import WebSocketClosed
from nonebot.utils import DataclassEncoder, escape_tag
from nonebot.drivers import (
    URL,
    Driver,
    Request,
    Response,
    WebSocket,
    ForwardDriver,
    ReverseDriver,
    HTTPServerSetup,
    WebSocketServerSetup,
)

from nonebot.adapters import Adapter as BaseAdapter

from .log import log
from .bot import Bot
from .event import Event
from .config import Config, ADAPTER_NAME
from .message import Message, MessageSegment


class Adapter(BaseAdapter):
    imap_client: IMAP4_SSL | None = None

    @overrides(BaseAdapter)
    def __init__(self, driver: Driver, **kwargs: Any):
        super().__init__(driver, **kwargs)
        self.adapter_config = Config(**self.config.dict())
        # setup adapter
        self.setup()

    @classmethod
    @overrides(BaseAdapter)
    def get_name(cls) -> str:
        return ADAPTER_NAME

    def setup(self) -> None:
        # if not isinstance(self.driver, ForwardDriver):
        #     raise RuntimeError(
        #         f"Current driver {self.config.driver} is not supported forward connection"
        #         f"{self.get_name()} Adapter need a ForwardDriver to work."
        #     )
        # on NoneBot startup
        self.driver.on_startup(self.startup)
        # on NoneBot shutdown
        self.driver.on_shutdown(self.shutdown)

    async def startup(self) -> None:
        bot_id = self.adapter_config.user
        asyncio.create_task(self._start_imap(bot_id))

    async def _start_imap(self, email: str) -> None:
        """使用IMAP4协议连接邮箱服务器"""
        while True:
            bot = Bot(self, email)
            try:
                self.imap_client = IMAP4_SSL(
                    host=self.adapter_config.imap_host,
                    port=self.adapter_config.imap_port,
                    loop=get_running_loop(),
                    timeout=self.adapter_config.imap_login_timeout,
                )
                await self.imap_client.wait_hello_from_server()
                await self.imap_client.login(
                    email,
                    self.adapter_config.password,
                )
                await self.imap_client.select()
                self.bot_connect(bot)

                while True:
                    self.idle = await self.imap_client.idle_start(timeout=self.adapter_config.imap_idle_timeout)
                    await self.imap_client.wait_server_push()
                    self.imap_client.idle_done()
                    await asyncio.wait_for(self.idle, timeout=self.adapter_config.imap_login_timeout)

            except AioImapException as e:
                log(
                    "ERROR",
                    f"IMAP4 connection error: {e}, retrying in 5 seconds...",
                )
                self.bot_disconnect(bot)
                self.idle.cancel()
                await asyncio.sleep(5)

    async def shutdown(self) -> None:
        """关闭IMAP4连接"""
        if self.imap_client:
            await self.imap_client.close()
            await self.imap_client.logout()

    async def _handle_connect(self):
        bot_id = self.adapter_config.user
        bot = Bot(self, bot_id)
        self.bot_connect(bot)

    @overrides(BaseAdapter)
    async def _call_api(self, bot: Bot, api: str, **data: Any) -> Any:
        log("DEBUG", f"{bot} calling API {api} with data: {data}")
        return "NotImplemented, please use bot.imap_client"
