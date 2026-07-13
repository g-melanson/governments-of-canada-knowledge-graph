# Stage 1 — Ingest

Parse raw publisher data into **source-shaped** JSONL. No GCKG domain IDs — only normalized rows that match the source LinkML schema contract.

| | |
|--|--|
| **CLI** | `python3 -m pipeline.ingest` |
| **Tier** | Pre-Bronze (staging) |
| **Output** | `universe/{run_id}/1-staging/{source}/` |

## Commands

```bash
# List registered sources
python3 -m pipeline.ingest list-sources

# Run one source (default run_id = UTC timestamp)
python3 -m pipeline.ingest run --source commons_members --run-id demo

# Local fixture (offline)
python3 -m pipeline.ingest run --source commons_members \
  --run-id demo --fetch-policy local-file \
  --input pipeline/ingest/tests/fixtures/raw/commons_members_sample.xml

# Force fresh HTTP download (bypass TTL cache)
python3 -m pipeline.ingest run --source commons_members \
  --run-id demo --fetch-policy refresh
```

### CLI flags

| Flag | Default | Purpose |
|------|---------|---------|
| `--source` | required | Registered source name |
| `--run-id` | UTC timestamp | Run directory name |
| `--universe-root` | `universe` | Runtime output root |
| `--fetch-policy` | `default` | `default`, `refresh`, `cache-only`, `local-file` |
| `--input` | — | Local raw file (`local-file` policy) |

## Registered sources

| Source | Adapter | Fetch | Notes |
|--------|---------|-------|-------|
| `commons_members` | `sources/commons_members/adapter.py` | HTTP or `local-file` | MP XML from ourcommons.ca |
| `commons_members_bylaw` | `sources/commons_members_bylaw/adapter.py` | HTTP or `local-file` | Bylaw XML; multi-class rows |
| `commons_members_expenditures` | `sources/commons_members_expenditures/adapter.py` | `local-file` only | Pickle at `data/expense_claims.pkl` |

Publisher URLs and TTLs: [`config/sources.yaml`](config/sources.yaml).

## Output layout

```text
universe/{run_id}/1-staging/{source}/
  raw/{filename}          publisher snapshot for this run
  records.jsonl           one normalized JSON object per line
  manifest.json           provenance, counts, input metadata

universe/cache/{source}/  shared HTTP cache (not per-run)
```

## How it works

1. **`sources/registry.py`** resolves `--source` → adapter class (`@register`).
2. **`fetch/client.py`** downloads or copies raw bytes into `raw/`, using `universe/cache/{source}/` when appropriate.
3. **`adapter.parse()`** yields publisher-shaped dicts with `_row_class` for multi-class sources.
4. **`normalize.py` (`SchemaNormalizer`)** coerces types using `sources/{source}/{source}.schema.yaml`.
5. **`runner.py`** writes `records.jsonl` + `manifest.json`.

## Package layout

```text
ingest/
  cli.py           CLI entry
  runner.py        orchestration
  context.py       RunContext → UniversePaths
  normalize.py     SchemaNormalizer
  schema.py        load_source_schema()
  fetch/           HTTP cache + client
  config/          sources.yaml
  tests/           adapter unit tests + fixtures
```

## Adding a source

1. Create `sources/{name}/` with `{name}.schema.yaml`, `adapter.py`, and optional transform map.
2. Register the adapter in `sources/registry.py` (or import in `cli.py` like existing Commons sources).
3. Add an entry to `config/sources.yaml` and `pipeline/validate/config/schemas.yaml`.
4. Add tests under `tests/adapters/`.

## Handoff to Stage 2

```bash
python3 -m pipeline.validate run \
  --source commons_members \
  --run-id {run_id}
```
