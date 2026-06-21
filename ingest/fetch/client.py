"""Download or reuse cached raw publisher bytes for a staging run."""

from __future__ import annotations

import shutil
import time
from pathlib import Path
from typing import Any

import requests

from ingest.context import RunContext
from ingest.errors import FetchError
from ingest.fetch.cache import (
    is_cache_fresh,
    read_cache_meta,
    sha256_file,
    url_cache_path,
    write_cache_meta,
)

USER_AGENT = "GCKG-Ingest/0.1 (+https://w3id.org/gckg/)"


def fetch_raw(ctx: RunContext, source_cfg: dict[str, Any]) -> tuple[Path, dict[str, Any]]:
    """Return (run_snapshot_path, input_manifest_fragment)."""
    url = source_cfg["url"]
    ext = "xml" if source_cfg.get("format") == "xml" else "csv"
    raw_name = source_cfg.get("raw_filename", f"source.{ext}")
    cache_file = url_cache_path(ctx.cache_dir, url, ext)
    ctx.cache_dir.mkdir(parents=True, exist_ok=True)
    ctx.raw_dir.mkdir(parents=True, exist_ok=True)
    run_snapshot = ctx.raw_dir / raw_name

    if source_cfg.get("local_only") and ctx.fetch_policy != "local-file":
        raise FetchError(
            f"{ctx.source} must be ingested from a local file. "
            "Download and extract the publisher CSV, then rerun with "
            "--fetch-policy local-file --input <path/to/csv>"
        )

    if ctx.fetch_policy == "local-file":
        if ctx.input_path is None:
            raise FetchError("--input required for local-file fetch policy")
        shutil.copy2(ctx.input_path, run_snapshot)
        return run_snapshot, {
            "url": str(ctx.input_path),
            "fetch_policy": ctx.fetch_policy,
            "cache_hit": False,
            "sha256": sha256_file(run_snapshot),
            "bytes": run_snapshot.stat().st_size,
            "retrieved_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        }

    ttl = int(source_cfg.get("ttl_seconds", 86400))
    use_cache = ctx.fetch_policy == "cache-only" or (
        ctx.fetch_policy == "default" and is_cache_fresh(cache_file, ttl)
    )

    if ctx.fetch_policy == "cache-only":
        if not cache_file.exists():
            raise FetchError(f"No cached raw file for {ctx.source}")
        shutil.copy2(cache_file, run_snapshot)
        meta = read_cache_meta(cache_file) or {}
        meta["cache_hit"] = True
        meta["fetch_policy"] = ctx.fetch_policy
        return run_snapshot, meta

    if use_cache and cache_file.exists():
        shutil.copy2(cache_file, run_snapshot)
        meta = read_cache_meta(cache_file) or {}
        meta["cache_hit"] = True
        meta["fetch_policy"] = ctx.fetch_policy
        return run_snapshot, meta

    headers = {"User-Agent": USER_AGENT}
    meta = read_cache_meta(cache_file) or {}
    if meta.get("etag"):
        headers["If-None-Match"] = meta["etag"]
    if meta.get("last_modified"):
        headers["If-Modified-Since"] = meta["last_modified"]

    try:
        resp = requests.get(url, headers=headers, timeout=(10, 120))
    except requests.RequestException as exc:
        raise FetchError(f"GET {url} failed: {exc}") from exc

    if resp.status_code == 304 and cache_file.exists():
        shutil.copy2(cache_file, run_snapshot)
        meta["cache_hit"] = True
        meta["fetch_policy"] = ctx.fetch_policy
        return run_snapshot, meta

    if resp.status_code != 200:
        raise FetchError(f"GET {url} returned {resp.status_code}")

    cache_file.write_bytes(resp.content)
    run_snapshot.write_bytes(resp.content)
    new_meta = {
        "url": url,
        "fetch_policy": ctx.fetch_policy,
        "cache_hit": False,
        "etag": resp.headers.get("ETag"),
        "last_modified": resp.headers.get("Last-Modified"),
        "sha256": sha256_file(cache_file),
        "bytes": len(resp.content),
        "retrieved_at": time.time(),
    }
    write_cache_meta(cache_file, new_meta)
    new_meta["retrieved_at"] = time.strftime(
        "%Y-%m-%dT%H:%M:%SZ", time.gmtime(new_meta["retrieved_at"])
    )
    return run_snapshot, new_meta
