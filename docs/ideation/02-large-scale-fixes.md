# Large-scale fixes

_Drafted 2026-07-01. Net-new: none of these appear in `docs/roadmap.md` or
`docs/RESEARCH-ROADMAP.md`; overlaps are cited by ID and extended, not
repeated._

Effort tiers: **S** ≤ a day · **M** a few days · **L** one to two weeks ·
**XL** multi-week.

---

## FIX-01 — One supplement-evaluation engine, proven equivalent

**Pitch:** collapse the duplicated supplement logic in
`gtfs_companion.merge_supplement()` and `merge._merge_file()` into one shared
module, with a differential test that the validation view and the
materialized merge can never disagree.

**Why it matters:** these two functions independently implement the spec's
most delicate section (PK match → delete/update/add). If they drift, the
validator could pass a reference that the merged feed then breaks — the exact
failure the tool exists to prevent. Impact lands on vendors (P7) and CAD/AVL
consumers (P10) who treat "validates clean" as "safe to merge."

**Shape of the work:** extract a `supplement.py` with a single
`apply_supplement(base_rows, supplement_rows, pk) -> EffectiveTable` that
also returns per-key provenance (updated/added/deleted/skipped) so
`merge.MergeStats` and `CompanionGTFS.base_keys` both derive from it.
Property-based test (see FIX-13) that for arbitrary generated supplements,
`build_companion()`'s effective keys equal the keys serialized by
`merge_feeds()`.

**Effort:** M. **Risks/deps:** behavior-preserving refactor across the two
most-tested paths; land before FIX-03 touches the same files. **Excellent
looks like:** one implementation, a CI property test asserting equivalence on
≥10k generated cases, zero conformance-corpus diffs before/after.

---

## FIX-02 — Validation assurance manifest ("what did NOT run")

**Pitch:** every report states which rules ran, which were skipped, and why —
so a green run carries its own scope statement.

**Why it matters:** today `rules/__init__.py:validate()` silently drops
`needs_gtfs` rules when `context.gtfs is None`, and TODS-W302 only warns for
run_events' dependencies — `vehicle_assignments.txt` with no companion
trips/calendar loses E205/E311/E312 with no trace. For a tool whose Markdown
report is pitched as a "citable compliance artifact" (`--stamp`), an
unqualified green is an honesty bug, not a missing feature. This is the
single most on-ethos fix available.

