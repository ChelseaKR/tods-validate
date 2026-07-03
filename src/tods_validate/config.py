"""Optional configuration file support.

A ``tods-validate.toml`` in the working directory (or a file passed via
``--config``) lets an agency encode local policy once instead of repeating
command-line flags in every CI job:

    profile = "strict"
    ignore = ["TODS-W206", "TODS-I108"]
    fail-on = "warning"
    enable = ["coverage"]

    [workspace]
    history-dir = ".tods-history"

    [severity]
    "TODS-W316" = "error"
    "TODS-E205" = {level = "warning", acknowledged = true}

Command-line flags take precedence over the file, which takes precedence over
its named ``profile``. A config may also ``extends = "../base.toml"`` to inherit
a shared house policy; the local file overrides the inherited one.

The ``[workspace]`` table configures the run-history ledger (see
``workspace.py``): ``history-dir`` sets where ``batch`` appends run summaries
and where ``trend`` reads them from, so CI does not need to repeat
``--history`` on every invocation.

The optional ``[severity]`` table remaps individual rules to a different
severity than the spec declares (a rule ID key, mapped to a severity string,
or an inline table with ``level`` and ``acknowledged``). Every remapped
finding is disclosed in every report format: this is a non-negotiable honesty
constraint, not a display option. Downgrading a rule that the spec declares
ERROR requires ``acknowledged = true``, so silently muting a spec violation
is impossible by accident.
"""

from __future__ import annotations

import tomllib
from dataclasses import dataclass, replace
from pathlib import Path

from .findings import Severity

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
    "workspace",
    # "severity" is a table (dict), not a list/string, so it is parsed by its
    # own helper (_severity_table) rather than the generic _str_list/_opt_str
    # machinery below. It only needs to be here so the unknown-key check does
    # not reject it.
    "severity",
}
_WORKSPACE_KEYS = {"history-dir"}
_FAIL_ON_VALUES = {"error", "warning"}
_SEVERITY_VALUES = {"error", "warning", "info"}
_SEVERITY_TABLE_KEYS = {"level", "acknowledged"}


