"""Game node service entrypoint."""

from .service import run_game_node


def main() -> None:
    run_game_node()


if __name__ == "__main__":
    main()
