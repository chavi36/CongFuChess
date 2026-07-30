"""Allocator service entrypoint."""

from .service import run_allocator


def main() -> None:
    run_allocator()


if __name__ == "__main__":
    main()
