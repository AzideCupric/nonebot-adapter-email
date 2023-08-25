
def test_event_str():
    from nonebot.utils import escape_tag
    from nonebot.adapters.email.log import log # type: ignore
    from nonebot.adapters.email.event import Event # type: ignore

    event = Event.parse_obj({
        "self_id": "email@none.bot",
        "date": "Fri, 25 Aug 2023 02:53:48 +0000",
        "subject": "测试邮件7",
        "mail_id": "3124",
        "mime_types": ["text/plain"],
        "headers": {
            "To": '"mailbot" <email@none.bot>',
            "From": "YAMB <mail@test.adp>",
            "Cc": "mailbot2 <bot@none.mail>",
            "Message-ID": "<1111>",
        }
    })

    log("INFO", f"event: \n{escape_tag(str(event))}")

