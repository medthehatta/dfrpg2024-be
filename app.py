import litestar
from command_stream import insert_command


@litestar.get("/")
async def index() -> str:
    return "Hello, world!"


@litestar.post("/commands")
async def issue_command(data: dict) -> dict:
    insert_command(data)
    return data


app = litestar.Litestar([index, issue_command])
