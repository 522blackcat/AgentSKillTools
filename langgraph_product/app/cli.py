"""Small CLI for local platform checks."""

from __future__ import annotations

import argparse

from app.database.session import init_db


def main() -> None:
    parser = argparse.ArgumentParser(description="LangGraph Product platform CLI")
    subparsers = parser.add_subparsers(dest="command", required=True)
    subparsers.add_parser("init-db", help="Create local database tables")
    args = parser.parse_args()
    if args.command == "init-db":
        init_db()
        print("database initialized")


if __name__ == "__main__":
    main()
