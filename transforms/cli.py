import argparse

import json
import logging
from datetime import datetime, timezone
from pathlib import Path

from transforms.context import TransformContext
from transforms.runner import run_transform

def _default_run_id() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H%M%SZ")


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    parser = argparse.ArgumentParser(prog="validate")
    sub = parser.add_subparsers(dest="command", required=True)

    run_p = sub.add_parser("run", help="Transform Bronze records → Silver")
    run_p.add_argument("--source", required=True)
    run_p.add_argument("--bronze-run-id", required=True)
    run_p.add_argument("--run-id", default=_default_run_id())
    run_p.add_argument("--bronze-root", type=Path, default=Path("bronze"))
    run_p.add_argument("--silver-root", type=Path, default=Path("silver"))

    args = parser.parse_args()
    ctx = TransformContext(
        source=args.source,
        run_id=args.run_id,
        bronze_run_id=args.bronze_run_id,
        bronze_root=args.bronze_root,
        silver_root=args.silver_root,
    )
    manifest = run_transform(ctx)
    print(json.dumps(manifest["output"], indent=2))