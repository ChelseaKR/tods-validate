# Internationalization & Localization Standard

Canonical rules for any repo that renders, stores, or transmits human-language text to a user. This is **decision-dense, not a survey**: the chosen tool and target are stated with a one-line rationale; rejected alternatives carry a "rejected because" note. A control is either **AUTO-GATE** (mechanically checkable, merge-blocking in CI) or **REVIEW-GATE** (human judgment, paired with a checklist item and a committed artifact). There is no aspirational third category. Cross-cutting rigor (coverage, SAST, supply-chain, a11y browser-engine gates) lives in its own STANDARD and is referenced, not repeated.

> **Why this exists.** Eight bilingual repos store EN/ES as Python dicts or regex — `civic-rag-starter-kit`, `fare-assistant`, `ledger`, `nearmiss`, `swelter` — with no extraction tooling, no plural handling, no translator workflow, and no key-parity check. Only `trans-docs-navigator` (TS `LocaleBundle`), `personal-site` (i18next), and `habitable` (JSON catalogs) have real infra. For civic multilingual RAG explicitly targeting Spanish-dominant California populations, a hand-rolled dict is a correctness and equity defect, not a shortcut. This standard makes the catalog, the gates, and the disaggregated-quality tie-in mandatory for the surfaces that owe it, and makes "we don't need i18n" a **declared decision** rather than a silent omission.

---

## 1. Applicability — who owes i18n and who declares N/A

i18n is **required** for any repo with a user-facing civic / public-sector / multilingual surface. Concretely, in scope today:

| Repo | Surface | Required because |
|---|---|---|
| `civic-rag-starter-kit` | RAG answer UI/API | Civic RAG, Spanish-dominant CA users; LEP populations |
| `trans-docs-navigator` | TS/React frontend | Public legal-doc navigation; already has `LocaleBundle` |
| `govchat-eval` | Eval HTML reports + any served prompts/UI | Civic chat eval; user-facing report output |
| `fare-assistant` | Transit fare answers (EN/ES dicts today) | Public transit + PII; LEP riders |
| `gtfs-scorecard` | Transit scorecard UI | Civic transit data, public-facing |
| `davis-bike-hazard-map` | TS/React map UI | Public civic map |
| `personal-site` | i18next frontend | Already bilingual; reference implementation |
| `habitable` | JSON catalogs | Already bilingual; reference for catalog parity |
| `ledger`, `nearmiss`, `swelter` | EN/ES user-facing strings | Currently bespoke dicts → must migrate |

**Explicitly out of scope** — a repo MAY declare i18n N/A when **all** hold: (a) no natural-language output to a human other than the single developer-operator; (b) English-only by design with no civic/public obligation; (c) no localized dates/numbers/currency shown to an end user. Candidate N/A repos: pure libraries/CLIs with English-only operator output (`tods-validate`, `olive-bark-logger`), single-user privacy tools (`self-osint-monitor`, `women-artist-discovery` where output is operator-only), the `queer-the-stacks`/`queer-specfic-reader` pair (reconcile the fork first — see §11).

**N/A is a committed decision, never a silent skip.** A repo claiming N/A MUST ship `docs/I18N.md` containing exactly:

```markdown
# i18n status: N/A
Reason: <one of the three out-of-scope conditions, named>
Entry point if this changes: wrap user-facing strings in `_()` (gettext) for
Python or `intl.formatMessage` (@formatjs) for TS; then this standard's
AUTO-GATEs apply. See STANDARDS/INTERNATIONALIZATION-STANDARD.md §3.
Declared: 2026-06-21 · Reviewer: <name>
```

| Control | Gate | Mechanism |
|---|---|---|
| In-scope repo has no catalog infra | AUTO-GATE | CI fails if repo is on the in-scope list (§1 table, mirrored in `STANDARDS/applicability.yml`) and ships no `locales/` catalog dir |
| N/A repo missing `docs/I18N.md` | AUTO-GATE | CI greps for `docs/I18N.md` with `i18n status: N/A` and a non-empty Reason; absence fails |

