"""Semantic package diff: what changed in the operational data between two exports.

``diff`` compares two packages by their *findings* and ``drift`` compares a
companion GTFS feed under one package. Neither answers the question a scheduler
actually asks of a new pick: **what changed in the data itself**. This module
does, by primary key.

Two things it deliberately does not do. It produces no findings and passes no
judgement on whether a change is right; and it never reports a file it could not
read as a file whose rows were all deleted. That second one is the whole reason
the ``unreadable`` bucket exists: an unreadable ``run_events.txt`` on the NEW
side has zero rows, and a keyed comparison that trusted the row count would
announce every run in the pick as removed. A read that failed is not a
measurement of anything, so the file is excluded from the comparison and named.

Comparison is keyed on the spec's own primary key for each file
(``schema.TableSpec.primary_key``), so row order is not a difference. A file
whose spec declares no primary key -- every v1.0.0 file except
``runs_pieces.txt`` -- cannot be compared this way and is reported as unkeyed
rather than compared on row position, which would report a single inserted row
as every subsequent row changing. Duplicate primary keys are reported too: a
dict keyed on them would keep the last silently, and the count of rows would
stop matching the count of keys with nothing to say so.
"""

from __future__ import annotations

import secrets
from collections.abc import Iterable
from dataclasses import dataclass, field

from .anonymize import PROTECTED_FIELD_PREFIXES, pseudonym
from .loader import BLOCKING_PROBLEM_CODES, FeedFile, Package
from .schema import SPEC_VERSION, tables_for_version
from .stats import event_minutes

#: The key identifying one run, and the file runs live in.
_RUN_FIELDS = ("service_id", "run_id")
_RUN_EVENTS = "run_events.txt"


@dataclass(frozen=True)
class RowChange:
    """One row added, removed, or changed between OLD and NEW."""

    file: str
    key: tuple[str, ...]
    #: (field, old value, new value), empty for added/removed rows.
    changes: tuple[tuple[str, str, str], ...] = ()

    def key_text(self) -> str:
        return ", ".join(self.key)


@dataclass(frozen=True)
class FileDiff:
    """The comparison of one file, or the reason there was not one."""

    file: str
    key_fields: tuple[str, ...] = ()
    added: tuple[RowChange, ...] = ()
    removed: tuple[RowChange, ...] = ()
    changed: tuple[RowChange, ...] = ()
    #: Primary keys appearing more than once, per side. Reported, never merged.
    duplicate_keys: tuple[tuple[str, tuple[str, ...]], ...] = ()
    #: Set when the file was NOT compared, with why. A file that was not
    #: compared has empty added/removed/changed, and those emptinesses mean
    #: "not measured", not "no change" -- which is what this field exists to
    #: say out loud.
    not_compared: str | None = None
    #: Which kind of not-compared this is: "unreadable" (a read failed, so
    #: there is no measurement and the run exits 2), "unkeyed" (the spec
    #: declares no primary key for the file), or "absent" (it is in neither
    #: package). Only the first is a failure; the other two are facts about
    #: the inputs.
    not_compared_kind: str | None = None

    @property
    def has_changes(self) -> bool:
        return bool(self.added or self.removed or self.changed)


@dataclass(frozen=True)
class RunRollup:
    """How many of one run's events moved."""

    service_id: str
    run_id: str
    added: int = 0
    removed: int = 0
    changed: int = 0


@dataclass(frozen=True)
class MinutesDelta:
    """Revenue and non-revenue minutes on each side, and the difference."""

    old_revenue: int = 0
    new_revenue: int = 0
    old_nonrevenue: int = 0
    new_nonrevenue: int = 0
    #: True when either side's run_events.txt was not compared, so the totals
    #: below describe only what could be read.
    partial: bool = False

    @property
    def revenue_delta(self) -> int:
        return self.new_revenue - self.old_revenue

    @property
    def nonrevenue_delta(self) -> int:
        return self.new_nonrevenue - self.old_nonrevenue


