import json
from functools import wraps
import random

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
    maxes = cmd.get("stress_maxes") or {}
    refresh = cmd.get("refresh") or 0
    fate = cmd.get("fate") or 0
    if "entities" not in g:
        g["entities"] = {}
    entities = get_path(g, ["entities"])
    if name in entities:
        return _error(
            list(entities.keys()),
            f"Entity {name} already exists!",
        )
    entities[name] = {
        "name": name,
        "fate": fate,
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
    entities[name] = entity_value
    return _ok(entities[name])


@cmds.register("remove_entity")
def _remove_entity(game, cmd):
    g = game["data"]
    name = cmd["entity"]
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
    aspect["name"] = cmd["name"]
    if "kind" in cmd:
        aspect["kind"] = cmd["kind"]
    if "tags" in cmd:
        aspect["tags"] = cmd["tags"]
    e = get_path(g, ["entities", entity])
    existing = [a["name"].lower() for a in e["aspects"]]
    if aspect.lower() in existing:
        return _error(
            existing,
            f"Aspect {aspect} already present on {entity}",
        )
    else:
        e["aspects"].append(aspect)
        return _ok(e)


@cmds.register("remove_aspect")
def _remove_aspect(game, cmd):
    g = game["data"]
    entity = cmd["entity"]
    aspect_name = cmd["name"]
    e = get_path(g, ["entities", entity])
    current_names = [a["name"].lower() for a in e.get("aspects", [])]
    if aspect_name.lower() in current_names:
        e["aspects"] = [
            a for a in e.get("aspects", [])
            if a["name"].lower() != aspect_name.lower()
        ]
        return _ok(e)
    else:
        return _error(
            e["aspects"],
            f"No aspect '{aspect_name}' present on '{entity}'",
        )


@cmds.register("tag_aspect")
def _tag_aspect(game, cmd):
    g = game["data"]
    entity = cmd["entity"]
    aspect_name = cmd["name"]
    e = get_path(g, ["entities", entity])
    current_names = [a["name"].lower() for a in e.get("aspects", [])]
    if aspect_name.lower() in current_names:
        aspect = next(
            a for a in e.get("aspects", [])
            if a["name"].lower() == aspect_name.lower()
        )
        if aspect["tags"] > 0:
            aspect["tags"] -= 1
            return _ok(e)
        else:
            return _error(
                e["aspects"],
                f"Aspect '{aspect_name}' on '{entity}' has no free tags",
            )

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
            if a.get("kind") in long_aspects
        ]
    return _ok(g["entities"])


@cmds.register("clear_consequences")
def _clear_consequences(game, cmd):
    g = game["data"]
    severities = [
        "mild",
        "moderate",
        "severe",
        "extreme",
    ]
    sev = cmd["max_severity"]

    try:
        last_sev_idx = severities.index(sev)
    except ValueError:
        return _error(
            severities,
            f"Invalid severity: {sev}"
        )

    aspects_to_keep = severities[last_sev_idx+1:]
    print(f"{sev=} {last_sev_idx=} {aspects_to_keep=}")

    if "entities" not in g:
        g["entities"] = {}

    for entity_name in g.get("entities", []):
        entity = get_path(g, ["entities", entity_name])
        entity["aspects"] = [
            a for a in entity.get("aspects", [])
            if a.get("kind") in aspects_to_keep
        ]

    return _ok(g["entities"])


@cmds.register("add_stress")
def _add_stress(game, cmd):
    g = game["data"]
    stress_kind = cmd["stress"]
    box = int(cmd["box"])
    entity = cmd["entity"]
    e = get_path(g, ["entities", entity])
    s = get_path(e, ["stress", stress_kind], default=None)
    if s is None:
        return _error(e, f"Entity {entity} has no {stress_kind} stress track")
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
                f"Entity {entity} has already used the {box} "
                f"{stress_kind} stress box"
            ),
        )
    # Otherwise
    s["checked"].append(box)
    return _ok(e)


@cmds.register("clear_stress_box")
def _clear_stress_box(game, cmd):
    g = game["data"]
    stress_kind = cmd["stress"]
    box = int(cmd["box"])
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
            e["stress"][s]["checked"] = []
    return _ok(entities)