---

## 2. Canonical stack (chosen, with rejected alternatives)

| Concern | Python repos | TS/React frontends | Rationale / rejected |
|---|---|---|---|
| Message catalog | **gettext `.po`/`.pot`** via Babel `pybabel` | **MF2 via `@messageformat/core` + `@formatjs/cli`** | gettext is legacy-appropriate for Python and has `xgettext`/`msgfmt` CI tooling. MF2 is the **normative successor to ICU MF1** (Stable in CLDR 47, LDML TR35 Part 9). *Rejected: ICU MF1 for new TS work — superseded; bespoke dicts — no extraction/plural/parity tooling.* |
| Message syntax (new strings) | gettext plural `Plural-Forms` header | **MF2** (`.match`, `{$count :number}`, required `*` wildcard) | New code MUST NOT introduce ICU MF1 resources. Any MF1 repo files `MIGRATION_MF2.md` (§9). |
| Locale data | **ICU/CLDR 48.2** (`PyICU`/`babel` CLDR tables) | **Ecma-402 `Intl.*`** (CLDR-backed in V8) + `@formatjs` for messages | CLDR is the single canonical source for numbers/currency/dates/plurals/collation/lists. *Rejected: hardcoded date patterns and `%` string formatting — locale-incorrect.* |
| Number/currency/date | `babel.numbers` / `babel.dates` (CLDR) | `Intl.NumberFormat`, `Intl.DateTimeFormat`, `Intl.RelativeTimeFormat`, `Intl.ListFormat` | Use CLDR **semantic skeletons**, not literal patterns. CLDR 48 relative date+time combos ("tomorrow at 12:30") must render. |
| Language tags | **BCP 47 / RFC 5646** everywhere | same | Validate well-formed at input boundary; valid (registry-checked) at authoring. *Rejected: custom locale enums — drift from IANA registry.* |
| HTTP negotiation | **RFC 9110 `Accept-Language`** + RFC 4647 lookup | same (server/Lambda) | `Vary: Accept-Language` mandatory for CDN correctness. MUST NOT use IP geolocation as sole signal. |
| Translation interchange | **XLIFF 2.2** (OASIS CS, Mar 2025) on any TMS round-trip | same | Stable segment IDs preserve TM. *Rejected: XLIFF 1.2 for new integrations.* |
| TMS (if/when human translation scales) | **Crowdin** (single source of truth) | same | 700+ integrations, XLIFF 2.2 + pseudolocale built-in. *Rejected: ad-hoc PRs from translators — no review state machine.* |
| IDE lint | **i18n-ally** (VS Code), mandatory dev dep for localized-UI work | same | Flags hardcoded strings + missing keys inline before CI. |

**Version pins (AUTO-GATE, §10):** CLDR/ICU ≥ **48.2**, lag ≤ 1 major release behind current stable; tzdata ≥ **2026a** (bundled in CLDR 48.2). MF2 runtime at **LDML 48.2** level. MF2 `u:` namespace functions are Draft — MUST NOT be used in shipping resources; `:number :integer :string :datetime :date :time :currency :percent :offset` are Stable and permitted.

---

## 3. The one-line entry point

This is the migration seam every bespoke-dict repo crosses. It is intentionally trivial so "no i18n yet" is never justified by setup cost.

**Python** (`civic-rag-starter-kit`, `fare-assistant`, `ledger`, `nearmiss`, `swelter`):

```python
# i18n.py — install once
import gettext
def get_translation(lang: str) -> gettext.NullTranslations:
    return gettext.translation("messages", localedir="locales",
                               languages=[lang], fallback=True)
_ = get_translation(negotiate_lang(request)).gettext      # see §6
ngettext = get_translation(...).ngettext                  # plural-correct

# usage: replace  f"Found {n} stops"  with:
_("Found {n} stops").format(n=n)         # extracted by pybabel
ngettext("{n} stop", "{n} stops", n).format(n=n)
```

