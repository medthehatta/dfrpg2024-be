import json
import os

from redis import Redis

from utils import query_eventually

redis_port = os.environ.get("REDIS_PORT", "6379")

redis = Redis(host="localhost", port=redis_port, db=0, decode_responses=True)


NOT_READY = "__NOT__READY__"
command_stream = "commands"



def wait_for_commands():
    result = redis.xread(streams={command_stream: "$"}, block=0)
    entries = dict(result)
    print(entries)
    for (entry_id, entry) in entries[command_stream]:
        yield (entry_id, json.loads(entry["data"]))


def read_command_log():
    result = redis.xrange(command_stream)
    for (entry_id, entry) in result:
        yield (entry_id, json.loads(entry["data"]))


def insert_command(command):
    added = redis.xadd(command_stream, {"data": json.dumps(command)})
    store_result(NOT_READY, added)
    redis.save()
    return added


def store_result(data, key):
    redis.set(key, json.dumps(data))


def read_result(key):
    res = redis.get(key)
    if res:
        return json.loads(res)
    else:
        return None


def wait_for_result(key):

    query_eventually(
        lambda: (key, read_result(key)),
        lambda result: result[1] is not None,
        interval=1,
        max_time=3,
    )

    return read_result(key)
