"""Orchestrate Stage 5 publish → Gold."""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from linkml.validator.report import Severity

from pipeline.publish.context import PublishContext
from pipeline.publish.engine import ValidationEngine, iter_jsonl

log = logging.getLogger(__name__)


@dataclass
class ValidationOutcome:
    line_number: int
    fragment: dict[str, Any]
    accepted: bool
    errors: list[dict[str, Any]] = field(default_factory=list)


@dataclass
class PublishSummary:
    input_count: int = 0
    accepted_count: int = 0
    rejected_count: int = 0
    error_counts: dict[str, int] = field(default_factory=dict)


def _validation_errors(report) -> list[dict[str, Any]]:
    return [
        {
            "type": r.type,
            "message": r.message,
            "severity": r.severity.name if r.severity else "ERROR",
            "slot": getattr(r, "instantiates", None) or getattr(r, "source", None),
        }
        for r in report.results
        if r.severity in (Severity.ERROR, Severity.FATAL) or r.severity is None
    ]


def _validate_stream(
    path: Path,
    engine: ValidationEngine,
    summary: PublishSummary,
) -> list[ValidationOutcome]:
    outcomes: list[ValidationOutcome] = []
    for line_number, fragment in iter_jsonl(path):
        summary.input_count += 1
        report = engine.validate_fragment(fragment)
        errors = _validation_errors(report)
        accepted = len(errors) == 0
        outcomes.append(
            ValidationOutcome(
                line_number=line_number,
                fragment=fragment,
                accepted=accepted,
                errors=errors,
            )
        )
        if accepted:
            summary.accepted_count += 1
        else:
            summary.rejected_count += 1
            for err in errors:
                key = str(err.get("slot") or err.get("type") or err.get("message") or "unknown")
                summary.error_counts[key] = summary.error_counts.get(key, 0) + 1
    return outcomes


def _write_outcomes(
    outcomes: list[ValidationOutcome],
    gold_path: Path,
    quarantine_path: Path,
) -> None:
    with gold_path.open("w", encoding="utf-8") as fout, quarantine_path.open(
        "w", encoding="utf-8"
    ) as qout:
        for outcome in outcomes:
            if outcome.accepted:
                fout.write(json.dumps(outcome.fragment, ensure_ascii=False) + "\n")
            else:
                qout.write(
                    json.dumps(
                        {
                            "line_number": outcome.line_number,
                            "fragment": outcome.fragment,
                            "errors": outcome.errors,
                        },
                        ensure_ascii=False,
                    )
                    + "\n"
                )


def run_validation(
    ctx: PublishContext,
) -> tuple[PublishSummary, list[ValidationOutcome], list[ValidationOutcome]]:
    engine = ValidationEngine(ctx)
    summary = PublishSummary()
    nodes_out = _validate_stream(ctx.merged_nodes_path, engine, summary)
    edges_out = _validate_stream(ctx.merged_edges_path, engine, summary)
    return summary, nodes_out, edges_out


def run_publisher(ctx: PublishContext) -> dict:
    ctx.gold_dir.mkdir(parents=True, exist_ok=True)
    ctx.quarantine_dir.mkdir(parents=True, exist_ok=True)
    started_at = datetime.now(timezone.utc)

    summary, nodes_out, edges_out = run_validation(ctx)

    _write_outcomes(nodes_out, ctx.gold_nodes_path, ctx.quarantine_nodes_path)
    _write_outcomes(edges_out, ctx.gold_edges_path, ctx.quarantine_edges_path)

    ended_at = datetime.now(timezone.utc)
    duration_seconds = (ended_at - started_at).total_seconds()

    manifest = {
        "run_id": ctx.run_id,
        "stage": "publish",
        "tier": "gold",
        "started_at": started_at.isoformat(),
        "ended_at": ended_at.isoformat(),
        "status": "success",
        "inputs": {
            "merged_run_id": ctx.run_id,
            "merged_nodes_path": str(ctx.merged_nodes_path),
            "merged_edges_path": str(ctx.merged_edges_path),
            "domain_schema_path": str(ctx.domain_schema_path),
        },
        "output": {
            "gold_nodes_path": str(ctx.gold_nodes_path),
            "gold_edges_path": str(ctx.gold_edges_path),
            "quarantine_nodes_path": str(ctx.quarantine_nodes_path),
            "quarantine_edges_path": str(ctx.quarantine_edges_path),
            "input_count": summary.input_count,
            "accepted_count": summary.accepted_count,
            "rejected_count": summary.rejected_count,
            "error_counts": summary.error_counts,
            "duration_seconds": duration_seconds,
        },
    }

    ctx.gold_manifest_path.write_text(
        json.dumps(manifest, indent=2), encoding="utf-8"
    )
    log.info(
        "publish_complete run_id=%s accepted=%s rejected=%s",
        ctx.run_id,
        summary.accepted_count,
        summary.rejected_count,
    )
    return manifest
