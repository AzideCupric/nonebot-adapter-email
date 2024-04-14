from pydantic import Field, BaseModel, validator, Extra
from nonebot.compat import PYDANTIC_V2, ConfigDict
from email_validator import validate_email, EmailNotValidError
from aioimaplib import IMAP4, TWENTY_NINE_MINUTES

ADAPTER_NAME = "email"


class Config(BaseModel):
    # 收发共用部分
    user: str = Field(..., description="email user")
    password: str = Field(..., description="email password or credential")
    # SMTP
    smtp_host: str = Field(..., description="SMTP server host")
    smtp_port: int | None = Field(None, description="SMTP server port")
    smtp_use_tls: bool = Field(True, description="use TLS for SMTP connection")
    # IMAP
    imap_host: str = Field(..., description="IMAP server host")
    imap_port: int = Field(993, description="IMAP server port")
    imap_login_timeout: int = Field(IMAP4.TIMEOUT_SECONDS, description="IMAP server connection timeout")
    imap_idle_timeout: int = Field(TWENTY_NINE_MINUTES, description="IMAP server idle timeout")
    imap_use_tls: bool = Field(True, description="use TLS for IMAP connection")


    @validator("user")
    def user_validator(cls, v):
        try:
            validate_email(v)
        except EmailNotValidError as e:
            raise ValueError(f"invalid email address: {v}") from e
        return v

    if PYDANTIC_V2:
        model_config = ConfigDict(extra="ignore")
    else:
        class Config:
            extra = Extra.ignore
            allow_population_by_field_name = True
