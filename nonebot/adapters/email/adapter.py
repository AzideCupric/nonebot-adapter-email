import asyncio
from typing import Any
from asyncio import get_running_loop
from aioimaplib import IMAP4_SSL, AioImapException
from email_validator import validate_email, EmailNotValidError
from nonebot.typing import overrides
from nonebot.drivers import Driver

from nonebot.adapters import Adapter as BaseAdapter

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
        # TODO: 多账号支持(还没想好怎么安排账号和密码在配置里的对应问题)
        self.tasks = [asyncio.create_task(self._start_imap(connect_req))]

    async def _start_imap(self, req: ConnectReq) -> None:
        bot: Bot | None = None
        self.email_client: dict[str, EmailClient] = {}
        while True:
            try:
                async with EmailClient(req) as client:
                    self.email_client[req.username] = client
                    bot = Bot(self, req.username)
                    self.bot_connect(bot)
                    log("INFO", f"Bot {bot.self_id} Connected, protocol: {self.email_client[bot.self_id].procotol}")
                    while True:
                        try:
                            resp: ImapResponse = await client.receive()
                            if resp is None:
                                continue

                                # TODO: 处理邮件

                        except AioImapException as e:
                            log("ERROR", "IMAP4 Receive Error", exception=e)

                        finally:
                            if bot:
                                self.email_client.pop(bot.self_id)
                                self.bot_disconnect(bot)
                                bot = None
            except AioImapException as e:
                log("ERROR", "IMAP4 Connect Error", exception=e)

                await asyncio.sleep(10)

    async def shutdown(self) -> None:
        """关闭IMAP4连接"""
        for task in self.tasks:
            if not task.done():
                task.cancel()
        await asyncio.gather(*self.tasks, return_exceptions=True)

    @overrides(BaseAdapter)
    async def _call_api(self, bot: Bot, api: str, tag: str, **data: Any) -> ImapResponse:
        """不建议直接使用此方法手搓Command,
        请使用`mailbox_operate`方法获取EmailClient实例后调用其封装好的方法
        """
        command = Command(name=api, tag=tag, **data)
        return await self.email_client[bot.self_id].operate(command)

    async def mailbox_operate(self, bot: Bot):
        """获取EmailClient实例, 用于调用其封装好的方法"""
        return self.email_client[bot.self_id].impl
