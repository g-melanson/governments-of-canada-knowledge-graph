"""On-disk cache helpers: paths, metadata, TTL checks, and file hashing."""

from __future__ import annotations

import hashlib
import json
import time
from pathlib import Path
from typing import Any


def url_cache_path(cache_dir: Path, url: str, ext: str) -> Path:
    digest = hashlib.sha256(url.encode()).hexdigest()[:16]
    return cache_dir / f"{digest}.{ext}"


def cache_meta_path(cache_file: Path) -> Path:
    return cache_file.with_suffix(cache_file.suffix + ".meta.json")


def read_cache_meta(cache_file: Path) -> dict[str, Any] | None:
    meta_path = cache_meta_path(cache_file)
    if not meta_path.exists():
        return None
    return json.loads(meta_path.read_text(encoding="utf-8"))


def write_cache_meta(cache_file: Path, meta: dict[str, Any]) -> None:
    cache_meta_path(cache_file).write_text(
        json.dumps(meta, indent=2), encoding="utf-8"
    )


def is_cache_fresh(cache_file: Path, ttl_seconds: int) -> bool:
    if not cache_file.exists():
        return False
    meta = read_cache_meta(cache_file)
    if not meta:
        return False
    retrieved_at = float(meta.get("retrieved_at", 0))
    return (time.time() - retrieved_at) < ttl_seconds


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()
