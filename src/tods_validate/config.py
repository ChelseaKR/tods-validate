"""Optional configuration file support.

A ``tods-validate.toml`` in the working directory (or a file passed via
``--config``) lets an agency encode local policy once instead of repeating
command-line flags in every CI job:

    ignore = ["TODS-W206", "TODS-I108"]
    fail-on = "warning"

Command-line flags take precedence over the file.
"""

from __future__ import annotations

import tomllib
from dataclasses import dataclass
from pathlib import Path

DEFAULT_FILENAME = "tods-validate.toml"

_ALLOWED_KEYS = {"ignore", "fail-on"}
_FAIL_ON_VALUES = {"error", "warning"}


class ConfigError(Exception):
    """The configuration file exists but cannot be used."""


@dataclass(frozen=True)
class Config:
    ignore: tuple[str, ...] = ()
    fail_on: str | None = None
    source: str | None = None


def load_config(explicit: Path | None, start_dir: Path | None = None) -> Config:
    """Read configuration from ``explicit``, or discover it in ``start_dir``.

    A missing discovered file is fine (empty config); a missing explicit file
    is the caller's error to surface before calling this.
    """
    path = explicit
    if path is None and start_dir is not None:
        candidate = start_dir / DEFAULT_FILENAME
        if candidate.is_file():
            path = candidate
    if path is None:
        return Config()

    try:
        data = tomllib.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError) as exc:
        raise ConfigError(f"{path} could not be read: {exc}") from exc
    except tomllib.TOMLDecodeError as exc:
        raise ConfigError(f"{path} is not valid TOML: {exc}") from exc

    unknown = set(data) - _ALLOWED_KEYS
    if unknown:
        raise ConfigError(
            f"{path} has unknown setting(s): {', '.join(sorted(unknown))}. "
            f"Allowed settings are: {', '.join(sorted(_ALLOWED_KEYS))}."
        )

    ignore = data.get("ignore", [])
    if not isinstance(ignore, list) or not all(isinstance(i, str) for i in ignore):
        raise ConfigError(f"{path}: 'ignore' must be a list of rule IDs, e.g. [\"TODS-W206\"].")

    fail_on = data.get("fail-on")
    if fail_on is not None and fail_on not in _FAIL_ON_VALUES:
        raise ConfigError(f"{path}: 'fail-on' must be 'error' or 'warning', not {fail_on!r}.")

    return Config(ignore=tuple(ignore), fail_on=fail_on, source=str(path))
