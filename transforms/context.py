
from pathlib import Path
from dataclasses import dataclass


@dataclass(frozen=True)
class TransformContext:
    source: str
    run_id: str
    bronze_run_id: str
    bronze_root: Path = Path("bronze")
    silver_root: Path = Path("silver")

    @property
    def bronze_dir(self) -> Path:
        return self.bronze_root / self.source / self.bronze_run_id

    @property
    def silver_dir(self) -> Path:
        return self.silver_root / self.source / self.run_id

    @property
    def bronze_manifest_path(self) -> Path:
        return self.bronze_dir / "manifest.json"

    @property
    def bronze_records_path(self) -> Path:
        return self.bronze_dir / "records.jsonl"

    @property
    def silver_fragments_path(self) -> Path:
        return self.silver_dir / "fragments.jsonl"

    @property
    def silver_manifest_path(self) -> Path:
        return self.silver_dir / "manifest.json"

    @property
    def map_path(self) -> Path:
        return self.silver_dir / "map.json"

    @property
    def quarantine_path(self) -> Path:
        return self.silver_dir / "quarantine.jsonl"
