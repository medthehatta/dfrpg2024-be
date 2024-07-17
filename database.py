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


def roll(k, amount):
    return (k + amount) % keep


def incr_checkpoint():
    new = roll(get_checkpoint(), 1)
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
    by_time = sorted(
        listing,
        key=lambda x: redis.get(f"ts:{x}") or -1,
        reverse=True,
    )
    return {
        "current": current,
        "listing": [int(x.replace("db-save-", "")) for x in by_time],
    }


@contextmanager
def incrementing_checkpoint():
    initial = get_checkpoint()
    new = roll(initial, 1)
    try:
        yield new

    except Exception:
        return initial

    else:
        redis.set(checkpoint, new)
        return new


def read(k=None):
    k = k or get_checkpoint()
    if k == 0:
        return {}

    return json.loads(redis.get(f"db-save-{k}") or "{}")


def write(data):
    with incrementing_checkpoint() as k:
        current = read(roll(k, -1))
        if current != data:
            redis.set(f"db-save-{k}", json.dumps(data))
            redis.set(f"ts:db-save-{k}", datetime.datetime.now().timestamp())
        else:
            print(
                f"Skipping commit of checkpoint {k} as there is no change "
                f"to the state."
            )


@contextmanager
def editing():
    game = read()
    enveloped = {"data": game}
    try:
        yield enveloped
    finally:
        write(enveloped.get("data", {}))
