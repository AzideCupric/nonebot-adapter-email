from pathlib import Path

import pytest
from nonebug import NONEBOT_INIT_KWARGS

import nonebot
import nonebot.adapters

nonebot.adapters.__path__.append(str((Path(__file__).parent.parent / "nonebot" / "adapters").resolve()))  # type: ignore


def pytest_configure(config: pytest.Config) -> None:
    config.stash[NONEBOT_INIT_KWARGS] = {
        "driver": "~none",
        "user": "test@test.com",
        "password": "test",
        "smtp_host": "test.com",
        "imap_host": "test.com",
        "log_level": "TRACE",
    }


@pytest.fixture(scope="session", autouse=True)
def _init_adapter(nonebug_init: None):
    from nonebot.adapters.email import Adapter  # type: ignore

    driver = nonebot.get_driver()
    driver.register_adapter(Adapter)