@dataclass(frozen=True)
class PickDiff:
    old_source: str
    new_source: str
    files: tuple[FileDiff, ...] = ()
    runs_added: tuple[tuple[str, str], ...] = ()
    runs_removed: tuple[tuple[str, str], ...] = ()
    run_rollup: tuple[RunRollup, ...] = ()
    minutes: MinutesDelta = field(default_factory=MinutesDelta)

    @property
    def has_changes(self) -> bool:
        return any(f.has_changes for f in self.files) or bool(self.runs_added or self.runs_removed)

    @property
    def not_compared(self) -> tuple[FileDiff, ...]:
        return tuple(f for f in self.files if f.not_compared)

    @property
    def unreadable(self) -> tuple[FileDiff, ...]:
        """Files that exist and could not be read."""
        return tuple(f for f in self.files if f.not_compared_kind == "unreadable")

    @property
    def incomplete(self) -> tuple[FileDiff, ...]:
        """Files whose comparison could not be completed, for any reason.

        Two shapes qualify: a file that could not be read at all, and a file
        holding a duplicate primary key, where rows after the first sharing a
        key were not compared against anything. The CLI exits 2 on either,
        because in both cases it has not established whether the pick changed,
        and reporting that as a clean diff would count a check that could not
        run as a check that passed. Both are already errors in their own right
        under `validate` (TODS-E103 and TODS-E204), so this is not a new
        judgement about the feed, only a refusal to answer over one.
        """
        return tuple(
            f for f in self.files if f.not_compared_kind == "unreadable" or f.duplicate_keys
        )

    @property
    def compared(self) -> tuple[FileDiff, ...]:
        return tuple(f for f in self.files if f.not_compared is None)


def _blocking_problem(feed: FeedFile) -> str | None:
    """The reason this file could not be read, or None if it was read."""
    for problem in feed.problems:
        if problem.code in BLOCKING_PROBLEM_CODES:
            return problem.message
    return None


def _keyed(
    feed: FeedFile, key_fields: tuple[str, ...]
) -> tuple[dict[tuple[str, ...], dict[str, str]], list[tuple[str, ...]]]:
    """Rows by primary key, plus the keys that appeared more than once.

    The first row wins for a duplicated key, and the duplicate is returned
    rather than dropped: which of two rows sharing a key is "the" row is not a
    question this module can answer, and picking silently would make the diff
    depend on file order for exactly the rows most likely to be a mistake
    (TODS-E204 reports the duplication itself).
    """
    rows: dict[tuple[str, ...], dict[str, str]] = {}
    duplicates: list[tuple[str, ...]] = []
    for row in feed.rows:
        key = tuple(row.values.get(name, "") for name in key_fields)
        if key in rows:
            if key not in duplicates:
                duplicates.append(key)
            continue
        rows[key] = dict(row.values)
    return rows, duplicates


def _compare_values(
    old: dict[str, str], new: dict[str, str], key_fields: Iterable[str]
) -> tuple[tuple[str, str, str], ...]:
    """Field-level differences between two rows sharing a primary key.

    Compared over the union of both rows' columns, so a column added to NEW is
    a change rather than something only OLD's header can see. A field absent
    from one side reads as '' -- the same value the loader gives a cell missing
    from a short row -- which is why a column of blanks appearing in NEW is not
    reported as every row changing.
    """
    skip = set(key_fields)
    changes = []
    for name in sorted(set(old) | set(new)):
        if name in skip:
            continue
        before, after = old.get(name, ""), new.get(name, "")
        if before != after:
            changes.append((name, before, after))
    return tuple(changes)


