"""Auth service entrypoint."""

from . import init_db


def main() -> None:
    init_db()
    print("Auth service started and database initialized")


if __name__ == "__main__":
    main()