**Shape of the work:** `validate()` returns (findings, `RunCoverage`) —
per-rule status: `ran` / `skipped:needs_gtfs` / `skipped:disabled` /
`skipped:ignored`. Surface it as an additive `coverage` block in
`render_json()` (report schema 1.2.0, add-only per the stated policy), one
summary line in text/Markdown ("13 cross-reference rules skipped: no
companion GTFS"), and SARIF `invocations`. Extend W302's dependency table to
cover vehicle_assignments and supplements while in there.

**Effort:** M. **Risks/deps:** report-schema version bump; golden-file test
updates. **Excellent looks like:** it is impossible to produce a report that
does not disclose skipped checks; `docs/report.schema.json` documents the
block; the `--stamp` footer includes rule-set coverage counts.

---

## FIX-03 — Shared derived state on `ValidationContext`

**Pitch:** compute the expensive derived views (parsed run events, per-run
groupings, parsed times, run-pair sets) once per validation instead of once
per rule.

**Why it matters:** `semantics.py` rebuilds `_events(context)` (with
`parse_time` regex parsing of every time value) separately in E401, E402,
W403, W404, W409, and `coverage.py` re-derives runs again; `references.py`
re-walks run_events per rule. At fixture scale it is invisible; at the
100k-row scale `scripts/benchmark.py` targets, it is an O(rules × rows)
multiplier on the hot path.

**Shape of the work:** turn `ValidationContext` into a lazily-caching object
(`functools.cached_property` on a non-frozen dataclass): `.events`,
`.events_by_run`, `.run_pairs`. Rules keep their current signatures; the
private helpers in `semantics.py`/`references.py` delegate to the context.
Benchmark before/after with `scripts/benchmark.py` and publish the numbers
(extends the intent of R9 without depending on real feeds).

**Effort:** M. **Risks/deps:** mutation-testing config (`pyproject.toml`
`[tool.mutmut]`) mutates `rules/*` — keep derived-state code out of the
mutated set or accept new survivors; sequence with FIX-01. **Excellent looks
like:** ≥3× throughput on the synthetic benchmark at 100k run events, no
behavior diffs on the corpus, and the benchmark result committed in docs.

---

## FIX-04 — Memory model for production-scale packages

**Pitch:** stop holding a 512 MiB file as a list of per-row
`dict[str, str]`; move `loader.Row` to a compact representation and give the
x1xx/x2xx rules a streaming path.

**Why it matters:** the loader's own safety limits (`MAX_FILE_BYTES = 512
MiB`, 2 GiB total in `loader.py`) advertise a scale the current
representation cannot reasonably hold: dict-per-row costs roughly an order of
magnitude over the raw bytes. First real agency feed that is big will make
the tool look untested — and it is the known unknown R1 will deliver.

**Shape of the work:** `Row.values` becomes a view over a tuple keyed by the
file's header index (a small `RowView` mapping class keeps the
`row.values.get(name, "")` API used by every rule); measure with
`tracemalloc` in the benchmark. Optionally, a second pass lets field-level
rules stream rows without materializing files that no cross-file rule needs.

**Effort:** L (XL if streaming). **Risks/deps:** touches every rule's data
access; do after FIX-03 so the derived views absorb most access patterns.
**Excellent looks like:** peak RSS ≤ 3× input size on the benchmark feed;
documented memory ceiling in `SECURITY.md` alongside the existing limits.

---

## FIX-05 — Structured finding parameters end to end

**Pitch:** add machine-readable fields to `Finding` (offending value,
expected/allowed values, referenced ID, context row keys) and thread them
through JSON, SARIF, LSP, and suggestions.

**Why it matters:** every downstream consumer currently parses English
prose: dashboards regex the message, `baseline.py` uses the message as
identity, SARIF results carry no structured context, and the LSP quick-fix
map (`lsp.py`) special-cases two rules because it cannot see values.
gtfs-validator's notices carry typed context fields; parity matters if this
corpus is to be adopted upstream (E2).

**Shape of the work:** additive `data: Mapping[str, str] | None` on
`Finding` (`findings.py`), populated rule by rule starting with the reference
band (E307–E314 already compute the value and target). Emit under `data` in
`to_dict()` (schema 1.2.0), as SARIF `result.properties`, and enrich
`render_sarif()` descriptors from `REGISTRY` (title → `shortDescription`,
description → `fullDescription`, spec link → `helpUri` — the registry data is
already there and currently dropped). Surface suggestions in machine form
too: a `suggestions` array behind `--suggest` in JSON output, which today is
text/Markdown-only by design.

**Effort:** M–L (mechanical but wide). **Risks/deps:** schema bump; enables
FIX-07 and future i18n; coordinate with FIX-02's schema change so 1.2.0 ships
once. **Excellent looks like:** every ERROR-band finding carries `data`;
SARIF validates against the 2.1.0 schema with populated descriptors; one
dashboard-style consumer test asserts no message parsing is needed.

---

## FIX-06 — One gating policy for validate / diff / batch / testing

**Pitch:** extract the exit-code and suppression logic into a single
`GatingPolicy` used by all subcommands and the pytest helpers.

**Why it matters:** observed inconsistency in `cli.py`: `validate` honors
config file, `--ignore`, profiles, and `--baseline`; `diff` and `batch`
honor none of them. An agency that encodes house policy in
`tods-validate.toml` (the whole point of `config.py`) gets different verdicts
from `validate` and `batch` on the same feed. `testing.assert_feed_valid`
re-implements the threshold+ignore logic a third time.

**Shape of the work:** `policy.py` with
`GatingPolicy(fail_on, ignore, baseline)` and `apply(findings) ->
GateResult`; `validate`, `diff`, `batch`, and `testing.py` all consume it;
`batch` and `diff` gain `--config`/`--ignore` for free. Document the
precedence table once.

**Effort:** M. **Risks/deps:** exit codes are a stated contract — golden
tests for every subcommand × policy combination before refactoring.
**Excellent looks like:** a parametrized test proving all four surfaces give
identical verdicts for identical inputs and policy.

✅ Implemented 2026-07-03 (branch: `roadmap/fix-06-one-gatingpolicy-for-validate-dif`)
— `src/tods_validate/policy.py` adds `GatingPolicy`/`GateResult`;
`GatingPolicy.from_config` centralizes the `--fail-on`/config/profile
precedence. `validate`, `diff`, `batch`, and
`testing.assert_feed_valid` all gate through `policy.apply()`; `diff` and
`batch` gained `--config`/`--ignore` (and `validate` keeps `--baseline`).
`tests/test_policy.py` parametrizes all four surfaces over the same
findings × policy inputs and asserts identical verdicts, plus golden
exit-code assertions per subcommand.

---

## FIX-07 — Content-anchored baseline fingerprints

**Pitch:** replace the row-number-based finding identity with a fingerprint
built from stable content (rule ID + file + field + the row's primary-key
values + offending value).

**Why it matters:** `baseline.finding_identity()` is (rule_id, pointer,
message); the pointer embeds the line number and the message embeds it again,
so inserting one row at the top of `run_events.txt` marks every existing
finding "new" and every baseline entry "fixed." That defeats `--baseline`'s
purpose (fail only on regressions) exactly when feeds are regenerated each
pick — the normal case.

**Shape of the work:** with FIX-05's `data` in place, fingerprint =
SHA-256 of (rule_id, file, field, sorted PK values from `data`, offending
value), with the current identity kept as fallback for old reports.
`diff_findings()` gains a fuzzy "moved" category. Version the baseline format.

**Effort:** M. **Risks/deps:** depends on FIX-05; heuristic honesty — docs
must state that renumbered *and* revalued rows still churn. **Excellent looks
like:** a test where 500 rows shift by one line and zero findings change
identity.

---

## FIX-08 — Finding causality and cascade suppression

**Pitch:** link derivative findings to their root cause and stop reporting
the echo by default.

**Why it matters:** a ragged row is kept by `loader.py` (deliberately) and
then reported twice: TODS-E104 for the shape and TODS-E201 for each cell the
short row left empty. A missing required column (E106) similarly implies a
wall of E201s is *not* possible but other cascades are. Cluster hints
(`report.py`, `_ROOT_CAUSE_HINTS`) paper over this statistically; causality
should be structural. Schedulers (P1) triage walls of findings; every echo
costs trust.

**Shape of the work:** give `Finding` an optional `caused_by` (rule ID +
pointer of the root); in the load-problem path, tag E201 findings on rows
that E104 already flagged; renderers collapse caused findings under their
root (text: an indented "and N follow-on findings"; JSON: keep all, with the
link). No finding is deleted — suppression is presentation, honesty is
preserved in the machine formats.

**Effort:** M. **Risks/deps:** interacts with FIX-05's schema bump; keep the
conformance contract (each fixture still trips its own rule). **Excellent
looks like:** the ragged-row fixture produces one primary finding with linked
echoes, and the text report line count for that fixture drops accordingly.

---

## FIX-09 — Severity remapping with an honesty stamp

**Pitch:** let a config remap rule severities (`[severity] "TODS-W316" =
"error"`), with every remap disclosed in the report output.

**Why it matters:** today policy is binary — `ignore` or `--fail-on
warning` globally (`config.py`). A CAD/AVL consumer wants W315/W316 to be
blocking (extends the *mechanism* behind E6's ingest-ready profile without
hard-coding one preset); an agency mid-migration wants E-severity spec
violations visible but non-blocking for one quarter. The honesty constraint
is the differentiator: remaps must be visible in the artifact, or the
"citable report" can quietly lie about what ERROR meant.

**Shape of the work:** a `[severity]` table in `tods-validate.toml`
(validated against known IDs like `_check_rule_ids` does); applied after
rule execution in `runner.run()`; every remapped finding carries
`severity_original` in JSON, and text/Markdown/`--stamp` outputs print a
"Local policy: N severities remapped" disclosure block. Downgrading an
E-band rule requires an explicit `acknowledged = true` per rule.

**Effort:** M. **Risks/deps:** philosophical risk of eroding the spec-based
severity contract — the disclosure block and the acknowledgment flag are the
mitigation, and profiles (E6) become expressible *as* shipped remap sets.
**Excellent looks like:** no output format can contain a remapped finding
without the disclosure.

---

## FIX-10 — Playground integrity and accessibility hardening

**Pitch:** make `web/index.html` reproducible, verifiable, and screen-reader
complete before it is linked from the README (sequenced with R7, which only
covers deploying/linking it).

**Why it matters:** observed in `web/index.html`: Pyodide is loaded from
jsdelivr with no SRI `integrity` attribute; `micropip.install("tods-validate")`
is unpinned, so the page silently changes validator versions under users; the
`#status` paragraph is updated via `textContent` with no `role="status"`/
`aria-live`, so the "Done."/"Validating…" transitions are invisible to screen
readers — on the one surface aimed at the least technical persona (P1). The
page's whole privacy pitch ("nothing leaves the browser") deserves
verification, not just assertion.

**Shape of the work:** pin the wheel version and print it in the UI
("validating with tods-validate 0.6.0 against TODS v2.1.0"); add SRI hashes
and a documented update procedure; `role="status"` on the status line and a
keyboard-reachable summary before the iframe report; a CSP meta tag
restricting network access to the two pinned origins as an enforceable
version of the no-upload claim.

**Effort:** S. **Risks/deps:** none; do alongside R7. **Excellent looks
like:** a screen-reader walkthrough note committed with the deploy, and the
page failing closed (clear error) if the pinned assets do not match.

---

## FIX-11 — Action runtime supply chain and speed

**Pitch:** make the GitHub Action install a pinned, hash-verified build (or
run the published GHCR image) instead of pip-installing the checked-out
source with floating dependencies on every run.

**Why it matters:** `action.yml` runs `pip install ${{ github.action_path }}`,
which resolves `click>=8.1` fresh from PyPI at each CI run — the one surface
marketed as "add 6 lines of YAML" has the weakest supply-chain posture in the
repo, in contrast to the SHA-pinned actions and SBOM/provenance work already
done in `pypi-publish.yml`. It also pays a cold `setup-python` + install cost
per run.

**Shape of the work:** either (a) container action referencing the GHCR
image by digest, or (b) keep composite but install the release wheel with
`--require-hashes` from a committed requirements lock; add pip caching; emit
the tool version in the annotation summary line for provenance.

**Effort:** S–M. **Risks/deps:** container actions are Linux-runner-only —
document that; version-bump automation should update the digest (Renovate
already runs). **Excellent looks like:** a run of the Action performs zero
unpinned network installs and starts ≥2× faster on a warm cache.

---

## FIX-12 — Anonymize: close the identifier gaps and report residual risk

**Pitch:** pseudonymize the fields that are still identifying, and make
`anonymize` report what it could *not* protect.

**Why it matters:** observed in `anonymize.py`: `vehicles.txt`
`vehicle_label` is untouched — it is typically the painted fleet number,
which correlates 1:1 with the pseudonymized `vehicle_id` and undoes it for
anyone with a photo of the bus. Unknown/extension columns and free-text
fields (`job_type`, supplement extension columns per TODS-I108) pass through
silently. The module's honesty about "pseudonymization, not anonymity" is
good; the tool should operationalize that honesty per run, since anonymized
sharing is the project's own proposed path to getting real feeds (R1).

**Shape of the work:** add `vehicle_label` to the default map; a
`--also FILE:FIELD` flag for extension columns; end each run with a
"carried through unprotected" table naming every non-pseudonymized column
that contains non-enum free text; refuse `--salt`-less runs from writing into
a directory that already contains a previous export (mixing salts silently
breaks joins).

**Effort:** S–M. **Risks/deps:** none. **Excellent looks like:** the residual-
risk table appears on every run, and a re-identification walkthrough in
`SECURITY.md` is updated to reflect the closed vehicle_label channel.

---

## FIX-13 — Property-based and differential testing for the untrusted-input path

**Pitch:** add Hypothesis-driven property tests and a small fuzz corpus for
`loader.py`, `merge.py`, and `fix.py` invariants.

**Why it matters:** the loader is explicitly a parser of untrusted input
(SECURITY.md posture, zip limits), yet all fixtures are well-formed
hand-built CSVs; mutation testing (advisory, `mutation.yml`) checks the
*rules*, not the parser. Invariants worth machine-checking: load→serialize→
load round-trips (`_pkgio.serialize_feed`); `fix` idempotence (fixing a fixed
package changes nothing); supplement-application equivalence (FIX-01);
`suggest`'s meaning-preservation bar (proposed value always re-validates
clean — the docstring in `suggest.py` promises exactly this).