def _diff_file(name: str, old: Package, new: Package, key_fields: tuple[str, ...]) -> FileDiff:
    old_feed, new_feed = old.get(name), new.get(name)
    if old_feed is None and new_feed is None:
        return FileDiff(
            file=name,
            key_fields=key_fields,
            not_compared="absent from both packages",
            not_compared_kind="absent",
        )
    if not key_fields:
        return FileDiff(
            file=name,
            not_compared=(
                "this spec version declares no primary key for the file, so its rows "
                "cannot be matched between the two packages"
            ),
            not_compared_kind="unkeyed",
        )
    for side, feed in (("OLD", old_feed), ("NEW", new_feed)):
        if feed is None:
            continue
        reason = _blocking_problem(feed)
        if reason is not None:
            return FileDiff(
                file=name,
                key_fields=key_fields,
                not_compared=(
                    f"{side} could not be read ({reason}), so nothing here is a "
                    f"comparison; its rows are unknown, not removed"
                ),
                not_compared_kind="unreadable",
            )

    old_rows, old_dupes = _keyed(old_feed, key_fields) if old_feed else ({}, [])
    new_rows, new_dupes = _keyed(new_feed, key_fields) if new_feed else ({}, [])
    added = tuple(RowChange(file=name, key=key) for key in new_rows if key not in old_rows)
    removed = tuple(RowChange(file=name, key=key) for key in old_rows if key not in new_rows)
    changed = []
    for key, old_row in old_rows.items():
        new_row = new_rows.get(key)
        if new_row is None:
            continue
        differences = _compare_values(old_row, new_row, key_fields)
        if differences:
            changed.append(RowChange(file=name, key=key, changes=differences))
    duplicates = tuple([("OLD", key) for key in old_dupes] + [("NEW", key) for key in new_dupes])
    return FileDiff(
        file=name,
        key_fields=key_fields,
        added=added,
        removed=removed,
        changed=tuple(changed),
        duplicate_keys=duplicates,
    )


def _run_of(key: tuple[str, ...], key_fields: tuple[str, ...]) -> tuple[str, str]:
    index = {name: position for position, name in enumerate(key_fields)}
    return (key[index["service_id"]], key[index["run_id"]])


def _rollup(events: FileDiff) -> tuple[RunRollup, ...]:
    """Per-run counts of added, removed and changed events."""
    if events.not_compared or not {"service_id", "run_id"} <= set(events.key_fields):
        return ()
    counts: dict[tuple[str, str], list[int]] = {}
    for bucket, position in ((events.added, 0), (events.removed, 1), (events.changed, 2)):
        for change in bucket:
            run = _run_of(change.key, events.key_fields)
            counts.setdefault(run, [0, 0, 0])[position] += 1
    return tuple(
        RunRollup(service_id=run[0], run_id=run[1], added=a, removed=r, changed=c)
        for run, (a, r, c) in sorted(counts.items())
    )


def _runs(feed: FeedFile | None) -> set[tuple[str, str]]:
    if feed is None:
        return set()
    runs = {(row.values.get("service_id", ""), row.values.get("run_id", "")) for row in feed.rows}
    return {run for run in runs if all(run)}


def _minutes(feed: FeedFile | None) -> tuple[int, int]:
    """(revenue, non-revenue) minutes, by the same rule ``stats`` uses."""
    revenue = nonrevenue = 0
    for row in feed.rows if feed else []:
        minutes = event_minutes(row.values.get("start_time", ""), row.values.get("end_time", ""))
        if row.values.get("trip_id", ""):
            revenue += minutes
        else:
            nonrevenue += minutes
    return revenue, nonrevenue


