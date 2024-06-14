from redis import Redis


redis = Redis(host="localhost", port=6379, db=0, decode_responses=True)


command_stream = "commands"


def wait_for_commands():
    result = redis.xread(streams={command_stream: "$"}, block=0)
    entries = dict(result)
    for (entry_id, entry) in entries[command_stream]:
        yield entry


def read_command_log():
    result = redis.xrange(command_stream)
    for (entry_id, command) in result:
        yield command


def insert_command(command):
    added = redis.xadd(command_stream, command)
    redis.save()
    return added
