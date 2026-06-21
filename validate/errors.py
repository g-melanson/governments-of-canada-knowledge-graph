"""Typed exceptions for Stage 2 validation."""


class ValidateError(Exception):
    """Base class for validation-stage failures."""


class StagingInputError(ValidateError):
    """Staging records.jsonl or manifest missing or unreadable."""


class SchemaConfigError(ValidateError):
    """Schema registry misconfigured or schema file missing."""


class ValidationFailedError(ValidateError):
    """One or more records failed validation (--fail-fast mode)."""


class EmptyBronzeError(ValidateError):
    """All records rejected; Bronze would be empty."""
    