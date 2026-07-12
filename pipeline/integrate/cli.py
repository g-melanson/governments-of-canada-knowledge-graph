"""CLI for Stage 4 integrate."""

from __future__ import annotations

import argparse
import json
import logging
from datetime import datetime, timezone
from pathlib import Path

from pipeline.integrate.context import IntegrateContext, SilverInput
from pipeline.integrate.runner import run_integrate
from pipeline.paths import UniversePaths


def _default_run_id() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H%M%SZ")


def _parse_input(token: str) -> SilverInput:
    # Format: source:silver_run_id  (e.g. commons_members:2026-06-24T172758Z)
    source, _, run_id = token.partition(":")
    if not source or not run_id:
        raise argparse.ArgumentTypeError(
            f"--input must be 'source:silver_run_id', got: {token!r}"
        )
    return SilverInput(source=source, silver_run_id=run_id)


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    parser = argparse.ArgumentParser(prog="integrate")
    sub = parser.add_subparsers(dest="command", required=True)

    run_p = sub.add_parser("run", help="Merge Silver fragments → universe/4-merged/")
    run_p.add_argument(
        "--input", action="append", required=True, type=_parse_input,
        metavar="SOURCE:SILVER_RUN_ID",
        help="A Silver run to merge; repeatable.",
    )
    run_p.add_argument("--run-id", default=_default_run_id())
    run_p.add_argument(
        "--universe-root",
        type=Path,
        default=Path("universe"),
        help="Root of runtime output tree (see universe/README.md)",
    )
    run_p.add_argument(
        "--resolver", default="integrate.resolvers.identity.get_resolver",
        help="Dotted path to an EntityResolver factory.",
    )
    run_p.add_argument(
        "--members-bronze",
        type=Path,
        default=None,
        help="Members Bronze records.jsonl for commons_person resolver.",
    )
    run_p.add_argument(
        "--expenditures-bronze",
        type=Path,
        default=None,
        help="Expenditures Bronze records.jsonl for commons_person resolver.",
    )
    run_p.add_argument(
        "--person-crosswalk-tsv",
        type=Path,
        default=None,
        help="Pre-built uuid→person_id TSV for commons_person resolver.",
    )

    args = parser.parse_args()
    ctx = IntegrateContext(
        run_id=args.run_id,
        inputs=tuple(args.input),
        paths=UniversePaths(root=args.universe_root),
        resolver=args.resolver,
        members_bronze_path=args.members_bronze,
        expenditures_bronze_path=args.expenditures_bronze,
        person_crosswalk_tsv=args.person_crosswalk_tsv,
    )
    manifest = run_integrate(ctx)
    print(json.dumps(manifest["output"], indent=2))