**TS/React** (`trans-docs-navigator`, `davis-bike-hazard-map`, `gtfs-scorecard`, `govchat-eval` reports):

```tsx
import { useIntl } from "react-intl";              // FormatJS, MF2 migration path
const { formatMessage } = useIntl();
formatMessage({ id: "stops.found", defaultMessage: "Found {count, number} stops" },
              { count });
```

Extraction (`pybabel extract` / `formatjs extract`) then populates the catalog. The no-hardcoded-strings gate (§4) keeps it honest thereafter.

---

## 4. AUTO-GATES (merge-blocking)

Every in-scope repo wires these into `make verify` (Python) or the npm `verify` script (TS) so local == CI, matching the portfolio's no-drift discipline. Each row is mechanically checkable; failure blocks merge.

| # | Metric | Target | Measured by | Gate |
|---|---|---|---|---|
| G1 | UTF-8 encoding | 0 non-UTF-8 files/strings | `git ls-files -z \| xargs -0 file --mime-encoding` asserts `utf-8`/`us-ascii`; DB columns asserted UTF-8 in migration test | merge-blocking |
| G2 | No hardcoded UI strings | 0 natural-language strings outside an i18n call | Python: `pybabel extract` + ratchet on count; TS: `formatjs extract` + `i18n-ally`/`eslint-plugin-formatjs` `no-literal-string` | merge-blocking |
| G3 | BCP 47 tag validity | 0 malformed tags | Validate every tag in code/config/headers/HTML via `Intl.Locale(tag)` (TS) / `babel.Locale.parse` (PY); registry-check authored locales | merge-blocking |
| G4 | HTML root `lang` (WCAG 3.1.1 A) | 100% pages valid `lang` | axe-core rule `html-has-lang` + `html-lang-valid` in CI (graduate from advisory — see ACCESSIBILITY-STANDARD) | merge-blocking |
| G5 | Translation completeness + placeholder parity | 0 missing keys, 0 broken/renamed placeholders, full CLDR plural categories | `i18n-check`/custom script: every source key in every target locale; plural categories `zero/one/two/few/many/other` present where the locale requires; placeholder set identical source↔target | merge-blocking |
| G6 | **EN/ES key-parity** (every shipping bilingual repo) | `keys(en) == keys(es)` exactly | Catalog diff in CI; symmetric-difference must be empty | merge-blocking |
| G7 | PO compilation | 0 `msgfmt` errors/warnings | `msgfmt --check --check-format --check-domain *.po` | merge-blocking (Python) |
| G8 | XLIFF schema validity | 0 invalid files | Apache Okapi / OASIS 2.2 schema validation on any committed `.xlf` | merge-blocking (if XLIFF present) |
| G9 | Pseudolocale overflow | 0 clipped/overlapping nodes under ~40% expansion | `formatjs` pseudo-locale (`en-XA` analogue) + Playwright DOM-overflow assertion on key views | merge-blocking (frontends) |
| G10 | RTL: no physical-direction CSS | 0 `margin-left/right`, `padding-left/right`, `left/right` in layout components | stylelint `csstools/use-logical` (require `margin-inline-*`, `padding-inline-*`); `ar`/`he` `dir=rtl` Playwright mirror smoke | merge-blocking (frontends) |
| G11 | `Vary: Accept-Language` | 100% localized endpoints set it | curl/Playwright header assertion in integration test; also assert `Content-Language` present on negotiated responses | merge-blocking (servers/Lambdas) |
| G12 | CLDR/tzdata freshness | CLDR lag ≤ 1 major, tzdata ≥ 2026a | Assert pinned version in `pyproject.toml`/`package.json` ≥ 48.2 | merge-blocking |

### Pseudolocale + extraction gate — copy-paste (TS frontends)

