"""Orchestrate Stage 2 validation: Bronze record output + quarantine + manifests.

This module owns the pipeline orchestration layer:
  - guards (staging input must exist)
  - directory creation
  - calling the pure engine (run_validation)
  - writing drift_report.json and bronze manifest.json
  - raising EmptyBronzeError when all records are rejected

The engine itself (pipeline/validate/engine.py) is context-free and reusable
by any stage that needs LinkML validation.
"""

from __future__ import annotations

import json
import logging
from datetime import datetime, timezone

from pipeline.validate.context import ValidateContext
from pipeline.validate.engine import ValidationIO, ValidationProfile, run_validation
from pipeline.validate.errors import EmptyBronzeError, StagingInputError

log = logging.getLogger(__name__)


# ── Context adapters ───────────────────────────────────────────────────────────


def io_from_ctx(ctx: ValidateContext) -> ValidationIO:
    """Derive ValidationIO (path bundle) from a ValidateContext."""
    return ValidationIO(
        input_path=ctx.staging_records_path,
        accepted_path=ctx.bronze_records_path,
        quarantine_path=ctx.rejects_path,
    )


def profile_from_ctx(ctx: ValidateContext) -> ValidationProfile:
    """Derive ValidationProfile (schema config) from a ValidateContext."""
    return ValidationProfile.for_bronze(ctx.source, fail_fast=ctx.fail_fast)


# ── Orchestration ──────────────────────────────────────────────────────────────


def run_validate(ctx: ValidateContext) -> dict:
    """Run the validate stage and return the bronze manifest dict.

    Writes:
      - bronze records.jsonl         (accepted records)
      - quarantine/rejects.jsonl     (rejected records with error detail)
      - quarantine/drift_report.json (schema drift metrics)
      - bronze manifest.json         (stage manifest, returned to caller)

    Raises:
      StagingInputError  if the staging manifest is missing.
      EmptyBronzeError   if every input record is rejected.
    """
    if not ctx.staging_manifest_path.exists():
        raise StagingInputError(
            f"Staging manifest not found: {ctx.staging_manifest_path}"
        )

    ctx.bronze_run_dir.mkdir(parents=True, exist_ok=True)
    ctx.quarantine_run_dir.mkdir(parents=True, exist_ok=True)

    io = io_from_ctx(ctx)
    profile = profile_from_ctx(ctx)

    started_at = datetime.now(timezone.utc)
    summary = run_validation(io, profile)
    finished_at = datetime.now(timezone.utc)

    if summary.accepted_count == 0:
        raise EmptyBronzeError(
            f"All {summary.input_record_count} records rejected for source '{ctx.source}' "
            f"— Bronze would be empty."
        )

    # Relative schema path for portability in reports.
    rel_schema = (
        profile.schema_path.relative_to(profile.schema_path.parents[2])
        if profile.schema_path.is_absolute()
        else profile.schema_path
    )

    drift_report = {
        "run_id": ctx.run_id,
        "source": ctx.source,
        "staging_run_id": ctx.effective_staging_run_id,
        "started_at": started_at.isoformat(),
        "finished_at": finished_at.isoformat(),
        "schema_path": str(rel_schema),
        "target_class": profile.target_class,
        "input_record_count": summary.input_record_count,
        "accepted_count": summary.accepted_count,
        "rejected_count": summary.rejected_count,
    }
    ctx.drift_report_path.write_text(
        json.dumps(drift_report, indent=2), encoding="utf-8"
    )

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
                "staging_run_id": ctx.effective_staging_run_id,
                "staging_manifest": json.loads(
                    ctx.staging_manifest_path.read_text(encoding="utf-8")
                ),
            }
        ],
        "output": {
            "records_path": str(ctx.bronze_records_path),
            "record_count": summary.accepted_count,
            "rejected_count": summary.rejected_count,
            "drift_report_path": str(ctx.drift_report_path),
        },
    }
    ctx.bronze_manifest_path.write_text(
        json.dumps(bronze_manifest, indent=2), encoding="utf-8"
    )

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
