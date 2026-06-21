# Execution plan — `commons_members` adapter (with code)

Stage 1 ingest for [MemberOfParliament XML](https://www.ourcommons.ca/members/en/search/xml).  
Registry name: **`commons_members`** · Module: `ingest/adapters/commons/members.py`

Implement files **top to bottom**. Each section: **what it does** → **exact code**.

---

## Source specification (reference)

| XML element | Staged field | Notes |
|-------------|--------------|--------|
| `PersonId` | `person_id` | required |
| `PersonShortHonorific` | `person_short_honorific` | |
| `PersonOfficialFirstName` | `person_official_first_name` | |
| `PersonOfficialLastName` | `person_official_last_name` | |
| `ConstituencyName` | `constituency_name` | |
| `ConstituencyProvinceTerritoryName` | `constituency_province_territory_name` | |
| `CaucusShortName` | `caucus_short_name` | |
| `FromDateTime` | `from_date_time` | ISO string |
| `ToDateTime` | `to_date_time` | `null` if `xsi:nil="true"` |

One JSONL record per `<MemberOfParliament>` element. No GCKG IDs in Stage 1.

---

## 0. Package manifest

**What:** Makes `ingest` installable so `python -m ingest` resolves imports from the repo root.

**File:** `pyproject.toml`

```toml
[project]
name = "gckg-ingest"
version = "0.1.0"
description = "GCKG Stage 1 ingest adapters"
requires-python = ">=3.11"
dependencies = [
  "pyyaml>=6.0",
  "requests>=2.31",
]

[project.optional-dependencies]
dev = ["pytest>=8.0"]

[project.scripts]
ingest = "ingest.cli:main"

[build-system]
requires = ["setuptools>=68"]
build-backend = "setuptools.build_meta"

[tool.setuptools.packages.find]
include = ["ingest*"]

[tool.pytest.ini_options]
testpaths = ["ingest/tests"]
```

```bash
pip install -e ".[dev]"
```

---

## 1. Errors

**What:** Typed exceptions the runner and adapters raise so failures are actionable (network vs parse vs empty feed).

**File:** `ingest/errors.py`

```python
class IngestError(Exception):
    """Base class for ingest failures."""


class FetchError(IngestError):
    """HTTP or cache fetch failed."""


class ParseError(IngestError):
    """Source file could not be parsed."""


class EmptySourceError(IngestError):
    """Adapter produced zero records after filtering."""


class UnknownSourceError(IngestError):
    """Registry has no adapter for the requested source name."""
```

---

## 2. Run context

**What:** Immutable per-run settings passed through fetch → parse → emit: where to write, which fetch policy, optional flags.

**File:** `ingest/context.py`

```python
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Literal

FetchPolicy = Literal["default", "refresh", "cache-only", "local-file"]


@dataclass(frozen=True)
class RunContext:
    source: str
    run_id: str
    staging_root: Path
    fetch_policy: FetchPolicy = "default"
    input_path: Path | None = None  # local-file mode
    current_only: bool = False  # commons_members: keep rows where to_date_time is null

    @property
    def source_dir(self) -> Path:
        return self.staging_root / self.source

    @property
    def run_dir(self) -> Path:
        return self.source_dir / self.run_id

    @property
    def raw_dir(self) -> Path:
        return self.run_dir / "raw"

    @property
    def records_path(self) -> Path:
        return self.run_dir / "records.jsonl"

    @property
    def manifest_path(self) -> Path:
        return self.run_dir / "manifest.json"

    @property
    def cache_dir(self) -> Path:
        return self.source_dir / "cache"
```

---

## 3. Source config

**What:** Declares URL, cache TTL, and rate limit for `commons_members` (and future sources).

**File:** `ingest/config/sources.yaml`

```yaml
commons_members:
  url: https://www.ourcommons.ca/members/en/search/xml
  ttl_seconds: 21600
  rate_limit_seconds: 1.0
  format: xml
  raw_filename: members.xml
```

**File:** `ingest/config/__init__.py` — load helper

```python
from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Any

import yaml

CONFIG_PATH = Path(__file__).with_name("sources.yaml")


@lru_cache
def load_sources() -> dict[str, dict[str, Any]]:
    with CONFIG_PATH.open(encoding="utf-8") as f:
        return yaml.safe_load(f) or {}


def get_source_config(source: str) -> dict[str, Any]:
    cfg = load_sources().get(source)
    if cfg is None:
        raise KeyError(f"Unknown source config: {source}")
    return cfg
```

---

## 4. Fetch layer

**What:** Downloads (or reuses cached) raw publisher bytes, writes a per-run snapshot under `staging/…/raw/`, returns path + metadata for `manifest.json`.

### `ingest/fetch/cache.py`

```python
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
```

### `ingest/fetch/client.py`

```python
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
```

---

## 5. Adapter protocol and registry

**What:** `BaseAdapter` defines the parse/normalize/filter pipeline; registry maps `commons_members` → adapter class.

### `ingest/adapters/base.py`

```python
from __future__ import annotations

from abc import ABC, abstractmethod
from typing import ClassVar, Iterator


class BaseAdapter(ABC):
    source: ClassVar[str]

    @abstractmethod
    def parse(self, raw_path) -> Iterator[dict]:
        """Yield one raw dict per source record (publisher-shaped keys)."""

    def normalize(self, row: dict) -> dict:
        """Mechanical cleanup. Override in subclass."""
        return row

    def filter_row(self, row: dict, ctx) -> bool:
        """Return False to drop row. Override in subclass."""
        return True
```

### `ingest/adapters/registry.py`

```python
from __future__ import annotations

from typing import Type

from ingest.adapters.base import BaseAdapter
from ingest.errors import UnknownSourceError

_REGISTRY: dict[str, Type[BaseAdapter]] = {}


def register(cls: Type[BaseAdapter]) -> Type[BaseAdapter]:
    if not cls.source:
        raise ValueError(f"{cls.__name__} missing source name")
    _REGISTRY[cls.source] = cls
    return cls


def get_adapter(source: str) -> BaseAdapter:
    cls = _REGISTRY.get(source)
    if cls is None:
        raise UnknownSourceError(f"No adapter registered for source: {source}")
    return cls()


def list_sources() -> list[str]:
    return sorted(_REGISTRY)
```

---

## 6. Commons XML utilities

**What:** Streaming XML helpers shared by members/votes/petitions adapters — strip namespaces, read child text, treat `xsi:nil` as null.

**File:** `ingest/adapters/commons/xml_utils.py`

```python
from __future__ import annotations

from pathlib import Path
from typing import Iterator
from xml.etree import ElementTree as ET

XSI_NIL = "{http://www.w3.org/2001/XMLSchema-instance}nil"


def local_tag(tag: str) -> str:
    return tag.rsplit("}", 1)[-1]


def child_text(parent: ET.Element, tag: str) -> str | None:
    for child in parent:
        if local_tag(child.tag) == tag:
            if child.get(XSI_NIL) == "true":
                return None
            text = (child.text or "").strip()
            return text or None
    return None


def iter_member_of_parliament(path: Path) -> Iterator[ET.Element]:
    """Stream <MemberOfParliament> elements without loading full tree."""
    for event, elem in ET.iterparse(path, events=("end",)):
        if local_tag(elem.tag) == "MemberOfParliament":
            yield elem
            elem.clear()
```

---

## 7. `commons_members` adapter

**What:** Parses MP XML into snake_case dicts, optionally filters to current members only, rejects rows without `person_id`.

**File:** `ingest/adapters/commons/members.py`

```python
from __future__ import annotations

from pathlib import Path
from typing import Iterator

from ingest.adapters.base import BaseAdapter
from ingest.adapters.commons.xml_utils import child_text, iter_member_of_parliament, local_tag
from ingest.adapters.registry import register

FIELD_MAP = {
    "PersonId": "person_id",
    "PersonShortHonorific": "person_short_honorific",
    "PersonOfficialFirstName": "person_official_first_name",
    "PersonOfficialLastName": "person_official_last_name",
    "ConstituencyName": "constituency_name",
    "ConstituencyProvinceTerritoryName": "constituency_province_territory_name",
    "CaucusShortName": "caucus_short_name",
    "FromDateTime": "from_date_time",
    "ToDateTime": "to_date_time",
}


@register
class CommonsMembersAdapter(BaseAdapter):
    source = "commons_members"

    def parse(self, raw_path: Path) -> Iterator[dict]:
        for elem in iter_member_of_parliament(raw_path):
            row: dict = {}
            for child in elem:
                xml_name = local_tag(child.tag)
                if xml_name not in FIELD_MAP:
                    continue
                row[FIELD_MAP[xml_name]] = child_text(elem, xml_name)
            yield row

    def normalize(self, row: dict) -> dict:
        out = {k: row.get(k) for k in FIELD_MAP.values()}
        pid = out.get("person_id")
        if pid is not None:
            out["person_id"] = str(pid).strip()
        for k, v in out.items():
            if isinstance(v, str):
                out[k] = v.strip() or None
        return out

    def filter_row(self, row: dict, ctx) -> bool:
        if not row.get("person_id"):
            return False
        if ctx.current_only and row.get("to_date_time") is not None:
            return False
        return True
```

**Filter policy:** default keeps all tenure rows; pass `--current-only` to keep only sitting members (`to_date_time is null`).

---

## 8. Runner and CLI

**What:** Orchestrates fetch → parse → normalize → filter → write `records.jsonl` + `manifest.json`; CLI exposes `run` and `list-sources`.

### `ingest/runner.py`

```python
from __future__ import annotations

import json
import logging
from datetime import datetime, timezone

from ingest.adapters.registry import get_adapter
from ingest.config import get_source_config
from ingest.context import RunContext
from ingest.errors import EmptySourceError
from ingest.fetch.client import fetch_raw

log = logging.getLogger(__name__)


def run_ingest(ctx: RunContext) -> dict:
    adapter = get_adapter(ctx.source)
    source_cfg = get_source_config(ctx.source)
    ctx.run_dir.mkdir(parents=True, exist_ok=True)

    started_at = datetime.now(timezone.utc)
    raw_path, input_meta = fetch_raw(ctx, source_cfg)

    record_count = 0
    rejected_count = 0
    with ctx.records_path.open("w", encoding="utf-8") as fout:
        for raw_row in adapter.parse(raw_path):
            row = adapter.normalize(raw_row)
            if not adapter.filter_row(row, ctx):
                rejected_count += 1
                continue
            fout.write(json.dumps(row, ensure_ascii=False) + "\n")
            record_count += 1

    if record_count == 0:
        raise EmptySourceError(f"{ctx.source} produced zero records")

    finished_at = datetime.now(timezone.utc)
    manifest = {
        "run_id": ctx.run_id,
        "source": ctx.source,
        "started_at": started_at.isoformat(),
        "finished_at": finished_at.isoformat(),
        "status": "success",
        "inputs": [input_meta],
        "output": {
            "records_path": "records.jsonl",
            "record_count": record_count,
            "rejected_count": rejected_count,
        },
    }
    ctx.manifest_path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    log.info(
        "ingest_complete",
        extra={
            "source": ctx.source,
            "run_id": ctx.run_id,
            "record_count": record_count,
            "rejected_count": rejected_count,
        },
    )
    return manifest
```

### `ingest/cli.py`

```python
from __future__ import annotations

import argparse
import json
import logging
from datetime import datetime, timezone
from pathlib import Path

from ingest.adapters.registry import list_sources
from ingest.context import RunContext
from ingest.runner import run_ingest

# Import adapters so @register runs
import ingest.adapters.commons.members  # noqa: F401


def _default_run_id() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H%M%SZ")


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    parser = argparse.ArgumentParser(prog="ingest")
    sub = parser.add_subparsers(dest="command", required=True)

    run_p = sub.add_parser("run", help="Run one source adapter")
    run_p.add_argument("--source", required=True)
    run_p.add_argument("--run-id", default=_default_run_id())
    run_p.add_argument("--staging-root", type=Path, default=Path("staging"))
    run_p.add_argument(
        "--fetch-policy",
        choices=["default", "refresh", "cache-only", "local-file"],
        default="default",
    )
    run_p.add_argument("--input", type=Path, help="Local raw file (local-file policy)")
    run_p.add_argument(
        "--current-only",
        action="store_true",
        help="commons_members: emit only rows with null to_date_time",
    )

    sub.add_parser("list-sources", help="List registered adapters")

    args = parser.parse_args()
    if args.command == "list-sources":
        for name in list_sources():
            print(name)
        return

    ctx = RunContext(
        source=args.source,
        run_id=args.run_id,
        staging_root=args.staging_root,
        fetch_policy=args.fetch_policy,
        input_path=args.input,
        current_only=args.current_only,
    )
    manifest = run_ingest(ctx)
    print(json.dumps(manifest["output"], indent=2))


if __name__ == "__main__":
    main()
```

**What `cli.py` does:** Parses subcommands; builds `RunContext`; triggers `run_ingest`; prints summary JSON for `run`, or source names for `list-sources`.

### `ingest/__main__.py`

```python
from ingest.cli import main

if __name__ == "__main__":
    main()
```

### Side-effect import in `ingest/adapters/commons/__init__.py`

```python
from ingest.adapters.commons import members  # noqa: F401
```

---

## 9. Tests

**What:** Offline tests using a trimmed fixture; no network in CI.

**Setup:**

```bash
curl -A "GCKG-Ingest/0.1" -o ingest/tests/fixtures/raw/commons_members.xml \
  "https://www.ourcommons.ca/members/en/search/xml"
# manually trim to commons_members_sample.xml (~10 rows)
```

**File:** `ingest/tests/adapters/test_commons_members.py`

```python
from __future__ import annotations

import json
from pathlib import Path

import pytest

from ingest.adapters.commons.members import CommonsMembersAdapter
from ingest.context import RunContext
from ingest.runner import run_ingest

FIXTURE = Path(__file__).resolve().parents[1] / "fixtures/raw/commons_members_sample.xml"


@pytest.fixture
def adapter() -> CommonsMembersAdapter:
    return CommonsMembersAdapter()


def test_parse_sample_has_required_keys(adapter: CommonsMembersAdapter) -> None:
    rows = list(adapter.parse(FIXTURE))
    assert len(rows) >= 1
    norm = adapter.normalize(rows[0])
    assert norm["person_id"]
    assert "constituency_name" in norm
    assert "caucus_short_name" in norm


def test_cache_only_integration(tmp_path: Path) -> None:
    ctx = RunContext(
        source="commons_members",
        run_id="test-run",
        staging_root=tmp_path,
        fetch_policy="local-file",
        input_path=FIXTURE,
    )
    manifest = run_ingest(ctx)
    assert manifest["output"]["record_count"] >= 1
    lines = ctx.records_path.read_text(encoding="utf-8").strip().splitlines()
    row = json.loads(lines[0])
    assert not any(k.startswith("gckg:") for k in row)
```

---

## 10. Wire registry import

**What:** Ensures `members` adapter self-registers when CLI loads. Already done via `import ingest.adapters.commons.members` in `cli.py`.

Add empty `ingest/fetch/__init__.py` and `ingest/adapters/__init__.py` if missing (Python package markers).

---

## 11. Manual run

```bash
pip install -e ".[dev]"

# From fixture (no network)
python -m ingest run --source commons_members \
  --fetch-policy local-file \
  --input ingest/tests/fixtures/raw/commons_members_sample.xml

# Live fetch
python -m ingest run --source commons_members --fetch-policy refresh

# Current MPs only
python -m ingest run --source commons_members --fetch-policy refresh --current-only
```

---

## 12. Done criteria

- [ ] All §0–§9 files exist and match this plan
- [ ] `pytest ingest/tests` passes offline
- [ ] `python -m ingest list-sources` prints `commons_members`
- [ ] `staging/commons_members/{run_id}/` contains `raw/`, `records.jsonl`, `manifest.json`
- [ ] No `gckg:` keys in `records.jsonl`

---

## 13. Follow-on (not this PR)

- `source/member_of_parliament.schema.yaml` + Stage 2 Validate
- Materialize: `Person` + `HouseOfCommonsMembership` from staged rows
