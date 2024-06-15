import json
from command_stream import wait_for_commands
from command_stream import read_command_log
from contextlib import contextmanager
from database import editing


#
# Processing
#


def process_command(game, cmd):
    # Inflict stress
    # Clear stress box
    # Clear all stress
    # Add aspect
    # Tag aspect
    # Remove aspect
    # Clear temporary aspects
    # Increment FP
    # Decrement FP
    # Set FP
    # Refresh FP
    # Establish initiative roll
    # Compute turn order
    # Clear turn order and initiative rolls


#
# Basic plumbing
#


stream = "commands"


def commands_incoming():
    while True:
        yield from wait_for_commands()


def populate():
    with editing() as game:
        for command in read_command_log():
            process_command(game, command)


def main_loop():
    while True:
        with editing() as game:
            for command in wait_for_commands():
                process_command(game, command)


def main():
    print("Populating with log...")
    populate()
    print("Done.")
    print("Reading stream...")
    main_loop()


if __name__ == "__main__":
    main()
