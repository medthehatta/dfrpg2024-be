import json
from command_stream import wait_for_commands
from command_stream import read_command_log
from contextlib import contextmanager


#
# Globals
#


game = {
    "entities": [],
}


#
# Processing
#


def process_command(cmd):
    print(cmd)


#
# Serialization
#


def entity_path(name):
    return f"db-entity-{name}.json"


@contextmanager
def entity_edit(name):
    with open(entity_path(name)) as f:
        original = json.load(f)
        result = json.load(f)
    try:
        yield result
    finally:
        if result != original:
            with open(entity_path(name), "w") as f:
                json.dump(result, f)


#
# Basic plumbing
#


stream = "commands"


def commands_incoming():
    while True:
        yield from wait_for_commands()


def populate():
    for command in read_command_log():
        process_command(command)


def main_loop():
    for command in commands_incoming():
        process_command(command)


def main():
    print("Populating with log...")
    populate()
    print("Done.")
    print("Reading stream...")
    main_loop()


if __name__ == "__main__":
    main()
