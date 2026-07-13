
from __future__ import annotations

import argparse
import json
import logging
from datetime import datetime, timezone
from pathlib import Path

from pipeline.paths import UniversePaths
from pipeline.validate.config import list_validatable_sources
from pipeline.validate.context import ValidateContext
from pipeline.validate.runner import run_validate


def _default_run_id() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H%M%SZ")


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    parser = argparse.ArgumentParser(prog="validate")
    sub = parser.add_subparsers(dest="command", required=True)

    run_p = sub.add_parser("run", help="Validate staging records → Bronze")
    run_p.add_argument("--source", required=True)
    run_p.add_argument(
        "--staging-run-id",
        default=None,
        help="Staging run id (defaults to --run-id)",
    )
    run_p.add_argument("--run-id", default=_default_run_id())
    run_p.add_argument(
        "--universe-root",
        type=Path,
        default=Path("universe"),
        help="Root of runtime output tree (see pipeline/README.md)",
    )
    run_p.add_argument(
        "--fail-fast",
        action="store_true",
        help="Stop on first invalid record (CI schema drift)",
    )

    sub.add_parser("list-sources", help="List sources with source schemas")

    args = parser.parse_args()
    if args.command == "list-sources":
        for name in list_validatable_sources():
            print(name)
        return

    paths = UniversePaths(root=args.universe_root)
    ctx = ValidateContext(
        source=args.source,
        run_id=args.run_id,
        staging_run_id=args.staging_run_id,
        paths=paths,
        fail_fast=args.fail_fast,
    )
    manifest = run_validate(ctx)
    print(json.dumps(manifest["output"], indent=2))
