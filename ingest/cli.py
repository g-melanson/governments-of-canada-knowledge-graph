"""Command-line interface for running ingest adapters and listing sources."""

from __future__ import annotations

import argparse
import json
import logging
from datetime import datetime, timezone
from pathlib import Path

from ingest.adapters.registry import list_sources
from ingest.context import RunContext
from ingest.runner import run_ingest

# Import adapters so @register runs
import ingest.adapters.commons.members  # noqa: F401
import ingest.adapters.open_canada.contribution  # noqa: F401


def _default_run_id() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H%M%SZ")


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    parser = argparse.ArgumentParser(prog="ingest")
    sub = parser.add_subparsers(dest="command", required=True)

    run_p = sub.add_parser("run", help="Run one source adapter")
    run_p.add_argument("--source", required=True)
    run_p.add_argument("--run-id", default=_default_run_id())
    run_p.add_argument("--staging-root", type=Path, default=Path("staging"))
    run_p.add_argument(
        "--fetch-policy",
        choices=["default", "refresh", "cache-only", "local-file"],
        default="default",
    )
    run_p.add_argument("--input", type=Path, help="Local raw file (local-file policy)")

    sub.add_parser("list-sources", help="List registered adapters")

    args = parser.parse_args()
    if args.command == "list-sources":
        for name in list_sources():
            print(name)
        return

    ctx = RunContext(
        source=args.source,
        run_id=args.run_id,
        staging_root=args.staging_root,
        fetch_policy=args.fetch_policy,
        input_path=args.input,
    )
    manifest = run_ingest(ctx)
    print(json.dumps(manifest["output"], indent=2))


if __name__ == "__main__":
    main()
