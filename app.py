import litestar
from command_stream import insert_command
from command_stream import wait_for_result
import database
from functools import wraps

from errors import _ok
from errors import _exception
from errors import _fail



@litestar.get("/")
async def index() -> dict:
    return _ok("Hello, world!")


@litestar.post("/commands")
async def issue_command(data: dict) -> dict:
    key = insert_command(data)
    try:
        return _ok(wait_for_result(key))
    except Exception as err:
        return _exception(err)


@litestar.get("/checkpoint")
async def get_checkpoint() -> dict:
    return database.checkpoint_data()


app = litestar.Litestar([index, issue_command, get_checkpoint])
