"""
Register the Debezium PostgreSQL connector with Kafka Connect.

Order matters. Run the loader first, because it drops and recreates the tables:

    docker compose up -d
    python src/loader/load_events.py
    python src/streaming/register_connector.py

Then check that it is running:

    python src/streaming/register_connector.py --status

After you re-run the loader, remove the old connector and register it again:

    python src/streaming/register_connector.py --reset
"""

import argparse
import json
import urllib.error
import urllib.request
from pathlib import Path

CONNECT = "http://localhost:8083"
CONFIG = Path(__file__).resolve().parents[2] / "debezium" / "postgres-connector.json"


def call(method: str, path: str, body: dict | None = None):
    data = json.dumps(body).encode() if body is not None else None
    request = urllib.request.Request(
        CONNECT + path,
        data=data,
        method=method,
        headers={"Content-Type": "application/json"},
    )
    try:
        with urllib.request.urlopen(request, timeout=15) as response:
            text = response.read().decode()
            return response.status, json.loads(text) if text else None
    except urllib.error.HTTPError as error:
        return error.code, error.read().decode()
    except urllib.error.URLError:
        raise SystemExit(
            "Kafka Connect is not answering on localhost:8083.\n"
            "Start it with: docker compose up -d   (it needs about a minute)"
        )


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--status", action="store_true")
    parser.add_argument("--reset", action="store_true", help="Delete the connector first.")
    args = parser.parse_args()

    config = json.loads(CONFIG.read_text(encoding="utf-8"))
    name = config["name"]

    if args.status:
        code, body = call("GET", f"/connectors/{name}/status")
        print(code, json.dumps(body, indent=2) if isinstance(body, dict) else body)
        return

    if args.reset:
        code, _ = call("DELETE", f"/connectors/{name}")
        print(f"Deleted old connector (HTTP {code}).")

    code, body = call("PUT", f"/connectors/{name}/config", config["config"])
    if code not in (200, 201):
        raise SystemExit(f"Could not register the connector (HTTP {code}): {body}")
    print(f"Connector {name} registered (HTTP {code}).")
    print("Check it with: python src/streaming/register_connector.py --status")


if __name__ == "__main__":
    main()