```yaml
# .github/workflows/i18n.yml  (pin uses: to full SHAs per SECURITY-AND-SUPPLY-CHAIN-STANDARD)
name: i18n
on: { pull_request: { paths: ["src/**", "locales/**", "lang/**"] } }
permissions: { contents: read }      # CI-CD-STANDARD: no default-write token
jobs:
  i18n:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@<40-char-sha>          # v4.x.x
      - uses: actions/setup-node@<40-char-sha>         # v4.x.x
      - run: npm ci
      - name: Extract — fail on hardcoded strings
        run: |
          npx formatjs extract 'src/**/*.{ts,tsx}' --out-file /tmp/extracted.json \
            --throws --id-interpolation-pattern '[sha512:contenthash:base64:6]'
          npx tsx scripts/assert-catalog-parity.ts   # G5/G6: keys + placeholders
      - name: Generate pseudolocale (en-XA, ~40% expansion)
        run: npx formatjs compile lang/en.json --ast --out-file lang/en-XA.json --pseudo-locale en-XA
      - name: Pseudolocale overflow + RTL mirror smoke
        run: npx playwright test tests/i18n/pseudo-overflow.spec.ts tests/i18n/rtl-mirror.spec.ts
```

### PO gate — copy-paste (Python repos, into `make verify`)

```makefile
.PHONY: i18n
i18n:
	pybabel extract -F babel.cfg -o locales/messages.pot src/      # regenerate template
	git diff --exit-code locales/messages.pot                       # G2: POT committed & current
	pybabel update  -i locales/messages.pot -d locales --no-fuzzy-matching
	msgfmt --check --check-format --check-domain locales/*/LC_MESSAGES/messages.po
	python scripts/check_catalog_parity.py        # G5/G6 keys + plural cats + placeholders
	python scripts/check_bcp47.py                 # G3 tag well-formedness/validity
verify: lint type test i18n                       # same target CI runs — no local/CI drift
```

---

## 5. REVIEW-GATES (human judgment + committed artifact)

Each is paired with a checklist item in `docs/RESPONSIBLE-TECH-AUDITS.md` (or `docs/I18N.md`) and a dated, committed artifact regenerated per release. No "aspirational."

| # | Review-gate | Committed artifact | Cadence |
|---|---|---|---|
| R1 | **Language-of-Parts audit** (WCAG 3.1.2 AA) — every foreign-language passage carries `lang`; exceptions (proper names, technical terms) justified | `docs/audits/lang-of-parts.md` | per release + quarterly |
| R2 | **Full-RTL QA** — human tester runs `ar`/`he`/`fa` in a real RTL browser: layout mirroring, bidi in mixed content, form-field alignment, icon directionality, date/number formatting | signed-off RTL QA checklist | per release |
| R3 | **Translation review workflow** — every human string passes `initial → translated → reviewed → final` in the TMS before merge; no unreviewed MT in civic prod without a documented MQM/BLEU threshold | TMS export + MT-QA policy in `docs/I18N.md` | per string change |
| R4 | **Locale-acceptance test** — per new locale, dev verifies number (decimal/grouping/negative), currency (symbol position/spacing), date/time (calendar/era/field order), address formatting against CLDR | `tests/locale_acceptance/<tag>.md` | per new locale |
| R5 | **Language-negotiation correctness** — send `Accept-Language` for each supported locale + one unsupported; verify fallback chain (e.g. `es-MX → es → site default`) | `docs/LANGUAGE_POLICY.md` | per release + quarterly |
| R6 | **Civic multilingual-obligations review** — map applicable law (EU EN 301 549 / Web Accessibility Directive, Canada OLA, applicable US state LEP mandates) to implementation. **Note: US federal EO 13166 was rescinded by EO 14224 (2025); verify current federal agency obligations independently — do not assume mandatory.** | `docs/compliance-matrix.md` | annual |
| R7 | **Equitable-quality / disaggregated eval** (see §7) — sign-off that per-language quality deltas are within tolerance | per-language eval report | per model/prompt/retrieval change |

---

## 6. Language negotiation (servers, Lambdas, RAG APIs)

`fare-assistant`, `civic-rag-starter-kit`, `gtfs-scorecard`, `govchat-eval`, `personal-site` Lambda:

