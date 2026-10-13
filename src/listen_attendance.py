"""
Print attendance events as Redpanda receives them.

Start the containers and the API, then from the project root:

    python src/listen_attendance.py

In another terminal, POST /attendance. This window prints the event.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from stream import listen  # noqa: E402


if __name__ == "__main__":
    listen()