def analyze_pickdiff(old: Package, new: Package, spec_version: str = SPEC_VERSION) -> PickDiff:
    """Compare two TODS packages by primary key."""
    tables = tables_for_version(spec_version)
    present = [name for name in tables if old.get(name) is not None or new.get(name) is not None]
    files = tuple(
        _diff_file(name, old, new, tuple(tables[name].primary_key or ()))
        for name in sorted(present)
    )

    events = next((f for f in files if f.file == _RUN_EVENTS), None)
    old_events, new_events = old.get(_RUN_EVENTS), new.get(_RUN_EVENTS)
    events_compared = events is not None and events.not_compared is None
    if events_compared:
        old_runs, new_runs = _runs(old_events), _runs(new_events)
        runs_added = tuple(sorted(new_runs - old_runs))
        runs_removed = tuple(sorted(old_runs - new_runs))
        old_revenue, old_nonrevenue = _minutes(old_events)
        new_revenue, new_nonrevenue = _minutes(new_events)
    else:
        # run_events.txt was not compared, so there is no honest count of runs
        # added or removed and no honest minutes total. Reporting zeroes here
        # would read as "the pick is unchanged".
        runs_added = runs_removed = ()
        old_revenue = old_nonrevenue = new_revenue = new_nonrevenue = 0
    return PickDiff(
        old_source=old.source,
        new_source=new.source,
        files=files,
        runs_added=runs_added,
        runs_removed=runs_removed,
        run_rollup=_rollup(events) if events is not None else (),
        minutes=MinutesDelta(
            old_revenue=old_revenue,
            new_revenue=new_revenue,
            old_nonrevenue=old_nonrevenue,
            new_nonrevenue=new_nonrevenue,
            partial=not events_compared,
        ),
    )


def anonymize_pickdiff(report: PickDiff, salt: str | None = None) -> PickDiff:
    """A copy of ``report`` with identifying values pseudonymized.

    The (file, field) pairs are :data:`anonymize.PROTECTED_FIELD_PREFIXES`, the
    same set ``tods-validate anonymize`` protects when it writes a package, so
    the two surfaces cannot drift into protecting different things.

    One salt is drawn per report and used for both sides, which is what makes
    the diff still readable: an employee removed from one run and added to
    another is the same pseudonym in both places. It is random by default, so
    the mapping is irreversible and *not* comparable across two runs of this
    command -- the same posture ``anonymize`` takes. Pass ``salt`` to make two
    reports comparable, knowing that anyone holding the salt can re-derive the
    mapping.
    """
    salt = salt if salt is not None else secrets.token_hex(8)

    def protect(file_name: str, field_name: str, value: str) -> str:
        prefix = PROTECTED_FIELD_PREFIXES.get((file_name, field_name))
        if prefix is None or not value:
            return value
        return pseudonym(prefix, value, salt)

    def protect_row(change: RowChange, key_fields: tuple[str, ...]) -> RowChange:
        return RowChange(
            file=change.file,
            key=tuple(
                protect(change.file, name, value)
                for name, value in zip(key_fields, change.key, strict=False)
            ),
            changes=tuple(
                (name, protect(change.file, name, before), protect(change.file, name, after))
                for name, before, after in change.changes
            ),
        )

    files = tuple(
        FileDiff(
            file=diff.file,
            key_fields=diff.key_fields,
            added=tuple(protect_row(c, diff.key_fields) for c in diff.added),
            removed=tuple(protect_row(c, diff.key_fields) for c in diff.removed),
            changed=tuple(protect_row(c, diff.key_fields) for c in diff.changed),
            duplicate_keys=tuple(
                (
                    side,
                    tuple(
                        protect(diff.file, name, value)
                        for name, value in zip(diff.key_fields, key, strict=False)
                    ),
                )
                for side, key in diff.duplicate_keys
            ),
            not_compared=diff.not_compared,
            not_compared_kind=diff.not_compared_kind,
        )
        for diff in report.files
    )
    # service_id and run_id are not in the protected set (they are schedule
    # identifiers, not people), so the run rollup and the run lists pass
    # through unchanged rather than being pseudonymized into unreadability.
    return PickDiff(
        old_source=report.old_source,
        new_source=report.new_source,
        files=files,
        runs_added=report.runs_added,
        runs_removed=report.runs_removed,
        run_rollup=report.run_rollup,
        minutes=report.minutes,
    )


# --- renderers ---------------------------------------------------------------


