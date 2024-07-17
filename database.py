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
    chkpt = redis.get(checkpoint)
    if chkpt is not None:
        return int(chkpt)
    else:
        return None


def roll(k, amount):
    if k is None:
        k = 0
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
        yield (initial, new)

    except Exception as err:
        print(f"Not incrementing: {err}.  Checkpoint is: {initial}")
        return initial

    else:
        print(f"Advancing to checkpoint {new}")
        redis.set(checkpoint, new)
        return new


def read(k=None):
    k = k or get_checkpoint()
    if k is None:
        return {}

    return json.loads(redis.get(f"db-save-{k}") or "null")


def write(data):
    with incrementing_checkpoint() as (old, new):
        current = read(old)
        if current != data:
            print(
                f"Found change from data in checkpoint {old}:"
                f"\nold={current}\n{data=}"
            )
            redis.set(f"db-save-{new}", json.dumps(data))
            redis.set(f"ts:db-save-{new}", datetime.datetime.now().timestamp())
        else:
            msg = (
                f"Skipping commit of checkpoint {new} as there is no change "
                f"to the state.  Using checkpoint {old}."
            )
            print(msg)
            raise ValueError(msg)


@contextmanager
def editing():
    game = read()
    enveloped = {"data": game}
    try:
        yield enveloped
    except Exception:
        print(f"Error editing state.  Found: {enveloped=}")
    else:
        write(enveloped.get("data"))
