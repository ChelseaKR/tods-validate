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

The optional ``[policy]`` table declares the agency's own operational limits,
evaluated as ``LOCAL-P0xx`` findings (see ``local_policy.py`` and ADR 0009):

    [policy]
    max-spread-minutes = 780
    min-break-minutes = { limit = 30, severity = "error" }
    break-event-types = ["Break", "Meal"]

With no ``[policy]`` table nothing about a run changes.

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
from math import isfinite
from pathlib import Path

from .findings import Severity
from .local_policy import (
    BREAK_TYPES_KEY,
    DEFAULT_SEVERITY,
    KIND_FLAG,
    KIND_MINUTES,
    LOCAL_NAMESPACE,
    LOCAL_RULES,
    LOCAL_RULES_BY_ID,
    LOCAL_RULES_BY_KEY,
    LocalPolicy,
    LocalRule,
    PolicyLimit,
)

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
    "max-implied-speed-kph",
    # "severity" is a table (dict), not a list/string, so it is parsed by its
    # own helper (_severity_table) rather than the generic _str_list/_opt_str
    # machinery below. It only needs to be here so the unknown-key check does
    # not reject it.
    "severity",
    # "policy" is a table too, parsed by _policy_table.
    "policy",
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
    # Implied-speed ceiling in km/h for the opt-in OPS-W001 feasibility check.
    # None means the rule's own default applies; see rules.__init__'s
    # DEFAULT_MAX_IMPLIED_SPEED_KPH for why that default is set high.
    max_implied_speed_kph: float | None = None
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
    # The agency's own operational limits from a `[policy]` table, evaluated
    # as LOCAL- rules (local_policy.py, ADR 0009). None when the file has no
    # [policy] table, and then no run is affected in any way.
    local_policy: LocalPolicy | None = None


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
            if rule_id.startswith(LOCAL_NAMESPACE):
                raise ConfigError(
                    f"{where}: [severity] cannot remap {rule_id!r}. A LOCAL- rule takes its "
                    "severity from its own [policy] setting, e.g. "
                    'max-spread-minutes = { limit = 780, severity = "error" }.'
                )
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

    max_implied_speed_kph = _max_implied_speed(data.get("max-implied-speed-kph"), where)

    history_dir = _workspace_history_dir(data.get("workspace"), where)
    severity_remap, severity_acknowledged = _severity_table(data, where)
    local_policy = _policy_table(data.get("policy"), where)

    return Config(
        ignore=_str_list("ignore"),
        fail_on=fail_on,
        enable=_str_list("enable"),
        max_findings=max_findings,
        max_implied_speed_kph=max_implied_speed_kph,
        encoding=encoding,
        spec_version=spec_version,
        profile=profile,
        history_dir=history_dir,
        source=where,
        severity_remap=severity_remap,
        severity_acknowledged=severity_acknowledged,
        local_policy=local_policy,
    )


_LOCAL_ORDER = {rule.id: index for index, rule in enumerate(LOCAL_RULES)}


def _policy_severity(raw: object, where: str) -> Severity:
    if not isinstance(raw, str) or raw.lower() not in _SEVERITY_VALUES:
        raise ConfigError(
            f"{where}: severity must be one of {', '.join(sorted(_SEVERITY_VALUES))}; got {raw!r}."
        )
    return Severity[raw.upper()]


