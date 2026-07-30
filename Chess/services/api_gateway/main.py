"""API gateway service entrypoint."""

from services.edge_gateway.main import main as run_edge_gateway


def main() -> None:
    """Run the API gateway service via the edge gateway service implementation."""
    run_edge_gateway()


if __name__ == "__main__":
    main()
