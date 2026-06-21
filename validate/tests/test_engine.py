from validate.engine import (
    validate_records,
    iter_staging_records,
)
from validate.tests.conftest import (
    valid_row,
    row_missing_id_key,
    row_has_null_id_value,
    row_has_bad_datetime_value,
    row_has_extra_field,
    rows_to_jsonl,
    SCHEMA_PATH,
    TARGET_CLASS,
)

def test_valid_single_row_accepted(make_records_file):
    rows = rows_to_jsonl(valid_row())
    records_file = make_records_file(rows)
    results, summary = validate_records(records_file, SCHEMA_PATH, TARGET_CLASS)
    assert len(results) == 1
    assert summary.accepted_count == 1
    assert summary.rejected_count == 0
    assert results[0].accepted
    assert results[0].errors == []

def test_valid_multiple_rows_accepted(make_records_file):
    rows = rows_to_jsonl(valid_row(), valid_row(), valid_row())
    records_file = make_records_file(rows)
    results, summary = validate_records(records_file, SCHEMA_PATH, TARGET_CLASS)
    assert len(results) == 3
    assert summary.accepted_count == 3
    assert summary.rejected_count == 0
    assert all(result.accepted for result in results)
    assert all(result.errors == [] for result in results)

def test_rejects_missing_person_id_key(make_records_file):
    rows = rows_to_jsonl(row_missing_id_key())
    records_file = make_records_file(rows)
    results, summary = validate_records(records_file, SCHEMA_PATH, TARGET_CLASS)
    assert len(results) == 1
    assert summary.accepted_count == 0
    assert summary.rejected_count == 1
    assert not results[0].accepted

def test_rejects_missing_person_id_value(make_records_file):
    rows = rows_to_jsonl(row_has_null_id_value())
    records_file = make_records_file(rows)
    results, summary = validate_records(records_file, SCHEMA_PATH, TARGET_CLASS)
    assert len(results) == 1
    assert summary.accepted_count == 0
    assert summary.rejected_count == 1
    assert not results[0].accepted

def test_rejects_bad_datetime_value(make_records_file):
    rows = rows_to_jsonl(row_has_bad_datetime_value())
    records_file = make_records_file(rows)
    results, summary = validate_records(records_file, SCHEMA_PATH, TARGET_CLASS)
    assert len(results) == 1
    assert summary.accepted_count == 0
    assert summary.rejected_count == 1
    assert not results[0].accepted

def test_rejects_extra_field(make_records_file):
    rows = rows_to_jsonl(row_has_extra_field())
    records_file = make_records_file(rows)
    results, summary = validate_records(records_file, SCHEMA_PATH, TARGET_CLASS)
    assert len(results) == 1
    assert summary.accepted_count == 0
    assert summary.rejected_count == 1
    assert not results[0].accepted

def test_fail_fast_stops_after_first_reject(make_records_file):
    rows = rows_to_jsonl(valid_row(), row_missing_id_key(), valid_row())
    records_file = make_records_file(rows)
    results, summary = validate_records(records_file, SCHEMA_PATH, TARGET_CLASS, fail_fast=True)
    assert len(results) == 2
    assert summary.accepted_count == 1
    assert summary.rejected_count == 1
    assert results[0].accepted
    assert not results[1].accepted

def test_fail_fast_false_processes_all(make_records_file):
    rows = rows_to_jsonl(valid_row(), row_missing_id_key(), valid_row())
    records_file = make_records_file(rows)
    results, summary = validate_records(records_file, SCHEMA_PATH, TARGET_CLASS, fail_fast=False)
    assert len(results) == 3
    assert summary.accepted_count == 2
    assert summary.rejected_count == 1
    assert results[0].accepted
    assert not results[1].accepted


