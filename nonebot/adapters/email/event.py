from typing import NamedTuple
import re
from datetime import datetime
from nonebot.utils import escape_tag
from nonebot.adapters import Event as BaseEvent

from .message import Message

class Emailer(NamedTuple):
    name: str
    addr: str

    def __str__(self) -> str:
        return f"{self.name} <{self.addr}>"

class Event(BaseEvent):
    """考虑到MIME部分可能会过大，因此仅获取邮件头部"""
    self_id: str
    date: str
    subject: str
    mail_id: str
    headers: dict[str, str]
    mime_types: list[str]


    @property
    def datetime(self) -> datetime:
        return datetime.strptime(self.date, "%a, %d %b %Y %H:%M:%S %z")

    @property
    def sender(self) -> Emailer:
        """sender 一般在 From 字段中， 格式为: 'xxx' <xxx@xxx.xxx>"""
        sender_pattern = re.compile(r"(.+) <(.+)>")
        sender = sender_pattern.match(self.headers.get("From", ""))
        if sender:
            return Emailer(sender.group(1), sender.group(2))

        return Emailer("", "")

    @property
    def recipients(self) -> list[Emailer]:
        """recipients 一般在 To 字段中， 格式为: 'xxx' <xxx@xxx.xxx>, 'xxx' <xxx@xxx.xxx>, ..."""
        recipients_pattern = re.compile(r"(.+) <(.+)>")
        recipients = recipients_pattern.findall(self.headers.get("To", ""))
        if recipients:
            return [Emailer(recipient[0], recipient[1]) for recipient in recipients]
        return []

    @property
    def cc(self) -> list[Emailer]:
        """cc 一般在 Cc 字段中， 格式为: 'xxx' <xxx@xxx.xxx>, ..."""
        cc_pattern = re.compile(r"(.+) <(.+)>")
        cc = cc_pattern.findall(self.headers.get("Cc", ""))
        if cc:
            return [Emailer(c[0], c[1]) for c in cc]
        return []

    @property
    def message_id(self) -> str:
        return self.headers.get("Message-ID", "")

    def get_type(self) -> str:
        return "new_mail"

    def get_event_name(self) -> str:
        return "New Mail"

    def get_event_description(self) -> str:
        return escape_tag(f"\n{str(self)}")

    def get_message(self) -> Message:
        raise ValueError("This event does not have a message.")

    def get_plaintext(self) -> str:
        raise ValueError("This event does not have a message.")

    def get_user_id(self) -> str:
        if not self.sender:
            return ""
        return self.sender.addr

    def get_session_id(self) -> str:
        if not self.sender:
            return ""
        return self.sender.addr

    def is_tome(self) -> bool:
        return self.self_id in self.recipients

    def is_ccme(self) -> bool:
        """当邮件抄送给机器人时返回 True"""
        if self.cc is None:
            return False
        return any(cc.addr == self.self_id for cc in self.cc)

    def __str__(self) -> str:
        return (
            f"Subject: {self.subject}\n"
            + f"From: {self.sender.name} <{self.sender.addr}>\n"
            + "To:" + ", ".join([str(r) for r in self.recipients]) + "\n"
            + (
                ("Cc:" + ", ".join([str(c) for c in self.cc]) + "\n")
                if self.cc
                else ""
            )
            + f"Date: {self.date}\n"
        )

    # Bcc 无法从接收到的邮件中判断
