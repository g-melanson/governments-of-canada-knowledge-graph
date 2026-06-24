from pathlib import Path
from typing import Any
import yaml
from functools import lru_cache

CONFIG_PATH = Path(__file__).with_name("maps.yaml")

REPO_ROOT = CONFIG_PATH.resolve().parents[2]

@lru_cache
def load_maps() -> dict[str, dict[str, Any]]:
    with CONFIG_PATH.open(encoding="utf-8") as f:
        return yaml.safe_load(f) or {}

def get_map_config(source: str, *, map_path: Path | None = None) -> dict[str, Any]:
    cfg = load_maps()[source] 
    resolved_map = map_path or (REPO_ROOT / cfg["map_path"])
    materializer = cfg["materializer"]
    return {**cfg, "map_path": resolved_map, "materializer": materializer}
