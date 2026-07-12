from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from pipeline.paths import REPO_ROOT, UniversePaths


@dataclass(frozen=True)
class PublishContext:
    run_id: str
    merged_run_id: str
    paths: UniversePaths = field(default_factory=UniversePaths)

    @property
    def domain_schema_path(self) -> Path:
        return REPO_ROOT / "schemas" / "schema.yaml"

    @property
    def merged_dir(self) -> Path:
        return self.paths.merged_run_dir(self.merged_run_id)

    @property
    def merged_manifest_path(self) -> Path:
        return self.paths.merged_manifest(self.merged_run_id)

    @property
    def merged_nodes_path(self) -> Path:
        return self.paths.merged_nodes(self.merged_run_id)

    @property
    def merged_edges_path(self) -> Path:
        return self.paths.merged_edges(self.merged_run_id)

    @property
    def gold_dir(self) -> Path:
        return self.paths.gold_run_dir(self.run_id)

    @property
    def gold_nodes_path(self) -> Path:
        return self.paths.gold_nodes(self.run_id)

    @property
    def gold_edges_path(self) -> Path:
        return self.paths.gold_edges(self.run_id)

    @property
    def gold_manifest_path(self) -> Path:
        return self.paths.gold_manifest(self.run_id)

    @property
    def quarantine_dir(self) -> Path:
        return self.paths.gold_quarantine_dir(self.run_id)

    @property
    def quarantine_nodes_path(self) -> Path:
        return self.paths.gold_quarantine_nodes(self.run_id)

    @property
    def quarantine_edges_path(self) -> Path:
        return self.paths.gold_quarantine_edges(self.run_id)