- Parse `Accept-Language` (RFC 9110 §12.5.4) into BCP 47 ranges with `q` weights; apply **RFC 4647 lookup**.
- Honor user preference; MUST NOT decide locale by IP geolocation alone.
- Set `Content-Language` and `Vary: Accept-Language` (G11) on every negotiated response.
- Document the fallback chain in `docs/LANGUAGE_POLICY.md` (R5). Default chain: `<requested> → <primary subtag> → site default (en)`.
- RAG specifics: the **answer locale, the retrieval-corpus locale, and the citation/grounding-guard locale must agree**; a Spanish query answered from English-only context with English citations is a defect — record corpus language coverage in the data card (RESPONSIBLE-TECH-FRAMEWORK §C/D).

---

## 7. Equitable quality across languages — disaggregated eval (responsible-tech tie-in)

This is the link to RESPONSIBLE-TECH-FRAMEWORK §B (bias & fairness) and AI-EVALUATION-STANDARD. **Translating the UI is necessary but not sufficient**; the *answer quality* must hold across languages, or LEP users get a degraded civic service.

For every AI/RAG repo serving more than one language (`civic-rag-starter-kit`, `fare-assistant`, `govchat-eval`, `trans-docs-navigator` if it serves generated text):

| Metric | Target | Measured by | Gate |
|---|---|---|---|
| Per-language faithfulness/grounding | EN↔ES delta ≤ **5 pts** absolute, and ES meets the same absolute floor as EN (per AI-EVALUATION-STANDARD: Faithfulness ≥ 0.80) | RAGAS/DeepEval run **disaggregated by query language** on a held-out bilingual benchmark | AUTO-GATE on PRs touching prompts/retrieval/model version |
| Per-language hallucination rate | ≤ 5% each language; no language > 2× the best | same held-out 100–500 query benchmark, split by language | AUTO-GATE |
| Citation/grounding-guard coverage | 100% each language (no ungrounded code path — already enforced in the RAG repos) | existing citation guard, exercised with ES fixtures | AUTO-GATE |
| Representational harm in non-EN output | none unmitigated | targeted probe suite per language | REVIEW-GATE (R7) |

Benchmarks MUST include native (not machine-translated) ES queries for the CA civic domain; an all-MT benchmark hides translation-induced quality loss and is itself a finding to record.

---

## 8. RTL & bidi requirements (frontends)

Per W3C *Additional Requirements for Bidi in HTML and CSS*:

- Every natural-language element carries `dir` (`ltr`/`rtl`/`auto`) or inherits it; **user-generated content of unknown direction uses `dir="auto"`.**
- `<bdi>` isolates embedded spans of unknown/opposite directionality; inline direction switches use `unicode-bidi: isolate`.
- Programmatic directionality uses **isolating** controls (RLI/LRI/FSI + PDI), never embedding controls (RLE/LRE).
- Form inputs use `dirname` to submit typing direction.
- Layout uses **CSS logical properties only** (`margin-inline-start`, `padding-inline-end`, `border-inline`, `inset-inline`) — enforced by G10. Punctuation at bidi boundaries is tested explicitly with `ar` and `he` fixtures in CI (G10 smoke).

---

## 9. MF1 → MF2 migration

Any repo with existing ICU MF1 resources (audit FormatJS/`react-intl` usage in `personal-site`, `trans-docs-navigator`) ships `MIGRATION_MF2.md` naming the target completion quarter. **REVIEW-GATE:** plan present; **AUTO-GATE:** no new MF1 message resources introduced after plan adoption (lint rule rejecting MF1-only syntax in new keys). gettext repos are exempt (PO is the chosen Python container; MF2 applies to the TS/JSON message layer).

---

## 10. Version pinning & upgrade cadence

```toml
# pyproject.toml (Python i18n repos)
[project]
dependencies = ["babel>=2.16", "pyicu>=2.13"]   # CLDR via ICU >= 78.3 / CLDR >= 48.2
```

