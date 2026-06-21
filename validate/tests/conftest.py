import pytest

import json
from pathlib import Path
from typing import Any
from types import SimpleNamespace

from validate.context import ValidateContext

SCHEMA_PATH = Path(__file__).resolve().parents[2] / "source/commons_members.schema.yaml"

TARGET_CLASS = "CommonsMembersRow"

@pytest.fixture
def schema_file(tmp_path):
    path = tmp_path / "schema.yaml"
    path.write_text("schema")
    return path

@pytest.fixture
def make_records_file(tmp_path):
    def _make(content: str):
        path = tmp_path / "records.jsonl"
        path.write_text(content)
        return path

    return _make

def valid_row():
    return {
            "person_id": "1",
            "person_short_honorific": "Mr.",
            "person_official_first_name": "John",
            "person_official_last_name": "Doe",
            "constituency_name": "Toronto",
            "constituency_province_territory_name": "Ontario",
            "caucus_short_name": "Liberal",
            "from_date_time": "2021-01-01T00:00:00Z",
            "to_date_time": "2025-12-31T23:59:59Z",
    }

def row_missing_id_key():
    row = valid_row()
    del row["person_id"]
    return row

def row_has_null_id_value():
    row = valid_row()
    row["person_id"] = None
    return row

def row_has_bad_datetime_value():
    row = valid_row()
    row["from_date_time"] = "not-a-date"
    return row

def row_has_extra_field():
    row = valid_row()
    row["extra_field"] = "extra-value"
    return row

def rows_to_jsonl(*rows: dict[str, Any]) -> str:
    return "\n".join(json.dumps(row) for row in rows) + "\n"

@pytest.fixture
def write_staging_dir(tmp_path):
    staging_root = tmp_path / "staging"
    def _write(source, staging_run_id, records_jsonl, **kwargs):
        return write_staging(staging_root, source, staging_run_id, records_jsonl, **kwargs)
    return _write

def write_staging(
    staging_root: Path,
    source: str,
    staging_run_id: str,
    records_jsonl: str,
    *,
    manifest: dict[str, Any] | None = None,
) -> Path:
    """Create staging/{source}/{staging_run_id}/records.jsonl + manifest.json."""
    run_dir = staging_root / source / staging_run_id
    run_dir.mkdir(parents=True, exist_ok=True)
    (run_dir / "records.jsonl").write_text(records_jsonl, encoding="utf-8")
    if manifest is None:
        manifest = {
            "run_id": staging_run_id,
            "source": source,
            "status": "success",
            "output": {"record_count": records_jsonl.count("\n") - (1 if records_jsonl.endswith("\n") else 0)},
        }
    (run_dir / "manifest.json").write_text(
        json.dumps(manifest, indent=2), encoding="utf-8"
    )
    return run_dir

def make_validate_context(
    tmp_path: Path,
    *,
    source: str = "commons_members",
    staging_run_id: str = "test-run",
    run_id: str = "validate-run",
    fail_fast: bool = False,
) -> ValidateContext:
    return ValidateContext(
        source=source,
        run_id=run_id,
        staging_run_id=staging_run_id,
        staging_root=tmp_path / "staging",
        bronze_root=tmp_path / "bronze",
        quarantine_root=tmp_path / "quarantine",
        fail_fast=fail_fast,
    )

@pytest.fixture
def validate_context(tmp_path):
    def _make(**kwargs):
        return make_validate_context(tmp_path, **kwargs)
    return _make
