"""Immutable per-run settings for Stage 2 validate."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class ValidateContext:
    source: str
    run_id: str
    staging_run_id: str
    staging_root: Path = Path("staging")
    bronze_root: Path = Path("bronze")
    quarantine_root: Path = Path("quarantine")
    fail_fast: bool = False

    @property
    def staging_run_dir(self) -> Path:
        return self.staging_root / self.source / self.staging_run_id

    @property
    def staging_records_path(self) -> Path:
        return self.staging_run_dir / "records.jsonl"

    @property
    def staging_manifest_path(self) -> Path:
        return self.staging_run_dir / "manifest.json"

    @property
    def bronze_run_dir(self) -> Path:
        return self.bronze_root / self.source / self.run_id

    @property
    def bronze_records_path(self) -> Path:
        return self.bronze_run_dir / "records.jsonl"

    @property
    def bronze_manifest_path(self) -> Path:
        return self.bronze_run_dir / "manifest.json"

    @property
    def quarantine_run_dir(self) -> Path:
        return self.quarantine_root / self.source / self.run_id

    @property
    def rejects_path(self) -> Path:
        return self.quarantine_run_dir / "rejects.jsonl"

    @property
    def drift_report_path(self) -> Path:
        return self.quarantine_run_dir / "drift_report.json"
        