"""Immutable per-run settings: staging paths, fetch policy, and adapter flags."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Literal

from pipeline.paths import REPO_ROOT, UniversePaths

FetchPolicy = Literal["default", "refresh", "cache-only", "local-file"]


@dataclass(frozen=True)
class RunContext:
    source: str
    run_id: str
    paths: UniversePaths = field(default_factory=UniversePaths)
    fetch_policy: FetchPolicy = "default"
    input_path: Path | None = None

    @property
    def run_dir(self) -> Path:
        return self.paths.staging_run_dir(self.source, self.run_id)

    @property
    def raw_dir(self) -> Path:
        return self.paths.staging_raw_dir(self.source, self.run_id)

    @property
    def records_path(self) -> Path:
        return self.paths.staging_records(self.source, self.run_id)

    @property
    def manifest_path(self) -> Path:
        return self.paths.staging_manifest(self.source, self.run_id)

    @property
    def cache_dir(self) -> Path:
        return self.paths.source_cache_dir(self.source)

    @property
    def source_dir(self) -> Path:
        return REPO_ROOT / "sources" / self.source

    @property
    def schema_path(self) -> Path:
        return self.source_dir / f"{self.source}.schema.yaml"
