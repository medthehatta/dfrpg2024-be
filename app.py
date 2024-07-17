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
from utils import flat_diff


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


@litestar.get("/checkpoint/{id_:int}")
async def get_checkpoint(id_: int) -> dict:
    return _ok(database.read(id_))


@litestar.get("/checkpoint/{id_:int}/diff")
async def get_checkpoint_diff(id_: int) -> dict:
    previous = database.read(database.roll(id_, -1))
    current = database.read(id_)
    diffed = list(flat_diff(previous, current))
    result = {
        "insertions": [
            (x, a) for (op, x, a, *bs) in diffed if op == "insert"
        ],
        "deletions": [
            (x, a) for (op, x, a, *bs) in diffed if op == "delete"
        ],
        "changes": [
            (x, a, bs[0]) for (op, x, a, *bs) in diffed if op == "edit"
        ],
    }

    return _ok(result)


@litestar.get("/game")
async def get_game() -> dict:
    try:
        result = database.read()
        return _ok(result)
    except Exception as err:
        return _exception(err)


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


@litestar.post("/entity")
async def create_entity(data: dict) -> dict:
    cmd = {"command": "create_entity", **data}
    key = insert_command(cmd)
    try:
        return _ok(wait_for_result(key))
    except Exception as err:
        return _exception(err)


routes = [
    index,
    issue_command,
    get_checkpoints,
    get_checkpoint,
    get_checkpoint_diff,
    get_game,
    get_entity,
    post_entity,
    create_entity,
]
app = litestar.Litestar(routes)
