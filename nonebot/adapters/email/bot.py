from typing import Any
from nonebot.typing import overrides

from nonebot.adapters import Bot as BaseBot

from .event import Event
from .message import Message, MessageSegment


class Bot(BaseBot):
    @overrides(BaseBot)
    async def send(
        self,
        event: Event,
        message: str | Message | MessageSegment,
        **kwargs,
    ) -> Any:
        ...

    async def handle_event(self, event: Event) -> None:
        """处理事件"""
        pass
