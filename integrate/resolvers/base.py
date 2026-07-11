
"""Entity-resolution interface for Stage 4."""

from __future__ import annotations

from abc import ABC, abstractmethod


class EntityResolver(ABC):
    @abstractmethod
    def canonical_id(self, node_id: str, *, node_type: str | None = None) -> str:
        """Return the canonical GCKG URI for a node id."""

    def resolve_endpoint(self, endpoint_id: str, *, node_type: str | None = None) -> str:
        return self.canonical_id(endpoint_id, node_type=node_type)
