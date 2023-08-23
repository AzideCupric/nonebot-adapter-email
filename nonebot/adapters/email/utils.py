from aioimaplib import Response
from email import parser
from fast_mail_parser import parse_email

def bytes_json_serializer(obj):
    if isinstance(obj, bytes):
        return obj.decode("utf-8")

def email_parser(resp: Response):
    str_parser = parser.BytesParser()
    raw_email = str_parser.parsebytes(resp.lines[1])
    return parse_email(raw_email.as_string())
