"""Orchestrate LinkML validation and Bronze/quarantine output."""

from __future__ import annotations

import json
import logging
from pathlib import Path
from datetime import datetime, timezone
from dataclasses import dataclass
from typing import Iterator, Any

from linkml.validator import Validator
from linkml.validator.plugins import JsonschemaValidationPlugin

from pipeline.validate.config import get_schema_config
from pipeline.validate.context import ValidateContext
from pipeline.validate.engine import validate_record
from pipeline.validate.errors import (
    StagingInputError, 
    ValidationFailedError
    )

log = logging.getLogger(__name__)


@dataclass
class ValidationSummary:
    input_record_count: int = 0
    accepted_count: int = 0
    rejected_count: int = 0


def iter_staging_records(path: Path) -> Iterator[tuple[int, dict[str, Any]]]:
    if not path.exists():
        raise StagingInputError(f"Staging records not found: {path}")
    with path.open(encoding="utf-8") as fin:
        for line_number, line in enumerate(fin, start=1):
            line = line.strip()
            if not line:
                continue
            yield json.loads(line)


def run_validate(ctx: ValidateContext) -> dict:
    schema_cfg = get_schema_config(ctx.source)
    if not ctx.staging_manifest_path.exists():
        raise StagingInputError(f"Staging manifest not found: {ctx.staging_manifest_path}")

    validator = Validator(
        str(schema_cfg["schema_path"]),
        validation_plugins=[JsonschemaValidationPlugin(closed=True)],
    )
    summary = ValidationSummary()

    ctx.bronze_run_dir.mkdir(parents=True, exist_ok=True)
    ctx.quarantine_run_dir.mkdir(parents=True, exist_ok=True)

    started_at = datetime.now(timezone.utc)

    with ctx.bronze_records_path.open("w", encoding="utf-8") as bout:
        with ctx.rejects_path.open("w", encoding="utf-8") as qout:

            for record in iter_staging_records(ctx.staging_records_path):
                summary.input_record_count += 1
                outcome = validate_record(
                    record=record,
                    target_class=schema_cfg["target_class"],
                    validator=validator
                )

                if outcome.accepted:
                    summary.accepted_count += 1
                    bout.write(json.dumps(outcome.record, ensure_ascii=False) + "\n")
                else:
                    summary.rejected_count += 1
                    qout.write(
                        json.dumps(
                            {
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
        "staging_run_id": ctx.effective_staging_run_id,
        "started_at": started_at.isoformat(),
        "finished_at": finished_at.isoformat(),
        "schema_path": str(schema_cfg["schema_path"].relative_to(schema_cfg["schema_path"].parents[2])
                         if schema_cfg["schema_path"].is_absolute() else schema_cfg["schema_path"]),
        "target_class": schema_cfg["target_class"],
        "input_record_count": summary.input_record_count,
        "accepted_count": summary.accepted_count,
        "rejected_count": summary.rejected_count,
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
                "staging_run_id": ctx.effective_staging_run_id,
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
    