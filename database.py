from contextlib import contextmanager
import json
import glob
import os
import re
import datetime

from db_redis import redis


checkpoint = "persist-checkpoint"
keep = 50


def get_checkpoint():
    return int(redis.get(checkpoint) or 0)


def incr_checkpoint():
    new = (get_checkpoint() + 1) % keep
    redis.set(checkpoint, new)
    return new


def set_checkpoint(value):
    if value >= keep:
        raise ValueError(f"Invalid: {value} exceeds keep {keep}")
    if not os.path.exists(f"db-save-{value}.json"):
        raise ValueError(f"Invalid: {value} is not persisted")
    return redis.set(checkpoint, value)


def checkpoint_data():
    current = get_checkpoint()
    globs = glob.glob("db-save-*.json")
    mtimes = [os.path.getmtime(p) for p in globs]
    listing = [
        {
            "path": int(re.search(r'db-save-(\d+).json', path).group(1)),
            "mtime": datetime.datetime.fromtimestamp(mtime).isoformat(),
            "size": os.path.getsize(path),
        }
        for (path, mtime) in zip(globs, mtimes)
    ]
    return {
        "current": current,
        "listing": sorted(
            listing,
            key=lambda x: x["mtime"],
            reverse=True,
        ),
    }


@contextmanager
def incrementing_checkpoint():
    initial = get_checkpoint()
    new = (initial + 1) % keep
    try:
        yield new

    except Exception:
        return initial

    else:
        redis.set(checkpoint, new)
        return new


def read():
    k = get_checkpoint()
    if k == 0:
        return {}

    with open(f"db-save-{k}.json", "r") as f:
        return json.load(f)


# This is ok because there will only be one process allowed to write

def write(data):
    with incrementing_checkpoint() as k:
        with open(f"db-save-{k}.json", "w") as f:
            json.dump(data, f)


@contextmanager
def editing():
    game = read()
    enveloped = {"data": game}
    try:
        yield enveloped
    finally:
        write(enveloped.get("data", {}))
