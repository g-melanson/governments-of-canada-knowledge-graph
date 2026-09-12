import yaml

from datetime import datetime, timezone
from typing import Any

from linkml_runtime.utils.schemaview import SchemaView

from datetime import datetime, timezone
from dateutil import parser
from typing import Type, TypeVar, Any

T = TypeVar("T", datetime, float, int, str)

def coerce(val: Any, target_type: Type[T]) -> T | None:
    if val is None:
        return None

    if target_type is datetime:
        if isinstance(val, datetime):
            return val if val.tzinfo else val.replace(tzinfo=timezone.utc)
        text = str(val).strip()
        if not text:
            return None
        for fmt in ("%Y-%m-%dT%H:%M:%S", "%Y/%m/%d"):  # ISO first, then expenditures
            try:
                return datetime.strptime(text, fmt).replace(tzinfo=timezone.utc)
            except ValueError:
                continue
        raise ValueError(f"unparseable datetime: {text!r}")

    if target_type is float:
        if isinstance(val, (int, float)):
            return float(val)
        text = str(val).strip().replace(",", "")
        return float(text) if text else None

    if target_type is int:
        if isinstance(val, int):
            return val
        text = str(val).strip()
        return int(text) if text else None

    if target_type is str:
        text = str(val).strip()
        return text or None

    raise TypeError(f"unsupported target type: {target_type!r}")


class SchemaNormalizer:
    def __init__(self, schema_path: str):
        self._schema_view = SchemaView(schema_path)
        self._ranges_cache: dict[str, dict[str, str | None]] = {}

    def _ranges(self, row_class: str) -> dict[str, str | None]:
        if row_class not in self._ranges_cache:
            self._ranges_cache[row_class] = self._class_slot_range_lookup(
                self._schema_view, row_class
            )
        return self._ranges_cache[row_class]

    def normalize(self, row_class: str, row: dict[str, Any]) -> dict[str, Any]:
        out: dict[str, Any] = {"_row_class": row_class}
        for slot_name, slot_range in self._ranges(row_class).items():
            val = row.get(slot_name)
            if slot_range == "string":
                out[slot_name] = coerce(val, str)
            elif slot_range == "integer":
                out[slot_name] = coerce(val, int)
            elif slot_range == "float":
                out[slot_name] = coerce(val, float)
            elif slot_range == "datetime":
                out[slot_name] = coerce(val, datetime)
        return out

    @staticmethod
    def _class_slot_range_lookup(
        schema: SchemaView,
        class_name: str,
    ) -> dict[str, str | None]:
        return {
            slot_name: schema.induced_slot(slot_name, class_name).range
            for slot_name in schema.class_slots(class_name)
        }
