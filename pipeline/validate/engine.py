"""LinkML validation engine — pure, streaming, reusable by validate and publish stages.

Two public APIs
---------------
validate_records(path, schema_path, target_class, *, fail_fast)
    Batch API: reads a JSONL file, returns (list[RecordOutcome], ValidationSummary).
    Loads all outcomes into memory.  Use for tests, CI drift checks, ad-hoc tooling.

run_validation(io, profile)
    Streaming production API: reads input JSONL line-by-line, writes accepted records
    to io.accepted_path and rejected records (with error detail) to io.quarantine_path.
    Caller is responsible for mkdir and manifest writing.
    Returns ValidationSummary.

Dispatch contract
-----------------
ValidationProfile.dispatch_key is read from each record to determine the LinkML
target class per-record.

  Bronze tier (_row_class):  internal routing key added by ingest adapters.
      strip_dispatch_key=True  — key is removed from the payload before validation
                                 and does NOT appear in quarantine output.
  Gold tier (@type):          semantic RDF field that belongs in the schema.
      strip_dispatch_key=False — key is kept in the payload; LinkML validates it as
                                 part of the record.

Both tiers strip PROVENANCE_KEYS (lineage metadata) before validation so the
validator does not flag them as unknown slots under a closed schema.
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Iterator

from linkml.validator import Validator
from linkml.validator.plugins import JsonschemaValidationPlugin
from linkml.validator.report import Severity

log = logging.getLogger(__name__)
logging.getLogger("linkml").setLevel(logging.ERROR)

# Lineage/provenance keys injected by pipeline stages — strip before schema validation.
PROVENANCE_KEYS: frozenset[str] = frozenset(
    {"bronze_references", "sources", "labels", "bronze_reference"}
)


# ── Data types ─────────────────────────────────────────────────────────────────


@dataclass(frozen=True)
class ValidationProfile:
    """Schema config and per-record dispatch rules for a single validation pass.

    Fields
    ------
    schema_path       : Path to the LinkML YAML schema.
    target_class      : Default class used when dispatch_key is absent from a record.
    strip_keys        : Keys stripped from the payload before validation (provenance).
    dispatch_key      : Record key used to determine target class per-record.
    strip_dispatch_key: If True, dispatch_key is also stripped from the validation
                        payload.  Set False when dispatch_key is a real schema field.
    fail_fast         : Stop after the first rejected record.
    plugins           : LinkML validation plugins tuple.
    """

    schema_path: Path
    target_class: str
    strip_keys: frozenset[str] = field(default_factory=frozenset)
    dispatch_key: str = "_row_class"
    strip_dispatch_key: bool = True
    fail_fast: bool = False
    plugins: tuple = field(
        default_factory=lambda: (JsonschemaValidationPlugin(closed=True),)
    )

    @classmethod
    def for_bronze(cls, source: str, *, fail_fast: bool = False) -> "ValidationProfile":
        """Build profile for the validate stage (staging → bronze).

        Reads schema config from pipeline/validate/config/schemas.yaml.
        """
        from pipeline.validate.config import get_schema_config  # local import avoids circular dep

        cfg = get_schema_config(source)
        return cls(
            schema_path=cfg["schema_path"],
            target_class=cfg["target_class"],
            strip_keys=PROVENANCE_KEYS,
            dispatch_key="_row_class",
            strip_dispatch_key=True,
            fail_fast=fail_fast,
        )

    @classmethod
    def for_gold(
        cls,
        schema_path: Path,
        *,
        target_class: str = "Thing",
        fail_fast: bool = False,
    ) -> "ValidationProfile":
        """Build profile for the publish stage (merged → gold).

        @type is a semantic field retained in the validated payload; open schema
        is used because graph records are expected to carry richer type hierarchies.
        """
        return cls(
            schema_path=schema_path,
            target_class=target_class,
            strip_keys=PROVENANCE_KEYS,
            dispatch_key="@type",
            strip_dispatch_key=False,
            fail_fast=fail_fast,
            plugins=(JsonschemaValidationPlugin(closed=False),),
        )


@dataclass(frozen=True)
class ValidationIO:
    """File paths for a single streaming validation pass.

    The caller creates parent directories before calling run_validation().
    """

    input_path: Path
    accepted_path: Path
    quarantine_path: Path


@dataclass
class ValidationSummary:
    input_record_count: int = 0
    accepted_count: int = 0
    rejected_count: int = 0
    error_counts: dict[str, int] = field(default_factory=dict)


@dataclass
class RecordOutcome:
    record: dict[str, Any]
    accepted: bool
    errors: list[dict[str, Any]] = field(default_factory=list)


# ── I/O utilities ──────────────────────────────────────────────────────────────


def iter_staging_records(path: Path) -> Iterator[dict[str, Any]]:
    """Yield parsed dicts from a JSONL file, skipping blank lines.

    Raises StagingInputError (not FileNotFoundError) so callers see a
    pipeline-domain exception rather than a raw OS error.
    """
    if not path.exists():
        from pipeline.validate.errors import StagingInputError

        raise StagingInputError(f"Records file not found: {path}")
    with path.open(encoding="utf-8") as fin:
        for line in fin:
            line = line.strip()
            if line:
                yield json.loads(line)


# ── Core validation logic ───────────────────────────────────────────────────────


def _make_validator(profile: ValidationProfile) -> Validator:
    return Validator(str(profile.schema_path), validation_plugins=list(profile.plugins))


def _extract_errors(report) -> list[dict[str, Any]]:
    return [
        {
            "message": r.message,
            "severity": r.severity.name if r.severity else "ERROR",
            "slot": getattr(r, "instantiates", None) or getattr(r, "source", None),
        }
        for r in report.results
        if r.severity in (Severity.ERROR, Severity.FATAL) or r.severity is None
    ]


def _prepare_payload(
    record: dict[str, Any], profile: ValidationProfile
) -> tuple[str, dict[str, Any]]:
    """Return (target_class, stripped_payload) ready for the LinkML validator.

    Strips provenance keys and, when strip_dispatch_key is True, also strips the
    dispatch key itself.  The original record object is never mutated.
    """
    record_class: str = record.get(profile.dispatch_key) or profile.target_class
    keys_to_strip = profile.strip_keys
    if profile.strip_dispatch_key:
        keys_to_strip = keys_to_strip | {profile.dispatch_key}
    payload = {k: v for k, v in record.items() if k not in keys_to_strip}
    return record_class, payload


def validate_record(
    record: dict[str, Any],
    profile: ValidationProfile,
    validator: Validator,
) -> RecordOutcome:
    """Validate a single record; return RecordOutcome with accepted flag and any errors."""
    record_class, payload = _prepare_payload(record, profile)
    report = validator.validate(payload, target_class=record_class)
    errors = _extract_errors(report)
    return RecordOutcome(record=record, accepted=not errors, errors=errors)


# ── Public APIs ────────────────────────────────────────────────────────────────


def validate_records(
    path: Path,
    schema_path: Path,
    target_class: str,
    *,
    fail_fast: bool = False,
) -> tuple[list[RecordOutcome], ValidationSummary]:
    """Batch API: validate all records in a JSONL file, return (outcomes, summary).

    Loads all outcomes into memory.
    Use run_validation() for production streaming over large files.
    """
    profile = ValidationProfile(
        schema_path=schema_path,
        target_class=target_class,
        fail_fast=fail_fast,
    )
    validator = _make_validator(profile)
    summary = ValidationSummary()
    results: list[RecordOutcome] = []

    for record in iter_staging_records(path):
        summary.input_record_count += 1
        outcome = validate_record(record, profile, validator)
        results.append(outcome)
        if outcome.accepted:
            summary.accepted_count += 1
        else:
            summary.rejected_count += 1
            for err in outcome.errors:
                key = str(
                    err.get("slot") or err.get("message") or "unknown"
                )
                summary.error_counts[key] = summary.error_counts.get(key, 0) + 1
            if fail_fast:
                break

    return results, summary


def run_validation(io: ValidationIO, profile: ValidationProfile) -> ValidationSummary:
    """Streaming production API.

    Reads io.input_path line-by-line.  Writes accepted records (original payload)
    to io.accepted_path and rejected records with error detail to io.quarantine_path.

    The caller is responsible for:
      - creating parent directories before calling this function
      - writing stage manifests after this function returns

    Respects profile.fail_fast: stops after the first rejected record.
    """
    validator = _make_validator(profile)
    summary = ValidationSummary()

    with io.accepted_path.open("w", encoding="utf-8") as accepted:
        with io.quarantine_path.open("w", encoding="utf-8") as quarantine:
            for record in iter_staging_records(io.input_path):
                summary.input_record_count += 1
                outcome = validate_record(record, profile, validator)

                if outcome.accepted:
                    summary.accepted_count += 1
                    accepted.write(
                        json.dumps(outcome.record, ensure_ascii=False) + "\n"
                    )
                else:
                    summary.rejected_count += 1
                    for err in outcome.errors:
                        key = str(
                            err.get("slot") or err.get("message") or "unknown"
                        )
                        summary.error_counts[key] = (
                            summary.error_counts.get(key, 0) + 1
                        )
                    quarantine.write(
                        json.dumps(
                            {"record": outcome.record, "errors": outcome.errors},
                            ensure_ascii=False,
                        )
                        + "\n"
                    )

                if profile.fail_fast and not outcome.accepted:
                    break

    return summary
