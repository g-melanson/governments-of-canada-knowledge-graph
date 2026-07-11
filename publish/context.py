from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent


@dataclass(frozen=True)
class PublishContext:
    run_id: str
    merged_run_id: str
    silver_root: Path = Path("silver")
    gold_root: Path = Path("gold")

    @property
    def domain_schema_path(self) -> Path:
        return BASE_DIR / "domain_model" / "schema.yaml"

    @property
    def silver_dir(self) -> Path:
        return BASE_DIR / self.silver_root 

    @property
    def merged_dir(self) -> Path:
        return self.silver_dir / "merged" / self.merged_run_id

    @property
    def merged_manifest_path(self) -> Path:
        return self.merged_dir / "manifest.json"

    @property
    def merged_nodes_path(self) -> Path:
        return self.merged_dir / "nodes.jsonl"

    @property
    def merged_edges_path(self) -> Path:
        return self.merged_dir / "edges.jsonl"

    @property
    def gold_dir(self) -> Path:
        return BASE_DIR / self.gold_root / self.run_id

    @property
    def gold_nodes_path(self) -> Path:
        return self.gold_dir / "nodes.jsonl"

    @property
    def gold_edges_path(self) -> Path:
        return self.gold_dir / "edges.jsonl"

    @property
    def gold_manifest_path(self) -> Path:
        return self.gold_dir / "manifest.json"

    @property
    def quarantine_dir(self) -> Path:
        return self.gold_dir / "quarantine"

    @property
    def quarantine_nodes_path(self) -> Path:
        return self.quarantine_dir / "nodes.jsonl"

    @property
    def quarantine_edges_path(self) -> Path:
        return self.quarantine_dir / "edges.jsonl"