def _policy_limit(rule: LocalRule, raw: object, where: str) -> PolicyLimit | None:
    """One ``[policy]`` limit, or None for a flag set to false. Raises ConfigError.

    A limit is refused rather than clamped for the reason
    ``max-implied-speed-kph`` is: a limit of zero or less would make every unit
    a finding, or none of them, and the run would still exit as though the
    agency's rule had been applied.
    """
    at = f"{where}: [policy] {rule.key!r}"
    severity = DEFAULT_SEVERITY
    value_key = "required" if rule.kind == KIND_FLAG else "limit"
    if isinstance(raw, dict):
        extra = set(raw) - {value_key, "severity"}
        if extra:
            raise ConfigError(
                f"{at} has unknown key(s): {', '.join(sorted(extra))}. "
                f"Allowed keys are: {value_key}, severity."
            )
        if value_key not in raw:
            raise ConfigError(f"{at} is a table with no {value_key!r}.")
        severity = _policy_severity(raw.get("severity", DEFAULT_SEVERITY.name), at)
        raw = raw[value_key]
    if rule.kind == KIND_FLAG:
        if not isinstance(raw, bool):
            raise ConfigError(f"{at} must be true or false, not {raw!r}.")
        return PolicyLimit(rule, 1, severity) if raw else None
    unit = "minutes" if rule.kind == KIND_MINUTES else "days"
    # bool is a subclass of int, so `= true` would otherwise read as 1.
    if isinstance(raw, bool) or not isinstance(raw, int) or raw <= 0:
        raise ConfigError(f"{at} must be a whole number of {unit} greater than zero, not {raw!r}.")
    return PolicyLimit(rule, raw, severity)


def _break_event_types(raw: object, where: str) -> frozenset[str]:
    at = f"{where}: [policy] {BREAK_TYPES_KEY!r}"
    if not isinstance(raw, list) or not all(isinstance(item, str) for item in raw):
        raise ConfigError(f'{at} must be a list of event_type values, e.g. ["Break", "Meal"].')
    cleaned = [item.strip() for item in raw]
    if any(not item for item in cleaned):
        raise ConfigError(
            f"{at} has a blank entry. List the event_type values your export uses for breaks."
        )
    return frozenset(cleaned)


def _policy_table(raw: object, where: str) -> LocalPolicy | None:
    """Parse the optional ``[policy]`` table (ADR 0009), or raise ConfigError.

    Each setting is checked on its own here. The checks that relate settings
    to each other run once every ``extends`` layer has been merged, in
    :func:`_check_policy`, because an inheriting file may set a limit whose
    break vocabulary its parent declares.
    """
    if raw is None:
        return None
    if not isinstance(raw, dict):
        raise ConfigError(f"{where}: 'policy' must be a table, e.g. [policy].")
    allowed = sorted({*LOCAL_RULES_BY_KEY, BREAK_TYPES_KEY})
    limits: list[PolicyLimit] = []
    switched_off: set[str] = set()
    break_types: frozenset[str] | None = None
    for key, value in raw.items():
        if key == BREAK_TYPES_KEY:
            break_types = _break_event_types(value, where)
            continue
        rule = LOCAL_RULES_BY_KEY.get(key)
        if rule is None:
            kebab = key.replace("_", "-")
            hint = f" Did you mean {kebab!r}?" if kebab in allowed else ""
            raise ConfigError(
                f"{where}: [policy] has unknown setting {key!r}.{hint} "
                f"Allowed settings are: {', '.join(allowed)}."
            )
        limit = _policy_limit(rule, value, where)
        if limit is None:
            switched_off.add(rule.id)
        else:
            limits.append(limit)
    if not limits and break_types is None and not switched_off:
        return None
    return LocalPolicy(
        limits=tuple(sorted(limits, key=lambda limit: _LOCAL_ORDER[limit.rule.id])),
        break_event_types=break_types,
        switched_off=frozenset(switched_off),
    )


def _merge_policy(base: LocalPolicy | None, override: LocalPolicy | None) -> LocalPolicy | None:
    """Layer one ``[policy]`` table over another, setting by setting.

    A flag set to false in the overriding file switches off the one it
    inherits; a limit replaces the inherited limit, severity included.
    """
    if override is None:
        return base
    if base is None:
        return override
    merged = {limit.rule.id: limit for limit in base.limits}
    for rule_id in override.switched_off:
        merged.pop(rule_id, None)
    merged.update({limit.rule.id: limit for limit in override.limits})
    return LocalPolicy(
        limits=tuple(sorted(merged.values(), key=lambda limit: _LOCAL_ORDER[limit.rule.id])),
        break_event_types=(
            override.break_event_types
            if override.break_event_types is not None
            else base.break_event_types
        ),
        switched_off=base.switched_off | override.switched_off,
    )


