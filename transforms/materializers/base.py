from __future__ import annotations
from abc import ABC, abstractmethod
from typing import Iterator
from transforms.context import TransformContext

class FragmentMaterializer(ABC):
    def __init__(self, context: TransformContext) -> None:
        self.context = context

    @abstractmethod
    def materialize(self, row: dict, line_number: int) -> Iterator[dict]:
        """Yield Silver fragment dicts from one Bronze row."""

    def make_bronze_reference(self, line_number: int) -> dict:
        return {
            "source": self.context.source,
            "bronze_run_id": self.context.bronze_run_id,
            "line_number": line_number,
        }