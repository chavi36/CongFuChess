"""Result writer service entrypoint."""

from .service import run_result_writer


def main() -> None:
    run_result_writer()


if __name__ == "__main__":
    main()
