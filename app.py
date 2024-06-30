import litestar
from command_stream import insert_command
from command_stream import wait_for_result
import database
from functools import wraps

from errors import _ok
from errors import _exception
from errors import _fail
from errors import _error
from utils import get_path


@litestar.get("/")
async def index() -> dict:
    return _ok("Hello, world!")


@litestar.post("/commands")
async def issue_command(data: dict) -> dict:
    print(data)
    key = insert_command(data)
    try:
        return _ok(wait_for_result(key))
    except Exception as err:
        return _exception(err)


@litestar.get("/checkpoints")
async def get_checkpoints() -> dict:
    return _ok(database.checkpoint_data())


@litestar.get("/game")
async def get_game() -> dict:
    return _ok(database.read())


@litestar.get("/entity/{name:str}")
async def get_entity(name: str) -> dict:
    data = database.read()
    entity = get_path(data, ["entities", name], default=None)
    if entity is None:
        return _error(
            data.get("entities", []),
            f"No such entity '{name}'",
        )
    else:
        return _ok(entity)


@litestar.post("/entity/{name:str}")
async def post_entity(name: str, data: dict) -> dict:
    cmd = {"command": "set_entity", "entity_value": data}
    key = insert_command(cmd)
    try:
        return _ok(wait_for_result(key))
    except Exception as err:
        return _exception(err)


routes = [
    index,
    issue_command,
    get_checkpoints,
    get_game,
    get_entity,
    post_entity,
]
app = litestar.Litestar(routes)