def pickdiff_to_dict(report: PickDiff) -> dict[str, object]:
    return {
        "old_source": report.old_source,
        "new_source": report.new_source,
        "has_changes": report.has_changes,
        "unreadable_files": [f.file for f in report.unreadable],
        "incomplete_files": [f.file for f in report.incomplete],
        "runs_added": [list(run) for run in report.runs_added],
        "runs_removed": [list(run) for run in report.runs_removed],
        "run_rollup": [
            {
                "service_id": entry.service_id,
                "run_id": entry.run_id,
                "added": entry.added,
                "removed": entry.removed,
                "changed": entry.changed,
            }
            for entry in report.run_rollup
        ],
        "minutes": {
            "old_revenue": report.minutes.old_revenue,
            "new_revenue": report.minutes.new_revenue,
            "revenue_delta": report.minutes.revenue_delta,
            "old_nonrevenue": report.minutes.old_nonrevenue,
            "new_nonrevenue": report.minutes.new_nonrevenue,
            "nonrevenue_delta": report.minutes.nonrevenue_delta,
            # True when run_events.txt was not compared. The totals above are
            # then zeroes that were never measured, and a consumer that reads
            # them as a delta of nothing is reading a failure as a clean pick.
            "partial": report.minutes.partial,
        },
        "files": [
            {
                "file": diff.file,
                "key_fields": list(diff.key_fields),
                "not_compared": diff.not_compared,
                "not_compared_kind": diff.not_compared_kind,
                "added": [_row_to_dict(c) for c in diff.added],
                "removed": [_row_to_dict(c) for c in diff.removed],
                "changed": [_row_to_dict(c) for c in diff.changed],
                "duplicate_keys": [
                    {"side": side, "key": list(key)} for side, key in diff.duplicate_keys
                ],
            }
            for diff in report.files
        ],
    }


def _row_to_dict(change: RowChange) -> dict[str, object]:
    return {
        "key": list(change.key),
        "changes": [
            {"field": name, "old": before, "new": after} for name, before, after in change.changes
        ],
    }


def _minutes_lines(report: PickDiff) -> list[str]:
    minutes = report.minutes
    if minutes.partial:
        return [
            "Revenue/non-revenue minutes: not measured "
            "(run_events.txt was not compared; see the notes above)"
        ]
    return [
        f"Revenue minutes: {minutes.old_revenue} -> {minutes.new_revenue} "
        f"({minutes.revenue_delta:+d})",
        f"Non-revenue minutes: {minutes.old_nonrevenue} -> {minutes.new_nonrevenue} "
        f"({minutes.nonrevenue_delta:+d})",
    ]


def _closing_line(report: PickDiff) -> str:
    """What a report with no differences is entitled to claim.

    Three different sentences, because they are three different claims: every
    file compared and nothing moved; some files not compared at all; and a
    comparison that ran but could not finish. Collapsing them into one "No
    differences." is how a failed read becomes a clean pick.
    """
    if report.incomplete:
        return (
            "No differences among the rows that could be compared, which is "
            "not the same claim as no differences."
        )
    if report.not_compared:
        return f"No differences in the {len(report.compared)} file(s) that were compared."
    return "No differences."


def _note_lines(report: PickDiff) -> list[str]:
    """Files that were not compared, and keys that were only partly compared."""
    lines = [f"! {d.file}: NOT COMPARED - {d.not_compared}" for d in report.not_compared]
    for diff in report.files:
        for side, key in diff.duplicate_keys:
            lines.append(
                f"! {diff.file}: {side} has more than one row with primary key "
                f"({', '.join(key)}); the first was compared and the rest were not"
            )
    return lines


def _run_lines(report: PickDiff) -> list[str]:
    return [f"+ run {service}/{run}" for service, run in report.runs_added] + [
        f"- run {service}/{run}" for service, run in report.runs_removed
    ]


