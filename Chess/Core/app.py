"""
Kungfu Chess application entry point.
"""

import sys
import os

# Force unbuffered stdout so output is always flushed to the platform.
sys.stdout.reconfigure(line_buffering=True)

# Allow running as a plain script (python kungfu_chess/app.py) in addition
# to running as a module (python -m kungfu_chess.app).
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from Core.texttests.script_runner import run_from_stdin


def main() -> None:
    run_from_stdin()
    sys.stdout.flush()


if __name__ == "__main__":
    main()
