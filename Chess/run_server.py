"""
run_server.py — launch the Kung-Fu Chess WebSocket server.

Run from the repo root:
    python Chess/run_server.py

Or from the Chess/ directory:
    python run_server.py
"""
import sys
import os

_here = os.path.dirname(os.path.abspath(__file__))
_root = os.path.dirname(_here)
# Chess/ must come first so bare imports (services.*, Core.*, application.*) resolve,
# then repo root so Chess.* resolves.
for _p in (_here, _root):
    if _p not in sys.path:
        sys.path.insert(0, _p)

os.chdir(_here)  # DB and CSV paths are relative to Chess/

import asyncio
import logging
from services.edge_gateway.server import main

if __name__ == "__main__":
    logging.basicConfig(level=logging.DEBUG)
    try:
        asyncio.run(main())
    except Exception:
        import traceback
        traceback.print_exc()
        sys.exit(1)
