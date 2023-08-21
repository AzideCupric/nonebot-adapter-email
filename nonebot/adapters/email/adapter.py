import asyncio
from typing import Any
from asyncio import get_running_loop
from aioimaplib import IMAP4_SSL, AioImapException
from email_validator import validate_email, EmailNotValidError
from nonebot.typing import overrides
from nonebot.drivers import Driver

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
        # on NoneBot startup
        self.driver.on_startup(self.startup)
        # on NoneBot shutdown
        self.driver.on_shutdown(self.shutdown)

    async def startup(self) -> None:
        bot_id = self.adapter_config.user
        asyncio.create_task(self._start_imap(bot_id))

    async def _start_imap(self, email: str) -> None:
        pass

    async def shutdown(self) -> None:
        """关闭IMAP4连接"""
        pass

    async def _handle_connect(self):
        bot_id = self.adapter_config.user
        bot = Bot(self, bot_id)
        self.bot_connect(bot)

    @overrides(BaseAdapter)
    async def _call_api(self, bot: Bot, api: str, **data: Any) -> Any:
        pass
