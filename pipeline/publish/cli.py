import argparse

import json
import logging
from datetime import datetime, timezone
from pathlib import Path

from pipeline.paths import UniversePaths
from pipeline.publish.context import PublishContext
from pipeline.publish.runner import run_publisher


def _default_run_id() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H%M%SZ")


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    parser = argparse.ArgumentParser(prog="publish")
    sub = parser.add_subparsers(dest="command", required=True)

    run_p = sub.add_parser("run", help="Validate merged Silver → Gold")
    run_p.add_argument("--merged-run-id", required=True)
    run_p.add_argument("--run-id", default=_default_run_id())
    run_p.add_argument(
        "--universe-root",
        type=Path,
        default=Path("universe"),
        help="Root of runtime output tree (see universe/README.md)",
    )

    args = parser.parse_args()
    ctx = PublishContext(
        run_id=args.run_id,
        merged_run_id=args.merged_run_id,
        paths=UniversePaths(root=args.universe_root),
    )
    manifest = run_publisher(ctx)
    print(json.dumps(manifest["output"], indent=2))
