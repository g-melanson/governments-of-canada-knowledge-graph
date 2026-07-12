"""Typed exceptions for Stage 4 integrate."""


class IntegrateError(Exception):
    """Base class for integrate-stage failures."""


class SilverInputError(IntegrateError):
    """A Silver fragments file or manifest is missing or unreadable."""


class FragmentShapeError(IntegrateError):
    """A fragment cannot be classified or normalized (handled → quarantine in runner)."""


class MergeConflictError(IntegrateError):
    """Same canonical node id resolves to incompatible @type values."""


class EmptyMergeError(IntegrateError):
    """No nodes or edges survived integration; merged output would be empty."""
    