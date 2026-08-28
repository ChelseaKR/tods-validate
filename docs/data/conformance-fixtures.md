# Data card: the rule conformance corpus

**Tier:** L1 (public, non-sensitive)

| Field | Value |
| --- | --- |
| Source | Written by this project. Every fixture under `tests/fixtures/` is hand-authored to trip exactly one rule, or to be clean. No fixture is derived from a real agency's feed; `CONTRIBUTING.md` carries a "no real agency data" house rule. |
| Licence | Apache-2.0, the repository's licence. Redistributed as a release asset by `.github/workflows/release-corpus.yml`. |
| Fetch/refresh cadence | Not fetched. A fixture changes only when a rule changes; `tests/test_conformance.py` enforces a 1:1 rule-to-fixture parity, so a rule cannot ship without one. |
| Fetch timestamp | Not applicable: the corpus is versioned with the repository and released against a tag. |
| Known limitations | **Synthetic.** The fixtures exercise the rules; they are not evidence about how real feeds are shaped, and no claim in this repository treats them as such. `employee_run_dates.txt` and `vehicles.txt` fixtures carry invented identifiers (`emp-100`, `bus-1`, plate `OR-E285104`) that resemble personal and vehicle data in shape only. |
| Retention | Indefinite (L1). |
