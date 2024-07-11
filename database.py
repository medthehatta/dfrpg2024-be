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
    if not redis.get(f"db-save-{value}"):
        raise ValueError(f"Invalid: {value} is not persisted")
    return redis.set(checkpoint, value)


def checkpoint_data():
    current = get_checkpoint()
    listing = list(
        redis.scan_iter(match="db-save-*")
    )
    return {
        "current": current,
        "listing": sorted(
            listing,
            key=lambda x: redis.get(f"x:timestamp") or -1,
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

    return json.loads(redis.get(f"db-save-{k}") or "{}")


def write(data):
    with incrementing_checkpoint() as k:
        redis.set(f"db-save-{k}", json.dumps(data))
        redis.set(f"db-save-{k}:timestamp", datetime.datetime.now().timestamp())


@contextmanager
def editing():
    game = read()
    enveloped = {"data": game}
    try:
        yield enveloped
    finally:
        write(enveloped.get("data", {}))
