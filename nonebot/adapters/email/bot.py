from nonebot.typing import overrides

from nonebot.adapters import Bot as BaseBot
from nonebot.message import handle_event
from .adapter import Adapter
from .event import Event
from .message import Message


class Bot(BaseBot):
    @overrides(BaseBot)
    async def send(
        self,
        event: Event,
        message: Message,
        **kwargs,
    ):
        """发送消息"""
        assert isinstance(self.adapter, Adapter)
        return await self.adapter.send_to(event.self_id, message, **kwargs)

    async def send_by(
        self,
        bot_id: str,
        message: Message,
        **kwargs,
    ):
        assert isinstance(self.adapter, Adapter)
        return await self.adapter.send_to(bot_id, message, **kwargs)

    async def handle_event(self, event: Event) -> None:
        """处理事件"""
        await handle_event(self, event)
