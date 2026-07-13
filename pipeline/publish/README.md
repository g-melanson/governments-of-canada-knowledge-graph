# Stage 5 — Publish

Domain validation gate: read merged Silver, strip internal metadata, validate against **`schemas/schema.yaml`**, write **Gold**.

| | |
|--|--|
| **CLI** | `python3 -m pipeline.publish` |
| **Tier** | Gold |
| **Input** | `universe/{run_id}/4-merged/nodes.jsonl` + `edges.jsonl` |
| **Output** | `universe/{run_id}/5-gold/` |

## Commands

```bash
python3 -m pipeline.publish run --run-id demo
```

### CLI flags

| Flag | Default | Purpose |
|------|---------|---------|
| `--run-id` | UTC timestamp | Run directory under `universe/` (reads merged + writes gold) |
| `--universe-root` | `universe` | Runtime output root |

## How it works

1. Stream merged `nodes.jsonl` and `edges.jsonl`.
2. Strip internal metadata (`bronze_references`, `sources`, …).
3. Validate each fragment's `@type` with `linkml.validator.Validator` against `schemas/schema.yaml`.
4. Write accepted fragments to Gold; rejects to Gold quarantine.

## Output layout

```text
universe/{run_id}/5-gold/
  nodes.jsonl
  edges.jsonl
  manifest.json
  quarantine/
    nodes.jsonl
    edges.jsonl
```

## Package layout

```text
publish/
  cli.py
  runner.py
  engine.py       ValidationEngine, JSONL streaming
  context.py      PublishContext → UniversePaths
```

Lint domain schema:

```bash
cd schemas && gen-yaml schema.yaml
```

## Downstream

Gold output is suitable for graph databases and query layers.
