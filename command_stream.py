import json
import os

from db_redis import redis

from utils import query_eventually


RESULT_TTL = 3600
command_stream = "commands"



def wait_for_commands(last="$"):
    result = redis.xread(streams={command_stream: last}, block=0)
    entries = dict(result)
    for (entry_id, entry) in entries[command_stream]:
        yield (entry_id, json.loads(entry["data"]))


def read_command_log():
    result = redis.xrange(command_stream)
    for (entry_id, entry) in result:
        yield (entry_id, json.loads(entry["data"]))


def insert_command(command):
    return redis.xadd(command_stream, {"data": json.dumps(command)})


def store_result(data, key):
    print(f"Saving data to {key}: {data}", flush=True)
    redis.set(key, json.dumps(data))
    redis.expire(key, RESULT_TTL)


def read_result(key):
    res = redis.get(key)
    if res:
        return json.loads(res)
    else:
        return None


def wait_for_result(key):

    def _read_result():
        return read_result(key)

    def _is_ready(result):
        return result is not None

    query_eventually(
        _read_result,
        _is_ready,
        interval=0.1,
        max_time=5,
    )

    return read_result(key)
