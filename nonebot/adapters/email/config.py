from pydantic import Field, Extra, BaseSettings, validator
from email_validator import validate_email, EmailNotValidError
from aioimaplib import IMAP4, TWENTY_NINE_MINUTES

ADAPTER_NAME = "email"


class Config(BaseSettings):
    # 收发共用部分
    user: str = Field(..., description="email user")
    password: str = Field(..., description="email password or credential")
    # SMTP
    smtp_host: str = Field(..., description="SMTP server host")
    smtp_port: int = Field(587, description="SMTP server port")
    # IMAP
    imap_host: str = Field(..., description="IMAP server host")
    imap_port: int = Field(993, description="IMAP server port")
    imap_login_timeout: int = Field(IMAP4.TIMEOUT_SECONDS, description="IMAP server connection timeout")
    imap_idle_timeout: int = Field(TWENTY_NINE_MINUTES, description="IMAP server idle timeout")

    @validator("user")
    def user_validator(cls, v):
        try:
            validate_email(v)
        except EmailNotValidError as e:
            raise ValueError(f"invalid email address: {v}") from e
        return v

    class Config:
        extra = Extra.ignore
        allow_population_by_field_name = True
