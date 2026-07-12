"""The single gating decision shared by validate, diff, batch, and testing.

Every entry point ends the same way: findings come out of the rules, some are
withheld by ``--ignore`` (command line or config file), a baseline may narrow
what's left to only what's new, and what remains decides pass/fail against
``--fail-on``. That decision used to be hand-rolled once per subcommand (and a
fourth time in :mod:`tods_validate.testing`); duplicated policy logic drifts
apart one flag at a time. This module is the one place it lives now.
"""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass

from .baseline import Identity, new_findings
from .config import Config
from .findings import Finding, Severity
from .report import summarize

# Ordered so a threshold comparison ("does this severity meet or exceed the
# gate?") is a single Severity comparison rather than a chain of `or`s.
_FAIL_ON_SEVERITY: dict[str, Severity] = {
    "info": Severity.INFO,
    "warning": Severity.WARNING,
    "error": Severity.ERROR,
}


@dataclass(frozen=True)
class GateResult:
    """The outcome of applying a :class:`GatingPolicy` to a list of findings."""

    # Findings surviving --ignore; what a report should show.
    kept: list[Finding]
    # Findings --ignore withheld, for a disclosure message admitting what a
    # clean-looking report did not report.
    suppressed_ignored: list[Finding]
    # `kept`, narrowed to what's new since the baseline when one was given;
    # otherwise the same list as `kept`. This is what the exit code is judged on.
    gating: list[Finding]
    # Severity counts of `gating`.
    counts: dict[Severity, int]
    # True when `gating` contains a finding at or above the effective fail-on
    # severity.
    failed: bool


@dataclass(frozen=True)
class GatingPolicy:
    """The exit-code and suppression policy for one validation run.

    ``fail_on`` is "error" (the default), "warning", or "info": the minimum
    severity, among the gating findings, that fails the run. ``ignore`` is the
    set of rule IDs whose findings are withheld from both the gate and the
    report. ``baseline_identities``, when given, further narrows the gating
    findings to those not present in a prior run (see
    :func:`tods_validate.baseline.load_baseline_identities`); it never affects
    ``kept``, since a baseline changes what fails the build, not what a report
    admits finding.
    """

    fail_on: str
    ignore: frozenset[str]
    baseline_identities: set[Identity] | None = None

    @classmethod
    def from_config(
        cls,
        *,
        fail_on: str | None,
        config: Config,
        ignore_ids: Iterable[str] = (),
        baseline_identities: set[Identity] | None = None,
    ) -> GatingPolicy:
        """Resolve CLI flags against a loaded :class:`~tods_validate.config.Config`.

        Centralizes the precedence every subcommand shares: an explicit
        ``--fail-on``/``--ignore`` on the command line wins; otherwise the
        config file applies (which may already have a ``--profile`` layered
        beneath it, see :mod:`tods_validate.config`); otherwise the default is
        "error" with nothing ignored.
        """
        effective_fail_on = fail_on or config.fail_on or "error"
        ignore = frozenset(ignore_ids) | frozenset(config.ignore)
        return cls(
            fail_on=effective_fail_on, ignore=ignore, baseline_identities=baseline_identities
        )

    def _threshold(self) -> Severity:
        try:
            return _FAIL_ON_SEVERITY[self.fail_on]
        except KeyError:
            raise ValueError(
                f"fail_on must be one of {sorted(_FAIL_ON_SEVERITY)}, got {self.fail_on!r}"
            ) from None

    def apply(self, findings: Iterable[Finding]) -> GateResult:
        """Partition ``findings`` and decide pass/fail in one consistent pass."""
        all_findings = list(findings)
        kept = [f for f in all_findings if f.rule_id not in self.ignore]
        suppressed_ignored = [f for f in all_findings if f.rule_id in self.ignore]
        gating = (
            new_findings(kept, self.baseline_identities)
            if self.baseline_identities is not None
            else kept
        )
        counts = summarize(gating)
        threshold = self._threshold()
        failed = any(severity >= threshold for severity in counts)
        return GateResult(
            kept=kept,
            suppressed_ignored=suppressed_ignored,
            gating=gating,
            counts=dict(counts),
            failed=failed,
        )


__all__ = ["GatingPolicy", "GateResult"]