**Shape of the work:** `hypothesis` as a dev-only dependency; strategies for
CSV cells (quotes, commas, BOMs, mixed newlines, non-UTF-8 bytes); property
modules kept out of the mutmut selection list (`pyproject.toml`) to protect
the mutation baseline's runtime.

**Effort:** M. **Risks/deps:** flaky-test discipline (derandomize in CI,
store failures as regression examples). **Excellent looks like:** four named
invariants running in CI, each having caught at least one real bug or being
documented as having survived 100k examples.

---

## FIX-14 — Portfolio-standards conformance debt

**Pitch:** add the missing `Makefile` (`make verify` reproducing the CI
AUTO-GATE set), a committed dependency lockfile, and the absent
`docs/RESPONSIBLE-TECH-AUDITS.md` audit artifact.

**Why it matters:** the shared STANDARDS spine requires `make verify` parity
and a per-repo responsible-tech audit; this repo has neither (observed:
no Makefile at root, no audits doc in `docs/`), and sibling repos carry the
uppercase `docs/ROADMAP.md` convention where this one has `docs/roadmap.md`.
For a repo whose pitch includes "boring in the best way," being the outlier
in its own portfolio's conformance snapshot is a credibility leak, and the
audit doc is where FIX-02/FIX-12's honesty work should be recorded.

