"""tods-validate: a validator for Transit Operational Data Standard (TODS) feeds."""

from importlib.metadata import PackageNotFoundError, version

try:
    __version__ = version("tods-validate")
except PackageNotFoundError:  # running from a source tree without an install
    __version__ = "0.0.0+unknown"

from . import read  # noqa: F401  (submodule import; makes `tods_validate.read` available)
from .api import Suggestion, ValidationResult, suggest_fixes, validate_feed
from .findings import Finding, Severity

__all__ = [
    "Finding",
    "Severity",
    "Suggestion",
    "ValidationResult",
    "__version__",
    "suggest_fixes",
    "validate_feed",
]
