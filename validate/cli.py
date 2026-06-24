
from __future__ import annotations

import argparse
import json
import logging
from datetime import datetime, timezone
from pathlib import Path

from validate.config import list_validatable_sources
from validate.context import ValidateContext
from validate.runner import run_validate


def _default_run_id() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H%M%SZ")


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    parser = argparse.ArgumentParser(prog="validate")
    sub = parser.add_subparsers(dest="command", required=True)

    run_p = sub.add_parser("run", help="Validate staging records → Bronze")
    run_p.add_argument("--source", required=True)
    run_p.add_argument("--staging-run-id", required=True, help="Stage 1 run_id under staging/")
    run_p.add_argument("--run-id", default=_default_run_id())
    run_p.add_argument("--staging-root", type=Path, default=Path("staging"))
    run_p.add_argument("--bronze-root", type=Path, default=Path("bronze"))
    run_p.add_argument("--quarantine-root", type=Path, default=Path("quarantine"))
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

    ctx = ValidateContext(
        source=args.source,
        run_id=args.run_id,
        staging_run_id=args.staging_run_id,
        staging_root=args.staging_root,
        bronze_root=args.bronze_root,
        quarantine_root=args.quarantine_root,
        fail_fast=args.fail_fast,
    )
    manifest = run_validate(ctx)
    print(json.dumps(manifest["output"], indent=2))