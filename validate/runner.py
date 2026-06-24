"""Orchestrate LinkML validation and Bronze/quarantine output."""

from __future__ import annotations

import json
import logging
from datetime import datetime, timezone

from validate.config import get_schema_config
from validate.context import ValidateContext
from validate.engine import validate_records
from validate.errors import EmptyBronzeError, StagingInputError, ValidationFailedError

log = logging.getLogger(__name__)


def run_validate(ctx: ValidateContext) -> dict:
    schema_cfg = get_schema_config(ctx.source)
    if not ctx.staging_manifest_path.exists():
        raise StagingInputError(f"Staging manifest not found: {ctx.staging_manifest_path}")

    staging_manifest = json.loads(ctx.staging_manifest_path.read_text(encoding="utf-8"))
    ctx.bronze_run_dir.mkdir(parents=True, exist_ok=True)
    ctx.quarantine_run_dir.mkdir(parents=True, exist_ok=True)

    started_at = datetime.now(timezone.utc)
    outcomes, summary = validate_records(
        ctx.staging_records_path,
        schema_cfg["schema_path"],
        schema_cfg["target_class"],
        fail_fast=ctx.fail_fast,
    )

    if summary.accepted_count == 0:
        raise EmptyBronzeError(f"{ctx.source}: all records rejected")

    with ctx.bronze_records_path.open("w", encoding="utf-8") as bout:
        with ctx.rejects_path.open("w", encoding="utf-8") as qout:
            for outcome in outcomes:
                if outcome.accepted:
                    bout.write(json.dumps(outcome.record, ensure_ascii=False) + "\n")
                else:
                    qout.write(
                        json.dumps(
                            {
                                "line": outcome.line_number,
                                "record": outcome.record,
                                "errors": outcome.errors,
                            },
                            ensure_ascii=False,
                        )
                        + "\n"
                    )

    finished_at = datetime.now(timezone.utc)
    drift_report = {
        "run_id": ctx.run_id,
        "source": ctx.source,
        "staging_run_id": ctx.staging_run_id,
        "started_at": started_at.isoformat(),
        "finished_at": finished_at.isoformat(),
        "schema_path": str(schema_cfg["schema_path"].relative_to(schema_cfg["schema_path"].parents[2])
                         if schema_cfg["schema_path"].is_absolute() else schema_cfg["schema_path"]),
        "target_class": schema_cfg["target_class"],
        "input_record_count": summary.input_record_count,
        "accepted_count": summary.accepted_count,
        "rejected_count": summary.rejected_count,
        "error_counts": summary.error_counts,
        "fail_fast": ctx.fail_fast,
    }
    ctx.drift_report_path.write_text(json.dumps(drift_report, indent=2), encoding="utf-8")

    bronze_manifest = {
        "run_id": ctx.run_id,
        "source": ctx.source,
        "stage": "validate",
        "tier": "bronze",
        "started_at": started_at.isoformat(),
        "finished_at": finished_at.isoformat(),
        "status": "success",
        "inputs": [
            {
                "staging_run_id": ctx.staging_run_id,
                "staging_manifest": json.loads(ctx.staging_manifest_path.read_text(encoding="utf-8")),
            }
        ],
        "output": {
            "records_path": str(ctx.bronze_records_path),
            "record_count": summary.accepted_count,
            "rejected_count": summary.rejected_count,
            "drift_report_path": str(ctx.drift_report_path),
        },
    }
    ctx.bronze_manifest_path.write_text(json.dumps(bronze_manifest, indent=2), encoding="utf-8")

    if ctx.fail_fast and summary.rejected_count > 0:
        raise ValidationFailedError(f"{ctx.source}: validation failed under --fail-fast")

    log.info(
        "validate_complete",
        extra={
            "source": ctx.source,
            "run_id": ctx.run_id,
            "accepted": summary.accepted_count,
            "rejected": summary.rejected_count,
        },
    )
    return bronze_manifest
    