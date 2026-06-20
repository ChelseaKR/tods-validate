"""tods-validate: a validator for Transit Operational Data Standard (TODS) feeds."""

__version__ = "0.4.0"

from .api import ValidationResult, validate_feed
from .findings import Finding, Severity

__all__ = ["Finding", "Severity", "ValidationResult", "__version__", "validate_feed"]
