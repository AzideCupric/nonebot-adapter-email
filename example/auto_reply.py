from datetime import datetime
from pathlib import Path
from typing import TYPE_CHECKING
from nonebot import on_message
from nonebot.log import logger
from nonebot.utils import escape_tag
import nonebot.adapters

nonebot.adapters.__path__.append(str((Path(__file__).parent / "nonebot" / "adapters").resolve()))  # type: ignore

from nonebot.adapters.email import Event # noqa: E402
from nonebot.adapters.email import Message # noqa: E402

if TYPE_CHECKING:
    from ..nonebot.adapters.email import Message, Event

auto = on_message()

@auto.handle()
async def auto_reply(event: Event):
    logger.debug(f"get event: {escape_tag(str(event))}")

    reply_email = Message()
    reply_email.from_(event.recipients[0].addr)
    reply_email.subject("收到")
    reply_email.to(event.sender.addr)
    reply_email.set_content("已收到")
    reply_email.email["Date"] = datetime.now().strftime("%a, %d %b %Y %H:%M:%S %z")

    await auto.finish(reply_email, username="me@cupric.top")