def _file_lines(diff: FileDiff) -> list[str]:
    lines = [
        f"{diff.file}: +{len(diff.added)} -{len(diff.removed)} ~{len(diff.changed)} "
        f"(key: {', '.join(diff.key_fields)})"
    ]
    lines += [f"  + {change.key_text()}" for change in diff.added]
    lines += [f"  - {change.key_text()}" for change in diff.removed]
    for change in diff.changed:
        lines.append(f"  ~ {change.key_text()}")
        lines += [
            f"      {name}: {before!r} -> {after!r}" for name, before, after in change.changes
        ]
    return lines


def _rollup_lines(report: PickDiff) -> list[str]:
    if not report.run_rollup:
        return []
    return ["Events changed per run:"] + [
        f"  {entry.service_id}/{entry.run_id}: +{entry.added} -{entry.removed} ~{entry.changed}"
        for entry in report.run_rollup
    ]


def render_pickdiff_text(report: PickDiff) -> str:
    body: list[str] = list(_note_lines(report))
    body += _run_lines(report)
    for diff in report.files:
        if diff.not_compared is None and diff.has_changes:
            body += _file_lines(diff)
    body += _rollup_lines(report)
    body += _minutes_lines(report)
    if not report.has_changes:
        body.append(_closing_line(report))
    header = f"tods-validate pickdiff: {report.old_source} -> {report.new_source}"
    return "\n".join([header] + [f"  {line}" for line in body])


def _markdown_run_section(report: PickDiff) -> list[str]:
    if not (report.runs_added or report.runs_removed):
        return []
    lines = ["## Runs", ""]
    lines += [f"- added: `{service}` / `{run}`" for service, run in report.runs_added]
    lines += [f"- removed: `{service}` / `{run}`" for service, run in report.runs_removed]
    return lines + [""]


def _markdown_row_section(changed_files: list[FileDiff]) -> list[str]:
    if not changed_files:
        return []
    lines = [
        "## Rows",
        "",
        "| File | Added | Removed | Changed | Key |",
        "| --- | ---: | ---: | ---: | --- |",
    ]
    for diff in changed_files:
        lines.append(
            f"| `{diff.file}` | {len(diff.added)} | {len(diff.removed)} | "
            f"{len(diff.changed)} | {', '.join(diff.key_fields)} |"
        )
    lines.append("")
    for diff in changed_files:
        if not diff.changed:
            continue
        lines += [f"### `{diff.file}` field changes", ""]
        for change in diff.changed:
            lines.append(f"- `{change.key_text()}`")
            lines += [
                f"  - `{name}`: `{before}` -> `{after}`" for name, before, after in change.changes
            ]
        lines.append("")
    return lines


def _markdown_rollup_section(report: PickDiff) -> list[str]:
    if not report.run_rollup:
        return []
    lines = [
        "## Events changed per run",
        "",
        "| Run | Added | Removed | Changed |",
        "| --- | ---: | ---: | ---: |",
    ]
    for entry in report.run_rollup:
        lines.append(
            f"| `{entry.service_id}` / `{entry.run_id}` | {entry.added} | "
            f"{entry.removed} | {entry.changed} |"
        )
    return lines + [""]


def render_pickdiff_markdown(report: PickDiff) -> str:
    lines = ["# Package diff", "", f"`{report.old_source}` -> `{report.new_source}`", ""]
    for diff in report.not_compared:
        lines += [f"> **{diff.file} was not compared.** {diff.not_compared}", ""]
    for diff in report.files:
        for side, key in diff.duplicate_keys:
            lines += [
                f"> **`{diff.file}` has a duplicate primary key.** {side} has more than "
                f"one row keyed `{', '.join(key)}`; the first was compared and the rest "
                f"were not.",
                "",
            ]
    lines += _markdown_run_section(report)
    lines += _markdown_row_section(
        [f for f in report.files if f.not_compared is None and f.has_changes]
    )
    lines += _markdown_rollup_section(report)
    lines += ["## Totals", ""]
    lines += [f"- {line}" for line in _minutes_lines(report)]
    if not report.has_changes:
        lines += ["", _closing_line(report)]
    return "\n".join(lines).rstrip("\n") + "\n"
