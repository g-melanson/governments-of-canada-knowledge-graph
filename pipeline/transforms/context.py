from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from pipeline.paths import UniversePaths


@dataclass(frozen=True)
class TransformContext:
    source: str
    run_id: str
    bronze_run_id: str | None = None
    paths: UniversePaths = field(default_factory=UniversePaths)

    @property
    def effective_bronze_run_id(self) -> str:
        return self.bronze_run_id or self.run_id

    @property
    def bronze_dir(self) -> Path:
        return self.paths.bronze_run_dir(self.source, self.effective_bronze_run_id)

    @property
    def silver_dir(self) -> Path:
        return self.paths.silver_run_dir(self.source, self.run_id)

    @property
    def bronze_manifest_path(self) -> Path:
        return self.paths.bronze_manifest(self.source, self.effective_bronze_run_id)

    @property
    def bronze_records_path(self) -> Path:
        return self.paths.bronze_records(self.source, self.effective_bronze_run_id)

    @property
    def silver_fragments_path(self) -> Path:
        return self.paths.silver_fragments(self.source, self.run_id)

    @property
    def silver_manifest_path(self) -> Path:
        return self.paths.silver_manifest(self.source, self.run_id)

    @property
    def map_path(self) -> Path:
        return self.paths.silver_map(self.source, self.run_id)

    @property
    def quarantine_path(self) -> Path:
        return self.paths.silver_quarantine(self.source, self.run_id)