def _default_order():
    default_order = {
        "entities": [],
        "bonuses": {},
        "order": [],
        "current": None,
        "deferred": [],
    }
    return {
        k: (v.copy() if hasattr(v, "copy") else v)
        for (k, v) in default_order.items()
    }


def _ensure_order(g):
    if "order" not in g:
        g["order"] = _default_order()


@cmds.register("order_add")
def _order_add(game, cmd):
    g = game["data"]
    entity = cmd["entity"]
    bonus = int(cmd["bonus"])
    e = get_path(g, ["entities", entity])
    _ensure_order(g)
    g["order"]["entities"] = list(
        set(g["order"]["entities"]).union({entity})
    )
    g["order"]["bonuses"][entity] = bonus
    return _ok(g["order"])


@cmds.register("next")
def _next(game, cmd):
    g = game["data"]
    _ensure_order(g)
    if g["order"]["current"] is not None and g["order"]["order"]:
        g["order"]["current"] = (
            (g["order"]["current"] + 1) % len(g["order"]["order"])
        )
    else:
        _start_order(game, {})
    return _ok(g["order"])


@cmds.register("back")
def _back(game, cmd):
    g = game["data"]
    _ensure_order(g)
    if g["order"]["current"] is not None and g["order"]["order"]:
        g["order"]["current"] = (
            (g["order"]["current"] - 1) % len(g["order"]["order"])
        )
    else:
        _start_order(game, {})
    return _ok(g["order"])


@cmds.register("drop_from_order")
def _drop_from_order(game, cmd):
    g = game["data"]
    entity = cmd.get("entity")
    _ensure_order(g)
    if g["order"]["current"] is not None and g["order"]["order"]:
        if not entity:
            current = g["order"]["current"]
            entity = g["order"]["order"][current]
        g["order"]["entities"].remove(entity)
        g["order"]["order"].remove(entity)
        g["order"]["current"] = (
            g["order"]["current"] % len(g["order"]["order"])
        )
    return _ok(g["order"])


@cmds.register("defer")
def _order_defer(game, cmd):
    g = game["data"]
    _ensure_order(g)
    if len(g["order"]["order"]) <= 1:
        return _error(
            g["order"],
            f"Can't defer, or nobody will be in the turn order!",
        )
    if g["order"]["current"] is not None and g["order"]["order"]:
        current = g["order"]["current"]
        active = g["order"]["order"][current]
        g["order"]["deferred"].append(active)
        g["order"]["order"].remove(active)
        g["order"]["current"] = (
            g["order"]["current"] % len(g["order"]["order"])
        )
    return _ok(g["order"])


@cmds.register("undefer")
def _order_undefer(game, cmd):
    g = game["data"]
    _ensure_order(g)
    entity = cmd.get("entity")
    if entity not in g["order"]["deferred"]:
        return _error(g["order"], f"Entity '{entity}' has not deferred")

    if g["order"]["current"] is not None and g["order"]["order"]:
        current = g["order"]["current"]
        g["order"]["order"].insert(current, entity)
        g["order"]["deferred"].remove(entity)
        g["order"]["current"] = (
            g["order"]["current"] % len(g["order"]["order"])
        )
    return _ok(g["order"])


@cmds.register("start_order")
def _start_order(game, cmd):
    g = game["data"]
    _ensure_order(g)
    g["order"]["order"] = sorted(
        g["order"]["entities"],
        key=lambda x: (g["order"]["bonuses"].get(x, 0), random.random()),
        reverse=True,
    )
    g["order"]["current"] = 0
    return _ok(g["order"])


@cmds.register("clear_order")
def _clear_order(game, cmd):
    g = game["data"]
    g["order"] = _default_order()
    return _ok(g["order"])


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
            res = process_command(game, command, entry_id=None)
            print(f"populate | {command} | {res}")


def main_loop():
    last = "$"
    while True:
        with editing() as game:
            for (entry_id, command) in wait_for_commands(last):
                res = process_command(game, command, entry_id=entry_id)
                print(f"main | {command} | {res}")
                last = entry_id


def main():
    print("Populating with log...")
    populate()
    print("Done.")
    print("Reading stream...")
    main_loop()


if __name__ == "__main__":
    main()
