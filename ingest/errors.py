"""Typed exceptions raised by ingest fetch, parse, and runner layers."""


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
