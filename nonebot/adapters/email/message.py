# from collections.abc import Mapping, Iterable
# from typing import Type
# from nonebot.adapters import Message as BaseMessage, MessageSegment as BaseMessageSegment


# class MessageSegment(BaseMessageSegment):
#     def __str__(self) -> str:
#         raise NotImplementedError

#     def __add__(self, other) -> "Message":
#         return Message(self) + other

#     def __radd__(self, other) -> "Message":
#         return Message(other) + self

#     def is_text(self) -> bool:
#         raise NotImplementedError


# class Message(BaseMessage):
#     @staticmethod
#     def _construct(msg: str | Mapping | Iterable[Mapping]) -> Iterable[MessageSegment]:
#         raise NotImplementedError

#     @classmethod
#     def get_segment_class(cls) -> type:
#         raise NotImplementedError

# TODO: 毙了，先用 python 自带的email库

from email.contentmanager import ContentManager
from email.message import EmailMessage
from typing import Any
from email_validator import validate_email, EmailNotValidError
from .log import log


class Message:
    def __init__(self):
        self._email = EmailMessage()

    def __str__(self) -> str:
        return self._email.as_string()

    @property
    def email(self) -> EmailMessage:
        return self._email

    def subject(self, subject: str) -> None:
        self._email["Subject"] = subject

    def to(self, to: str | list[str]) -> None:
        if isinstance(to, str):
            to = [to]
        valid_tos = []
        for t in to:
            try:
                validate_email(t)
            except EmailNotValidError:
                log("ERROR", f"Invalid email address: {t}")
                continue
            else:
                valid_tos.append(t)
        self._email["To"] = ", ".join(valid_tos)

    def cc(self, cc: str | list[str]) -> None:
        if isinstance(cc, str):
            cc = [cc]
        valid_ccs = []
        for c in cc:
            try:
                validate_email(c)
            except EmailNotValidError:
                log("ERROR", f"Invalid email address: {c}")
                continue
            else:
                valid_ccs.append(c)
        self._email["Cc"] = ", ".join(valid_ccs)

    def bcc(self, bcc: str | list[str]) -> None:
        if isinstance(bcc, str):
            bcc = [bcc]
        valid_bccs = []
        for b in bcc:
            try:
                validate_email(b)
            except EmailNotValidError:
                log("ERROR", f"Invalid email address: {b}")
                continue
            else:
                valid_bccs.append(b)
        self._email["Bcc"] = ", ".join(valid_bccs)

    def from_(self, from_: str) -> None:
        self._email["From"] = from_

    def set_content(self, *args: Any, content_manager: ContentManager | None = None, **kw: Any):
        self._email.set_content(
            *args,
            content_manager=content_manager,
            **kw
        )
