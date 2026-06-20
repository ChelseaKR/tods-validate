"""Optional configuration file support.

A ``tods-validate.toml`` in the working directory (or a file passed via
``--config``) lets an agency encode local policy once instead of repeating
command-line flags in every CI job:

    profile = "strict"
    ignore = ["TODS-W206", "TODS-I108"]
    fail-on = "warning"
    enable = ["coverage"]

Command-line flags take precedence over the file, which takes precedence over
its named ``profile``. A config may also ``extends = "../base.toml"`` to inherit
a shared house policy; the local file overrides the inherited one.
"""

from __future__ import annotations

import tomllib
from dataclasses import dataclass, replace
from pathlib import Path

DEFAULT_FILENAME = "tods-validate.toml"

_ALLOWED_KEYS = {
    "ignore",
    "fail-on",
    "enable",
    "max-findings",
    "encoding",
    "spec-version",
    "profile",
    "extends",
}
_FAIL_ON_VALUES = {"error", "warning"}


# Named presets. A profile sets defaults that the config file and command line
# can still override. Kept deliberately small and conservative.
PROFILES: dict[str, dict[str, object]] = {
    "default": {},
    "strict": {"fail-on": "warning", "enable": ["coverage", "advisory"]},
    "lenient": {"fail-on": "error", "ignore": ["TODS-W206", "TODS-W107"]},
}


class ConfigError(Exception):
    """The configuration file exists but cannot be used."""


@dataclass(frozen=True)
class Config:
    ignore: tuple[str, ...] = ()
    fail_on: str | None = None
    enable: tuple[str, ...] = ()
    max_findings: int | None = None
    encoding: str | None = None
    spec_version: str | None = None
    profile: str | None = None
    source: str | None = None


def _parse_data(data: dict[str, object], where: str) -> Config:
    unknown = set(data) - _ALLOWED_KEYS
    if unknown:
        raise ConfigError(
            f"{where} has unknown setting(s): {', '.join(sorted(unknown))}. "
            f"Allowed settings are: {', '.join(sorted(_ALLOWED_KEYS))}."
        )

    def _str_list(key: str) -> tuple[str, ...]:
        value = data.get(key, [])
        if not isinstance(value, list) or not all(isinstance(i, str) for i in value):
            hint = ' of rule IDs, e.g. ["TODS-W206"]' if key == "ignore" else " of strings"
            raise ConfigError(f"{where}: '{key}' must be a list{hint}.")
        return tuple(value)

    def _opt_str(key: str, allowed: set[str] | None = None) -> str | None:
        value = data.get(key)
        if value is None:
            return None
        if not isinstance(value, str) or (allowed is not None and value not in allowed):
            choices = f" (one of {', '.join(sorted(allowed))})" if allowed else ""
            raise ConfigError(f"{where}: '{key}' must be a string{choices}, not {value!r}.")
        return value

    fail_on = _opt_str("fail-on", _FAIL_ON_VALUES)
    encoding = _opt_str("encoding")
    spec_version = _opt_str("spec-version")

    raw_profile = data.get("profile")
    if raw_profile is not None and raw_profile not in PROFILES:
        raise ConfigError(
            f"{where}: unknown profile {raw_profile!r}. Choose from: {', '.join(sorted(PROFILES))}."
        )
    profile = raw_profile if isinstance(raw_profile, str) else None

    raw_max = data.get("max-findings")
    if raw_max is not None and (not isinstance(raw_max, int) or raw_max < 0):
        raise ConfigError(f"{where}: 'max-findings' must be a non-negative integer.")
    max_findings = raw_max if isinstance(raw_max, int) else None

    return Config(
        ignore=_str_list("ignore"),
        fail_on=fail_on,
        enable=_str_list("enable"),
        max_findings=max_findings,
        encoding=encoding,
        spec_version=spec_version,
        profile=profile,
        source=where,
    )


def _merge(base: Config, override: Config) -> Config:
    """Layer ``override`` on top of ``base``; non-empty override values win."""
    return Config(
        ignore=tuple(dict.fromkeys(base.ignore + override.ignore)),
        fail_on=override.fail_on or base.fail_on,
        enable=tuple(dict.fromkeys(base.enable + override.enable)),
        max_findings=(
            override.max_findings if override.max_findings is not None else base.max_findings
        ),
        encoding=override.encoding or base.encoding,
        spec_version=override.spec_version or base.spec_version,
        profile=override.profile or base.profile,
        source=override.source or base.source,
    )


def _profile_config(name: str) -> Config:
    return _parse_data(PROFILES[name], f"profile {name!r}")


def _load_file(path: Path, _seen: set[Path]) -> Config:
    resolved = path.resolve()
    if resolved in _seen:
        raise ConfigError(f"{path}: circular 'extends' chain.")
    _seen.add(resolved)

    try:
        data = tomllib.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError) as exc:
        raise ConfigError(f"{path} could not be read: {exc}") from exc
    except tomllib.TOMLDecodeError as exc:
        raise ConfigError(f"{path} is not valid TOML: {exc}") from exc

    config = _parse_data(data, str(path))

    extends = data.get("extends")
    if extends is not None:
        if not isinstance(extends, str):
            raise ConfigError(f"{path}: 'extends' must be a path string.")
        parent_path = (path.parent / extends).resolve()
        if not parent_path.is_file():
            raise ConfigError(f"{path}: extends target {extends!r} does not exist.")
        config = _merge(_load_file(parent_path, _seen), config)

    # A named profile is the lowest layer, below the file's own settings.
    if config.profile is not None:
        config = _merge(_profile_config(config.profile), replace(config, profile=config.profile))
    return config


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
    return _load_file(path, set())