def _check_policy(policy: LocalPolicy | None, where: str) -> LocalPolicy | None:
    """The checks that relate one ``[policy]`` setting to another, after merging.

    Breaks are declared, never guessed (ADR 0009 section 4): the spec lets a
    producer name event types freely, so a rule that has to tell a break from
    work refuses to load without the agency saying which is which. And a break
    vocabulary no rule reads is refused as well, because a setting that does
    nothing is a setting someone believes is doing something.
    """
    if policy is None:
        return None
    run_key = LOCAL_RULES_BY_ID["LOCAL-P001"].key
    break_key = LOCAL_RULES_BY_ID["LOCAL-P003"].key
    configured = {limit.rule.key for limit in policy.limits}
    if break_key in configured and not policy.break_event_types:
        raise ConfigError(
            f"{where}: [policy] {break_key!r} needs a non-empty {BREAK_TYPES_KEY!r}. The TODS "
            "spec lets a producer name event types freely, so the policy has to say which "
            'ones are breaks, e.g. break-event-types = ["Break"].'
        )
    if run_key in configured and policy.break_event_types is None:
        raise ConfigError(
            f"{where}: [policy] {run_key!r} needs {BREAK_TYPES_KEY!r}, so that the policy says "
            "which events are breaks and are left out of worked time. Write "
            "break-event-types = [] if none of your event types is a break."
        )
    if policy.break_event_types is not None and not configured & {run_key, break_key}:
        raise ConfigError(
            f"{where}: [policy] {BREAK_TYPES_KEY!r} is read only by {run_key!r} and "
            f"{break_key!r}, and neither is set, so it would do nothing."
        )
    return policy if policy.limits else None


def _max_implied_speed(raw: object, where: str) -> float | None:
    """Parse ``max-implied-speed-kph``, or raise ConfigError.

    Rejected rather than clamped: a ceiling of zero or below would make every
    measurable pair a finding, and a non-finite one would make none of them a
    finding, and in both cases the run would still exit as though the check had
    been applied. An impossible threshold is a mistake in the config file, so it
    is reported as one (exit 2) instead of being quietly repaired into a
    different check than the one the operator asked for.

    ``bool`` is excluded explicitly because it is a subclass of ``int`` in
    Python, so ``max-implied-speed-kph = true`` would otherwise be accepted as
    a ceiling of 1 km/h.
    """
    if raw is None:
        return None
    if isinstance(raw, bool) or not isinstance(raw, (int, float)):
        raise ConfigError(
            f"{where}: 'max-implied-speed-kph' must be a positive number of km/h, not {raw!r}."
        )
    value = float(raw)
    if not isfinite(value) or value <= 0:
        raise ConfigError(
            f"{where}: 'max-implied-speed-kph' must be a positive, finite number of km/h, "
            f"not {raw!r}."
        )
    return value


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
        max_implied_speed_kph=(
            override.max_implied_speed_kph
            if override.max_implied_speed_kph is not None
            else base.max_implied_speed_kph
        ),
        encoding=override.encoding or base.encoding,
        spec_version=override.spec_version or base.spec_version,
        profile=override.profile or base.profile,
        history_dir=override.history_dir or base.history_dir,
        source=override.source or base.source,
        severity_remap=tuple(severity_map.items()),
        severity_acknowledged=severity_acknowledged,
        local_policy=_merge_policy(base.local_policy, override.local_policy),
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
    config = _load_file(path, set())
    return replace(config, local_policy=_check_policy(config.local_policy, str(path)))
