import argparse

import json
import logging
from datetime import datetime, timezone
from pathlib import Path

from pipeline.paths import UniversePaths
from pipeline.transforms.context import TransformContext
from pipeline.transforms.runner import run_transform


def _default_run_id() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H%M%SZ")


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    parser = argparse.ArgumentParser(prog="transforms")
    sub = parser.add_subparsers(dest="command", required=True)

    run_p = sub.add_parser("run", help="Transform Bronze records → Silver")
    run_p.add_argument("--source", required=True)
    run_p.add_argument("--bronze-run-id", default=None, help="Bronze run id (defaults to --run-id)")
    run_p.add_argument("--run-id", default=_default_run_id())
    run_p.add_argument(
        "--universe-root",
        type=Path,
        default=Path("universe"),
        help="Root of runtime output tree (see pipeline/README.md)",
    )

    args = parser.parse_args()
    ctx = TransformContext(
        source=args.source,
        run_id=args.run_id,
        bronze_run_id=args.bronze_run_id,
        paths=UniversePaths(root=args.universe_root),
    )
    manifest = run_transform(ctx)
    print(json.dumps(manifest["output"], indent=2))
