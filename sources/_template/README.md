# Source template

Copy this directory to `sources/{your_source_name}/` and replace every `TEMPLATE` placeholder.

```bash
cp -R sources/_template sources/my_new_source
# then rename files:
#   TEMPLATE.schema.yaml  → my_new_source.schema.yaml
#   TEMPLATE_to_gckg.transform.yaml → my_new_source_to_gckg.transform.yaml
```

Wire-up outside this folder:

1. Add fetch config to `pipeline/ingest/config/sources.yaml`
2. Import the adapter in `pipeline/ingest/cli.py` (until auto-discovery exists)
3. Add tests under `pipeline/ingest/tests/adapters/`
4. Add a raw fixture under `pipeline/ingest/tests/fixtures/raw/`

Pattern guide: [`docs/ingest-patterns-skeleton.md`](../../docs/ingest-patterns-skeleton.md)
