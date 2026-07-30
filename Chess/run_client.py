"""
run_client.py — launch the Kung-Fu Chess GUI client.

Run from the repo root:
    python Chess/run_client.py

Or from the Chess/ directory:
    python run_client.py
"""
import sys
import os

_here = os.path.dirname(os.path.abspath(__file__))
_root = os.path.dirname(_here)
for _p in (_here, _root):
    if _p not in sys.path:
        sys.path.insert(0, _p)

os.chdir(_here)  # DB and CSV paths are relative to Chess/

from client.client import main

if __name__ == "__main__":
    main()
