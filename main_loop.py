import json
from functools import wraps

from command_stream import wait_for_commands
from command_stream import read_command_log
from command_stream import store_result
from contextlib import contextmanager
from database import editing
from utils import get_path
from errors import _ok
from errors import _error
from errors import _exception
from errors import _fail


example_game = {
    "entities": {
        "Umbra": {
            "fate": 5,
            "refresh": 9,
            "stress": {
                "physical": {
                    "checked": [2, 4],
                    "max": 5,
                },
                "mental": {
                    "checked": [],
                    "max": 2,
                },
                "hunger": {
                    "checked": [1, 2],
                    "max": 3,
                },
            },
            "aspects": [
                {"name": "Well-rested"},
                {"name": "Rekt", "kind": "temporary"},
                {"name": "Rekt", "kind": "sticky"},
                {"name": "Rekt", "tags": 1},
            ],
        },
    },
    "order": ["Umbra", "Nick", "Jackson"],
}


#
# Processing helpers
#


class CommandRegistrar:

    def __init__(self):
        self.commands = {}

    def register(self, *names):

        def _register(func):
            for name in names:
                self.commands[name] = func

            @wraps(func)
            def _a(*args, **kwargs):
                return func(*args, **kwargs)

            return _a

        return _register

    def get(self, cmd):
        return self.commands.get(cmd)


cmds = CommandRegistrar()


def process_command(game, cmd, entry_id=None):
    func = cmds.get(cmd.get("command"))

    if func:
        try:
            result = func(game, cmd)
        except Exception as err:
            result = _exception(err)
    else:
        result = _error(cmd, "Unrecognized command")

    if entry_id is not None:
        store_result(result, entry_id)

    return result


#
# Processing commands
#


@cmds.register("create_entity")
def _create_entity(game, cmd):
    name = cmd["name"]
    maxes = cmd["stress_maxes"]
    refresh = cmd["refresh"]
    entities = get_path(game, ["entities"])
    if name in entities:
        return _error(
            list(entities.keys()),
            f"Entity {name} already exists!",
        )
    entities[name] = {
        "fate": 0,
        "refresh": refresh,
        "aspects": [],
        "stress": {k: {"checked": [], "max": m} for (k, m) in maxes.items()},
    }
    return _ok(entities[name])


@cmds.register("decrement_fp")
def _decrement_fp(game, cmd):
    entity = cmd["entity"]
    fp = get_path(game, ["entities", entity, "fate"])
    if fp >= 1:
        e = get_path(game, ["entities", entity])
        e["fate"] -= 1
        return _ok(get_path(game, ["entities", entity]))
    else:
        return _error(
            get_path(game, ["entities", entity]),
            "Not enough FP to decrement",
        )


@cmds.register("set_fp")
def _set_fp(game, cmd):
    entity = cmd["entity"]
    fp = cmd["fp"]
    e = get_path(game, ["entities", entity])
    e["fate"] = fp
    return _ok(get_path(game, ["entities", entity]))


@cmds.register("refresh_fp")
def _refresh_fp(game, cmd):
    entity = cmd["entity"]
    refresh = get_path(game, ["entities", entity, "refresh"])
    fp = get_path(game, ["entities", entity, "fate"])
    new = max(fp, refresh)
    e = get_path(game, ["entities", entity])
    e["fate"] = new
    return _ok(get_path(game, ["entities", entity]))


@cmds.register("test")
def _test(game, cmd):
    return _ok(cmd.get("string", "foo"))


#
# Basic plumbing
#


stream = "commands"


def commands_incoming():
    while True:
        yield from wait_for_commands()


def populate():
    with editing() as game:
        for (_, command) in read_command_log():
            print(game)
            res = process_command(game, command, entry_id=None)
            print(f"populate | {command} | {res}")


def main_loop():
    while True:
        with editing() as game:
            for (entry_id, command) in wait_for_commands():
                res = process_command(game, command, entry_id=entry_id)
                print(f"main | {command} | {res}")


def main():
    print("Populating with log...")
    populate()
    print("Done.")
    print("Reading stream...")
    main_loop()


if __name__ == "__main__":
    main()
