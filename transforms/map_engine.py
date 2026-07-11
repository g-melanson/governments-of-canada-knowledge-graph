"""YAML-map-driven transform engine.

Reads a transform.yaml spec (class_derivations / populated_from / slot_derivations)
and materialises Silver fragments without a Python materializer.

Spec shape expected::

    class_derivations:
      DomainClassName:
        populated_from: BronzeRowClass        # matches _row_class on Bronze rows
        when: "python expression"             # optional; skip row if falsy
        slot_derivations:
          slot_name:
            expr: "python expression"         # evaluated with row fields as locals

The ``when`` expression is evaluated against the same row namespace as slot
expressions.  If it evaluates to a falsy value (False, None, 0, empty string)
the entire derivation is skipped for that row and no fragment is emitted.
Derivations without ``when`` behave exactly as before.

The ``expr`` strings are evaluated with the Bronze row fields available as local
variables (excluding ``_row_class``).  A restricted builtins dict is supplied so
expressions can call ``str()``, ``int()``, ``bool()``, ``len()`` etc but cannot
import modules or exec arbitrary code.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Callable, Iterator

import yaml

_SAFE_BUILTINS: dict[str, Any] = {
    "str": str,
    "int": int,
    "float": float,
    "bool": bool,
    "len": len,
    "None": None,
    "True": True,
    "False": False,
}


def _eval_expr(expr: str, ns: dict[str, Any]) -> Any:
    """Evaluate a slot derivation expression against the row namespace."""
    return eval(expr, {"__builtins__": _SAFE_BUILTINS}, ns)  # noqa: S307


class YamlMapEngine:
    """Materialises Silver fragments from a transform YAML spec.

    Implements the same interface as Python materializers — a single
    ``materialize(row, line_number)`` generator — so the runner can call
    either interchangeably.
    """

    def __init__(
        self,
        map_path: Path,
        bronze_reference_factory: Callable[[int], dict] | None = None,
        default_row_class: str | None = None,
    ) -> None:
        spec = yaml.safe_load(map_path.read_text(encoding="utf-8"))
        self._bronze_reference_factory = bronze_reference_factory
        self._default_row_class = default_row_class
        self._dispatch = self._build_dispatch(spec)

    @staticmethod
    def _build_dispatch(
        spec: dict,
    ) -> dict[str, list[tuple[str, str, dict[str, str], str | None]]]:
        """Return {bronze_row_class: [(domain_class, target_type, {slot: expr}, when_expr)]}.

        ``target_type`` is the value written to ``@type`` in the emitted fragment.
        It defaults to ``domain_class`` but can be overridden via ``target_type:``
        in the class derivation — useful when multiple derivations share the same
        logical type (e.g. several relationship kinds all emit ``@type: RELATIONSHIP``).

        ``when_expr`` is an optional guard expression (the ``when:`` key in the spec).
        None means no guard — the derivation always runs.
        """
        dispatch: dict[str, list[tuple[str, str, dict[str, str], str | None]]] = {}
        for domain_class, class_def in (spec.get("class_derivations") or {}).items():
            class_def = class_def or {}
            populated_from = class_def.get("populated_from")

            if not populated_from:
                continue
            
            target_type: str = class_def.get("target_type") or domain_class
            when_expr: str | None = class_def.get("when") or None
            slot_derivations: dict[str, str] = {
                slot: (sd or {}).get("expr") or ""
                for slot, sd in (class_def.get("slot_derivations") or {}).items()
            }
            dispatch.setdefault(populated_from, []).append(
                (domain_class, target_type, slot_derivations, when_expr)
            )
        return dispatch

    def materialize(self, row: dict, line_number: int) -> Iterator[dict]:
        """Yield Silver fragment dicts for one Bronze row."""
        row_class = row.get("_row_class") or self._default_row_class
        derivations = self._dispatch.get(row_class)
        if not derivations:
            return

        ns = {k: v for k, v in row.items() if k != "_row_class"}

        for domain_class, target_type, slot_derivations, when_expr in derivations:
            if when_expr is not None:
                try:
                    guard = _eval_expr(when_expr, ns)
                except Exception:
                    guard = False
                if not guard:
                    continue

            fragment: dict[str, Any] = {"@type": target_type}

            if self._bronze_reference_factory is not None:
                fragment["bronze_reference"] = self._bronze_reference_factory(
                    line_number
                )

            for slot, expr in slot_derivations.items():
                if not expr:
                    fragment[slot] = None
                    continue
                try:
                    fragment[slot] = _eval_expr(expr, ns)
                except Exception:
                    fragment[slot] = None

            yield fragment

    @property
    def dispatch_table(self) -> dict[str, list[tuple[str, str, dict[str, str], str | None]]]:
        """Expose dispatch table for testing and introspection."""
        return self._dispatch
