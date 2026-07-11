"""Default resolver: every id maps to itself (exact-URI merge only)."""

from __future__ import annotations

from integrate.resolvers.base import EntityResolver


class IdentityResolver(EntityResolver):
    def canonical_id(self, node_id: str, *, node_type: str | None = None) -> str:
        return node_id


def get_resolver() -> EntityResolver:
    return IdentityResolver()
    