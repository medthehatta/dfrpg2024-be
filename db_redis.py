import os
from redis import Redis

redis_host = os.environ.get("REDIS_HOST", "localhost")
redis_port = os.environ.get("REDIS_PORT", "6379")

redis_password = os.environ["REDIS_PASSWORD"]

redis = Redis(
    host=redis_host,
    port=redis_port,
    db=0,
    password=redis_password,
    decode_responses=True,
)
