import litestar
from litestar.config.cors import CORSConfig

from command_stream import insert_command
from command_stream import wait_for_result
import database
from functools import wraps
from typing import Optional
import time
import random

from errors import _ok
from errors import _exception
from errors import _fail
from errors import _error
from utils import get_path
from utils import flat_diff


undo_predecessors = {}


@litestar.get("/")
async def index() -> dict:
    try:
        return _ok("Hello, world!")
    except Exception:
        return _exception(err)


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
    try:
        return _ok(database.checkpoint_data())
    except Exception:
        return _exception(err)


@litestar.get("/checkpoint/{id_:int}")
async def get_checkpoint(id_: int) -> dict:
    try:
        return _ok(database.read(id_))
    except Exception:
        return _exception(err)


@litestar.post("/checkpoint")
async def set_checkpoint(data: int) -> dict:
    checkpoint_id = data
    try:
        checkpoint_data = database.read(checkpoint_id)
        key = insert_command(
            {
                "command": "overwrite_state",
                "state": checkpoint_data,
            }
        )
        return _ok(wait_for_result(key))
    except Exception as err:
        return _exception(err)


@litestar.get("/checkpoint/{id_:int}/diff")
async def get_checkpoint_diff(id_: int, base: Optional[int] = None) -> dict:
    try:
        base = base or database.roll(id_, -1)
        previous = database.read(base)
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
    except Exception as err:
        return _exception(err)


@litestar.post("/undo")
async def undo() -> dict:
    current = database.get_checkpoint()
    pre = undo_predecessors.get(current, database.roll(current, -1))
    post = database.roll(current, 1)
    # Wait to make sure there is no contention
    time.sleep(1 + random.random())
    if database.get_checkpoint() != current:
        return _error(
            current,
            f"Can't undo while doing other operations.  Please try again.",
        )

    undo_predecessors[post] = pre

    try:
        checkpoint_data = database.read(pre)
        key = insert_command(
            {
                "command": "overwrite_state",
                "state": checkpoint_data,
            }
        )
        return _ok(wait_for_result(key))
    except Exception as err:
        return _exception(err)


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
        try:
            return _ok(entity)
        except Exception as err:
            return _exception(err)


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
    set_checkpoint,
    get_game,
    get_entity,
    post_entity,
    create_entity,
    undo,
]
cors_config = CORSConfig(allow_origins=["*"])
app = litestar.Litestar(
    route_handlers=routes,
    cors_config=cors_config,
)