# Named presets. A profile sets defaults that the config file and command line
# can still override. Kept deliberately small and conservative.
PROFILES: dict[str, dict[str, object]] = {
    "default": {},
    "strict": {"fail-on": "warning", "enable": ["coverage", "advisory"]},
    "lenient": {"fail-on": "error", "ignore": ["TODS-W206", "TODS-W107"]},
    # For a downstream CAD/AVL consumer deciding whether to ingest a feed at
    # all (a go/no-go gate, not an authoring workflow): at least as strict as
    # "strict", with no ignores, so nothing is silently let through.
    "ingest-ready": {"fail-on": "warning", "enable": ["coverage", "advisory"]},
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
    history_dir: str | None = None
    source: str | None = None
    # A `[severity]` table remapping rule_id -> new severity name ("ERROR",
    # "WARNING", or "INFO"). Applied after rule execution (see runner.py);
    # every remap must be disclosed in every report format (see report.py).
    severity_remap: tuple[tuple[str, str], ...] = ()
    # Rule IDs whose remap in severity_remap carried `acknowledged = true`.
    # Required (and enforced at parse time) when the remap downgrades a rule
    # the spec declares ERROR to a lower severity.
    severity_acknowledged: frozenset[str] = frozenset()


def _severity_table(  # noqa: C901 - validates several user-facing config shapes
    data: dict[str, object], where: str
) -> tuple[tuple[tuple[str, str], ...], frozenset[str]]:
    """Parse and validate the optional ``[severity]`` remap table.

    Each key is a rule ID; each value is either a severity string or an
    inline table ``{level = "...", acknowledged = true}``. Unknown rule IDs
    are rejected, as is downgrading an ERROR-band rule without
    ``acknowledged = true``.
    """
    raw = data.get("severity")
    if raw is None:
        return (), frozenset()
    if not isinstance(raw, dict):
        raise ConfigError(f"{where}: 'severity' must be a table, e.g. [severity].")

    # Imported lazily: rules/__init__.py does not import config.py, so this
    # is not a real cycle, but keeping it local avoids paying the rule-module
    # import cost (and any future accidental cycle) for configs that never
    # touch [severity].
    from .rules import all_rules

    known = {r.id: r.severity for r in all_rules()}
    remap: list[tuple[str, str]] = []
    acknowledged: set[str] = set()

    for rule_id, value in raw.items():
        if rule_id not in known:
            raise ConfigError(
                f"{where}: [severity] has unknown rule ID {rule_id!r}. "
                "See docs/rules.md for the rule catalog."
            )

        if isinstance(value, str):
            level_raw: object = value
            acked = False
        elif isinstance(value, dict):
            extra = set(value) - _SEVERITY_TABLE_KEYS
            if extra:
                raise ConfigError(
                    f"{where}: [severity.{rule_id!r}] has unknown key(s): "
                    f"{', '.join(sorted(extra))}."
                )
            level_raw = value.get("level")
            acked = bool(value.get("acknowledged", False))
        else:
            raise ConfigError(
                f"{where}: [severity.{rule_id!r}] must be a severity string or a table "
                "with a 'level' key."
            )

        if not isinstance(level_raw, str) or level_raw.lower() not in _SEVERITY_VALUES:
            raise ConfigError(
                f"{where}: [severity.{rule_id!r}] level must be one of "
                f"{', '.join(sorted(_SEVERITY_VALUES))}; got {level_raw!r}."
            )
        level = level_raw.upper()

        original = known[rule_id]
        if original is Severity.ERROR and Severity[level] < Severity.ERROR and not acked:
            raise ConfigError(
                f"{where}: [severity.{rule_id!r}] downgrades {rule_id} from the spec's "
                f"ERROR severity to {level}. Set acknowledged = true to confirm this is "
                "intentional local policy."
            )

        remap.append((rule_id, level))
        if acked:
            acknowledged.add(rule_id)

    return tuple(remap), frozenset(acknowledged)


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

    history_dir = _workspace_history_dir(data.get("workspace"), where)
    severity_remap, severity_acknowledged = _severity_table(data, where)
    history_dir = _workspace_history_dir(data.get("workspace"), where)

    return Config(
        ignore=_str_list("ignore"),
        fail_on=fail_on,
        enable=_str_list("enable"),
        max_findings=max_findings,
        encoding=encoding,
        spec_version=spec_version,
        profile=profile,
        history_dir=history_dir,
        source=where,
        severity_remap=severity_remap,
        severity_acknowledged=severity_acknowledged,
    )


def _workspace_history_dir(raw: object, where: str) -> str | None:
    """Pull ``history-dir`` out of an optional ``[workspace]`` table."""
    if raw is None:
        return None
    if not isinstance(raw, dict):
        raise ConfigError(f"{where}: 'workspace' must be a table, e.g. [workspace].")
    unknown = set(raw) - _WORKSPACE_KEYS
    if unknown:
        raise ConfigError(
            f"{where}: [workspace] has unknown setting(s): {', '.join(sorted(unknown))}. "
            f"Allowed settings are: {', '.join(sorted(_WORKSPACE_KEYS))}."
        )
    value = raw.get("history-dir")
    if value is None:
        return None
    if not isinstance(value, str):
        raise ConfigError(f"{where}: [workspace] 'history-dir' must be a path string.")
    return value


def _merge(base: Config, override: Config) -> Config:
    """Layer ``override`` on top of ``base``; non-empty override values win."""
    # dict.fromkeys-style merge, keyed by rule_id: override's remap for a
    # given rule replaces base's entirely (including its acknowledged flag),
    # rather than the two layers' settings for that one rule mixing.
    severity_map = dict(base.severity_remap)
    severity_map.update(override.severity_remap)
    overridden_ids = {rule_id for rule_id, _ in override.severity_remap}
    severity_acknowledged = (base.severity_acknowledged - overridden_ids) | (
        override.severity_acknowledged
    )
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
        history_dir=override.history_dir or base.history_dir,
        source=override.source or base.source,
        severity_remap=tuple(severity_map.items()),
        severity_acknowledged=severity_acknowledged,
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