**Shape of the work:** Makefile targets mirroring `ci.yml` byte-for-byte
(ruff, ruff-format, mypy, pytest+coverage, docs-drift, i18n check); a
`uv`-style lock for the dev environment; an audits doc instantiating the
RESPONSIBLE-TECH-FRAMEWORK sections (privacy: anonymize; transparency:
interpretation fields; accessibility: R2's completed pass).

**Effort:** S. **Risks/deps:** none; purely additive. **Excellent looks
like:** `make verify` green equals CI green, and the audit doc is dated and
regenerated on release.

---

## FIX-15 — HTML report that survives a real feed

**Pitch:** keep the single-file/no-external-assets contract but make the
HTML report usable at 10,000 findings: filtering, per-rule grouping, and a
verified dark scheme.

**Why it matters:** `render_html()` emits one flat `<table>`; a first real
agency feed (R1) will produce thousands of rows of it, and "shareable
report" fails exactly when it is most needed. The palette is also hard-coded
for a white background — the severity colors were AA-checked against white
only (per the R2 pass), and there is no `prefers-color-scheme` handling,
while the playground page *does* declare `color-scheme: light dark`, so the
report renders light inside a dark page.

**Shape of the work:** inline, dependency-free `<script>` (still a single
file) providing severity/rule/file filters and collapsible per-rule groups,
all functional without JavaScript (details/summary fallback); a
`prefers-color-scheme: dark` palette with contrast pairs re-validated to AA
in both schemes; row count and "showing N of M" always in text. Respect the
existing accessibility invariants (caption, scoped headers, word-carried
severity).

**Effort:** M. **Risks/deps:** keep renderer output deterministic for
golden-file consumers (the ordering contract in `report.py`'s docstring);
test with `--max-findings`-sized and 10k-finding synthetic reports.
**Excellent looks like:** a 10k-finding report loads, filters, and reads
under a screen reader in both color schemes with zero external requests.
