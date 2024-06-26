from contextlib import contextmanager
import glob
import json
import os
import time

from command_stream import insert_command
from command_stream import wait_for_result
from command_stream import read_command_log
import database

from errors import _ok
from errors import _exception
from errors import _error


#
# Processing
#


#
# Basic plumbing
#


stream = "commands"


def reset():
    for x in glob.glob("db-save-*"):
        os.remove(x)
    for k in database.redis.keys():
        database.redis.delete(k)


def issue(cmd):
    key = insert_command(cmd)
    try:
        return _ok(wait_for_result(key))
    except Exception as err:
        return _exception(err)


def pissue(cmd):
    res = issue(cmd)
    print(json.dumps(res))
    return res


def setup():
    pissue(
        {
            "command": "create_entity",
            "name": "Umbra",
            "stress_maxes": {"physical": 5, "mental": 2, "hunger": 2},
            "refresh": 2,
        }
    )
    pissue(
        {
            "command": "create_entity",
            "name": "Rayne",
            "stress_maxes": {"physical": 7, "mental": 2, "hunger": 3},
            "refresh": 3,
        }
    )
    pissue(
        {
            "command": "create_entity",
            "name": "Smelly",
            "stress_maxes": {"physical": 7, "mental": 2, "hunger": 3},
            "refresh": 3,
        }
    )
    pissue(
        {
            "command": "create_entity",
            "name": "Tasty",
            "stress_maxes": {"physical": 7, "mental": 2, "hunger": 3},
            "refresh": 3,
        }
    )
