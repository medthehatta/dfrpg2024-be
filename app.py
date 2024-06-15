import litestar
from command_stream import insert_command
import database
from functools import wraps


def _ok(result=None):
    if result is not None:
        return {"ok": True, "result": result}
    else:
        return {"ok": True}


def _exception(exception):
    return {
        "ok": False,
        "error": str(type(exception)),
        "description": str(exception.args),
    }


def _fail(message):
    return {
        "ok": False,
        "error": "Operation failed",
        "description": message,
    }


@litestar.get("/")
async def index() -> dict:
    return _ok("Hello, world!")


@litestar.post("/commands")
async def issue_command(data: dict) -> dict:
    return insert_command(data)


@litestar.get("/checkpoint")
async def get_checkpoint() -> dict:
    return database.checkpoint_data()


app = litestar.Litestar([index, issue_command, get_checkpoint])
