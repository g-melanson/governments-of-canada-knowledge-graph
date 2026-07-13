"""Immutable per-run settings for Stage 2 validate."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from pipeline.paths import UniversePaths


@dataclass(frozen=True)
class ValidateContext:
    source: str
    run_id: str
    staging_run_id: str | None = None
    paths: UniversePaths = field(default_factory=UniversePaths)
    fail_fast: bool = False

    @property
    def effective_staging_run_id(self) -> str:
        return self.staging_run_id or self.run_id

    @property
    def staging_run_dir(self) -> Path:
        return self.paths.staging_run_dir(self.source, self.effective_staging_run_id)

    @property
    def staging_records_path(self) -> Path:
        return self.paths.staging_records(self.source, self.effective_staging_run_id)

    @property
    def staging_manifest_path(self) -> Path:
        return self.paths.staging_manifest(self.source, self.effective_staging_run_id)

    @property
    def bronze_run_dir(self) -> Path:
        return self.paths.bronze_run_dir(self.source, self.run_id)

    @property
    def bronze_records_path(self) -> Path:
        return self.paths.bronze_records(self.source, self.run_id)

    @property
    def bronze_manifest_path(self) -> Path:
        return self.paths.bronze_manifest(self.source, self.run_id)

    @property
    def quarantine_run_dir(self) -> Path:
        return self.paths.validate_quarantine_run_dir(self.source, self.run_id)

    @property
    def rejects_path(self) -> Path:
        return self.paths.validate_quarantine_rejects(self.source, self.run_id)

    @property
    def drift_report_path(self) -> Path:
        return self.paths.validate_quarantine_drift_report(self.source, self.run_id)
