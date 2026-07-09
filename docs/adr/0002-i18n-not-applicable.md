# 0002 — Internationalization declared not applicable

- Status: accepted (backfilled 2026-07-09; declared 2026-06-30 in docs/I18N.md)
- Date: 2026-07-09

## Context

The portfolio i18n standard requires either externalized, translatable
user-facing strings or an explicit N/A declaration. This tool emits
TODS-E/W/I findings for feed producers and CI systems: developer-facing
English, no localized dates, numbers, or currency rendered to an end user.
Finding messages are also a stability surface (golden files, baselines,
annotation parsers), so translating them would break consumers for an
audience that has not asked for it.

## Decision

Declare i18n N/A, per `docs/I18N.md` (out-of-scope conditions a, b, c of the
standard). An enforcing CI gate (`scripts/check_i18n.py`, the `i18n` job)
keeps the declaration honest by failing if localization surfaces appear.

Revisit trigger: a real request from a non-English-speaking agency or
working-group direction toward localized findings. The entry path is
gettext `_()` wrapping for Python and `intl.formatMessage` for the VS Code
extension, at which point the standard's AUTO gates apply.

## Consequences

- Finding text can be treated as a stable contract.
- The README conformance table row for i18n points at a reasoned
  declaration instead of a bare N/A.
- If the revisit trigger fires, the migration is a scoped, known quantity
  rather than a surprise.
