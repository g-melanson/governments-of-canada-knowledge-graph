
import json
import pytest

from validate.runner import run_validate
from validate.errors import EmptyBronzeError
from validate.tests.conftest import (
    valid_row,
    row_missing_id_key,
    row_has_null_id_value,
    row_has_bad_datetime_value,
    row_has_extra_field,
    rows_to_jsonl,
    write_staging,
)

def test_run_validate_writes_bronze(write_staging_dir, validate_context):
    write_staging_dir(
        "commons_members",
        "test-run",
        rows_to_jsonl(valid_row()),
    )
    ctx = validate_context(staging_run_id="test-run", run_id="validate-run")
    manifest = run_validate(ctx)
    assert manifest["tier"] == "bronze"
    assert ctx.bronze_manifest_path.exists()

def test_all_restricted_records_rejected_raises_empty_bronze_error(write_staging_dir, validate_context):
    write_staging_dir(
        "commons_members",
        "test-run",
        rows_to_jsonl(row_missing_id_key(), row_has_null_id_value(), row_has_bad_datetime_value(), row_has_extra_field()),
    )
    ctx = validate_context(staging_run_id="test-run", run_id="validate-run")
    with pytest.raises(EmptyBronzeError):
        run_validate(ctx)

def test_run_validate_handles_multiple_records(write_staging_dir, validate_context):
    write_staging_dir(
        "commons_members",
        "test-run",
        rows_to_jsonl(valid_row(), valid_row()),
    )
    ctx = validate_context(staging_run_id="test-run", run_id="validate-run")
    manifest = run_validate(ctx)
    assert manifest["output"]["record_count"] == 2

def test_run_validate_differentiates_invalid_records(write_staging_dir, validate_context):
    write_staging_dir(
        "commons_members",
        "test-run",
        rows_to_jsonl(valid_row(), row_missing_id_key(), valid_row()),    
    )
    ctx = validate_context(staging_run_id="test-run", run_id="validate-run")
    manifest = run_validate(ctx)
    assert manifest["output"]["record_count"] == 2
    assert manifest["output"]["rejected_count"] == 1

def test_run_validate_writes_drift_report(write_staging_dir, validate_context):
    write_staging_dir(
        "commons_members",
        "test-run",
        rows_to_jsonl(valid_row(), row_missing_id_key(), valid_row()),    
    )
    ctx = validate_context(staging_run_id="test-run", run_id="validate-run")
    manifest = run_validate(ctx)

    contents = ctx.drift_report_path.read_text(encoding="utf-8")
    drift_report = json.loads(contents)

    assert drift_report["run_id"] == "validate-run"
    assert drift_report["source"] == "commons_members"
    assert drift_report["input_record_count"] == 3
    assert drift_report["accepted_count"] == 2
    assert drift_report["rejected_count"] == 1



