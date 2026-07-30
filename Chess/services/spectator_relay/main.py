"""Spectator relay service entrypoint."""

from .service import run_spectator_relay


def main() -> None:
    run_spectator_relay()


if __name__ == "__main__":
    main()
