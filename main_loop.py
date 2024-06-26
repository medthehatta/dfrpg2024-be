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
    g = game["data"]
    name = cmd["name"]
    maxes = cmd["stress_maxes"]
    refresh = cmd["refresh"]
    if "entities" not in g:
        g["entities"] = {}
    entities = get_path(g, ["entities"])
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


@cmds.register("set_entity")
def _set_entity(game, cmd):
    g = game["data"]
    name = cmd["name"]
    entity_value = cmd["entity_value"]
    if "entities" not in g:
        g["entities"] = {}
    entities = get_path(g, ["entities"])
    if name in entities:
        return _error(
            list(entities.keys()),
            f"Entity {name} already exists!",
        )
    entities[name] = entity_value
    return _ok(entities[name])


@cmds.register("remove_entity")
def _remove_entity(game, cmd):
    g = game["data"]
    name = cmd["name"]
    entity_name = cmd["entity"]
    if "entities" not in g:
        g["entities"] = {}
    entities = get_path(g, ["entities"])
    if name not in entities:
        return _error(
            list(entities.keys()),
            f"Entity {name} not present!",
        )
    else:
        entities.pop(name)
        return _ok(entities)


@cmds.register("decrement_fp")
def _decrement_fp(game, cmd):
    g = game["data"]
    entity = cmd["entity"]
    e = get_path(g, ["entities", entity])
    fp = e["fate"]
    if fp >= 1:
        e["fate"] -= 1
        return _ok(e)
    else:
        return _error(
            e,
            "Not enough FP to decrement",
        )


@cmds.register("increment_fp")
def _increment_fp(game, cmd):
    g = game["data"]
    entity = cmd["entity"]
    e = get_path(g, ["entities", entity])
    e["fate"] += 1
    return _ok(e)


@cmds.register("set_fp")
def _set_fp(game, cmd):
    g = game["data"]
    entity = cmd["entity"]
    fp = cmd["fp"]
    e = get_path(g, ["entities", entity])
    e["fate"] = fp
    return _ok(e)


@cmds.register("refresh_fp")
def _refresh_fp(game, cmd):
    g = game["data"]
    entity = cmd["entity"]
    e = get_path(g, ["entities", entity])
    refresh = e["refresh"]
    fp = e["fate"]
    new = max(fp, refresh)
    e["fate"] = new
    return _ok(e)


@cmds.register("add_aspect")
def _add_aspect(game, cmd):
    g = game["data"]
    entity = cmd["entity"]
    aspect = {}
    aspect["name"] = cmd["aspect"]
    if "kind" in cmd:
        aspect["kind"] = cmd["kind"]
    if "tags" in cmd:
        aspect["tags"] = cmd["tags"]
    e = get_path(g, ["entities", entity])
    e["aspects"].append(aspect)
    return _ok(e)


@cmds.register("remove_aspect")
def _remove_aspect(game, cmd):
    g = game["data"]
    entity = cmd["entity"]
    aspect_name = cmd["aspect"]
    e = get_path(g, ["entities", entity])
    current_names = [a["name"] for a in e.get("aspects", [])]
    if aspect_name in current_names:
        e["aspects"] = [a for a in e.get("aspects", []) if a["name"] != aspect_name]
        return _ok(e)
    else:
        return _error(
            e["aspects"],
            f"No aspect '{aspect_name}' present on '{entity}'",
        )


@cmds.register("remove_all_temporary_aspects")
def _remove_all_temp_aspects(game, cmd):
    g = game["data"]
    long_aspects = [
        "mild",
        "moderate",
        "severe",
        "extreme",
        "sticky",
    ]
    if "entities" not in g:
        g["entities"] = {}
    for entity_name in g.get("entities", []):
        entity = get_path(g, ["entities", entity_name])
        entity["aspects"] = [
            a for a in entity.get("aspects", [])
            if a["kind"] not in long_aspects
        ]
    return _ok(g["entities"])


@cmds.register("add_stress")
def _add_stress(game, cmd):
    g = game["data"]
    stress_kind = cmd["stress"]
    box = cmd["box"]
    entity = cmd["entity"]
    e = get_path(g, ["entities", entity])
    s = get_path(e, ["stress", stress_kind], default=None)
    if s is None:
        return _error(e, f"Entity {entity} has no stress track {stress_kind}")
    if box > s["max"]:
        return _error(
            e,
            (
                f"Entity {entity} cannot take {box} {stress_kind} "
                f"stress without consequence!"
            ),
        )
    if box in s["checked"]:
        return _error(
            e,
            (
                f"Entity {entity} already has the {box} "
                f"{stress_kind} stress checked"
            ),
        )
    # Otherwise
    s["checked"].append(box)
    return _ok(e)


@cmds.register("clear_stress_box")
def _clear_stress_box(game, cmd):
    g = game["data"]
    stress_kind = cmd["stress"]
    box = cmd["box"]
    entity = cmd["entity"]
    e = get_path(g, ["entities", entity])
    s = get_path(e, ["stress", stress_kind], default=None)
    if s is None:
        return _error(e, f"Entity {entity} has no stress track {stress_kind}")
    if box > s["max"]:
        return _error(
            e,
            (
                f"Entity {entity} does not have a {box} {stress_kind} "
                f"stress box at all"
            ),
        )
    if box not in s["checked"]:
        return _error(
            e,
            (
                f"Entity {entity} doesn't have the {box} "
                f"{stress_kind} stress box checked"
            ),
        )
    # Otherwise
    s["checked"] = [b for b in s["checked"] if b != box]
    return _ok(e)


@cmds.register("clear_all_stress")
def _clear_all_stress(game, cmd):
    g = game["data"]
    if "entities" not in g:
        g["entities"] = {}
    entities = get_path(g, ["entities"])
    for entity in entities:
        e = entities[entity]
        for s in e["stress"]:
            e[s]["checked"] = []
    return _ok(entities)


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
