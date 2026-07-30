"""Edge gateway service entrypoint."""

import asyncio

from .server import main as run_server


def main() -> None:
    asyncio.run(run_server())


if __name__ == "__main__":
    main()