```json
// package.json (TS frontends)
"dependencies": {
  "@messageformat/core": "^3",        // LDML 48.2 level
  "@formatjs/intl": "^3", "react-intl": "^7"
}
```

- AUTO-GATE (G12): pinned CLDR/ICU ≥ 48.2, lag ≤ 1 major; tzdata ≥ 2026a.
- Documented CLDR upgrade cadence: **at minimum once per major CLDR release cycle**, tracked in `docs/I18N.md`. Renovate/Dependabot (per SECURITY-AND-SUPPLY-CHAIN-STANDARD: digest-pinned actions, `minimumReleaseAge` 72h) opens the bump PR; the i18n gates prove the upgrade is non-breaking.

---

## 11. Repo-specific actions (closing the gap)

| Repo | Action | First gate to land |
|---|---|---|
| `civic-rag-starter-kit` | Replace EN/ES dicts → gettext `.po`; add §7 disaggregated eval | G1, G2, G6, then §7 |
| `fare-assistant` | regex/dict → `.po`; negotiate `Accept-Language`; ES faithfulness parity | G6, G11, §7 |
| `ledger`, `nearmiss`, `swelter` | dict → `.po`; key-parity gate | G6, G7 |
| `trans-docs-navigator` | confirm MF2/`LocaleBundle` parity + pseudolocale + RTL gates; fix the one tag-pinned `uses:` in `deploy-aws-preview.yml` (supply-chain, cross-ref) | G5, G9, G10 |
| `personal-site` | reference i18next repo; audit MF1→MF2 (§9) | G9 (reference) |
| `habitable` | JSON catalogs → wire G5/G6 parity gate | G6 |
| `gtfs-scorecard` | add UI catalog; note real `pyproject.toml` lives under `pipeline/` — wire gates there | G1, G2, G4 |
| `davis-bike-hazard-map` | pseudolocale + RTL gates on the map UI | G9, G10 |
| `govchat-eval` | served HTML report `lang` + bidi; disaggregated eval | G4, §7 |
| N/A candidates (`tods-validate`, `olive-bark-logger`, `self-osint-monitor`, `women-artist-discovery`) | commit `docs/I18N.md` N/A declaration | N/A-declaration gate |
| `queer-the-stacks` / `queer-specfic-reader` | **reconcile the undocumented fork before declaring i18n status** — they share package `queer_the_stacks`; one declaration must not silently cover both | reconcile first |
| `self-osint-monitor` | i18n decision is part of M0/M1 scaffold, not a retrofit; default N/A (single-user) with declaration | N/A-declaration gate |

---

## 12. Cross-references (reference, don't repeat)

- **Browser-engine a11y gates** (axe/pa11y graduated to blocking, WCAG 2.2 AA, target-size 2.5.8): ACCESSIBILITY-STANDARD. G4 here depends on that graduation.
- **SHA-pinned `uses:`, `permissions: contents: read`, OIDC, Scorecard** on the i18n workflow: SECURITY-AND-SUPPLY-CHAIN-STANDARD + CI-CD-STANDARD.
- **Faithfulness/hallucination/judge-calibration thresholds** underpinning §7: AI-EVALUATION-STANDARD.
- **Coverage floors, ruff/mypy pins, single `pyproject.toml`, `make verify == CI`**: CODE-QUALITY-STANDARD. The i18n target joins `make verify`.
- **Data card / model card / disaggregated fairness narrative**: RESPONSIBLE-TECH-FRAMEWORK §B, §C, §D.
- **Metric table shape** (Metric/Target/Measured-by/Gate/Owner) mirrored into each repo's `ROADMAP.md`: QUALITY-AND-METRICS-STANDARD.

---

Last verified: 2026-06-21 · Recheck cadence: per Unicode CLDR/ICU major release (next ≥ 49) and on any WCAG, BCP 47/RFC 5646, RFC 9110, XLIFF, or US/EU/state language-access legal change. Confirm CLDR 48.2 / ICU 78.3 / MF2 LDML 48.2 / WCAG 2.2 are still current at build time.
