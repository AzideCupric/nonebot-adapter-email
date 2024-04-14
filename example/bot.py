from pathlib import Path
import nonebot

nonebot.adapters.__path__.append(str((Path(__file__).parent.parent.parent / "nonebot" / "adapters").resolve()))  # type: ignore

from nonebot.adapters.email import Adapter as EmailAdapter

nonebot.init(
    _env_file=Path(__file__).parent/ "nb.env"
)

driver = nonebot.get_driver()
driver.register_adapter(EmailAdapter)

nonebot.load_plugin(Path(__file__).parent / "auto_reply.py")

if __name__ == "__main__":
    nonebot.run()
