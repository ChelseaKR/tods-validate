# Accessibility Standard

The canonical accessibility floor for everything in this portfolio that renders HTML to a human — the three frontends (`personal-site`, `davis-bike-hazard-map`, `trans-docs-navigator`) **and** any HTML a Python repo emits (eval-harness report pages, RAG answer pages, GTFS scorecards, generated `index.html`). Repos override the *values* (a civic transit tool serves a Spanish-dominant California public; a local-only CLI may render no HTML at all) but not the *structure* or the *gates*.

**Floor:** WCAG 2.2 Level AA. Not 2.0, not 2.1 — 2.2, because it is backward-compatible (2.2 AA ⊇ 2.1 AA ⊇ 2.0 AA) and is the standard EN 301 549 v4.1.1 will harmonize to under the EU EAA. Where a repo already exceeds this (`personal-site` ships some AAA), the higher bar is enforced, not relaxed. *Rejected: targeting 2.1 AA "because that's what ADA Title II mandates today" — the 6 new 2.2 SC are cheap to meet on greenfield and expensive to retrofit; we pay now.*

**Enforcement is binary.** Automated tooling mechanically catches ~30–57% of WCAG violations. That ~30–57% is **AUTO-GATED** (merge-blocking CI). The remainder requires human judgment and is **REVIEW-GATED** (a checklist item + a committed, dated artifact). There is no "aspirational" third category. A control that is neither auto-gated nor backed by a committed review artifact does not exist.

This document is the single source of accessibility rigor. Repos record only project-specific values and findings (route lists, ignore-list justifications, the dated screen-reader walkthrough, the ACR). Reference, don't repeat.

---

## 0. Scope, applicability, and N/A declaration

| Repo class | Examples | This standard applies to |
|---|---|---|
| **Frontend (TS/Vite/React)** | `personal-site`, `davis-bike-hazard-map`, `trans-docs-navigator` | Everything below, full force. |
| **Python repo emitting user-facing HTML** | eval-harness report pages (`civic-ai-eval-harness`, `govchat-eval`), RAG answer pages (`civic-rag-starter-kit`, `fare-assistant`), `gtfs-scorecard` HTML output | §1 AUTO-GATEs run against the *generated* HTML (built in CI, then scanned). §2 REVIEW-GATEs apply to each primary task the page supports. |
| **Civic / public-facing content** | `gtfs-scorecard`, `fare-assistant`, `trans-docs-navigator`, `civic-rag-starter-kit`, `davis-bike-hazard-map` | All of the above **plus** §3 plain-language gate. |
| **No-HTML repo** | local-only libraries/CLIs (`ledger`, `nearmiss` core, `swelter`, `tods-validate`, `women-artist-discovery`, `self-osint-monitor`) | Declares **N/A with reason** (below). The standard does not silently skip. |

**N/A is a declaration, not a default.** A repo that renders no HTML to a human records, in its `ROADMAP.md` Metrics table:

```
| Accessibility (ACCESSIBILITY-STANDARD) | N/A — emits no human-facing HTML (CLI/library only). Re-enter scope if a report page, web UI, or HTML export is added. | n/a | n/a | — |
```

A repo that emits HTML but claims a specific gate is N/A (e.g. "no drag interactions, 2.5.7 N/A") records the SC and the reason. Silent omission is a defect.

> **`nearmiss` / `swelter` / `ledger`:** these are local-first but several render summary/report HTML. If the HTML is opened in a browser by a human, it is in scope — re-read the table above before declaring N/A.

---

## 1. AUTO-GATES (merge-blocking CI)

Every gate below either blocks the merge or it is not a gate. `make verify` runs the same checks locally that CI runs remotely — byte-for-byte where the repo already achieves that (most Python repos do; frontends should). No `continue-on-error`, no `|| true`. **The advisory `pa11y`/`axe` pattern (`continue-on-error: true`) currently in `civic-ai-eval-harness`, `govchat-eval`, `civic-rag-starter-kit`, `fare-assistant` is hereby retired** — those flags are deleted, the checks block.

| Metric | Target | Measured by | Gate |
|---|---|---|---|
| axe-core violations (WCAG 2.2 AA) | **0** of impact `critical`, `serious`, `moderate` | `@axe-core/playwright` (frontends) / `@axe-core/cli` against built HTML (Python report pages); `--tags wcag2a,wcag2aa,wcag22aa` | merge-blocking |
| Lighthouse CI accessibility score | **≥ 0.90**; `gtfs-scorecard` **≥ 0.95** (it self-declares ≥95 in `CLAUDE.md` but runs **no** a11y CI — it MUST wire LHCI) | `@lhci/cli autorun`, assertion budget | merge-blocking |
| pa11y-ci errors | **0** errors; `--standard WCAG2AA`, `--level-cap-when-needs-review=AA`; warnings logged, not blocking | `pa11y-ci` over the route list | merge-blocking |
| Lint-time a11y (React) | **0** `jsx-a11y` errors | `eslint-plugin-jsx-a11y` `recommended` + key rules to `error` | merge-blocking (pre-commit + CI) |
| Color contrast | text ≥ **4.5:1** (large ≥ 3:1); non-text/UI ≥ **3:1** (SC 1.4.11) | axe `color-contrast` rule + design-token contrast unit test | merge-blocking |
| Target size (SC 2.5.8, **new in 2.2**) | all pointer targets **≥ 24×24 CSS px** (inline/equivalent/essential excepted) | axe `target-size` rule (verify enabled) + stylelint custom rule | merge-blocking |
| Keyboard path | every primary task completable Tab/Shift-Tab/Enter/Space/Arrow/Escape; visible focus; **focus never fully obscured** (SC 2.4.11, **new in 2.2**) | Playwright keyboard-only spec per primary task | merge-blocking |
| Reduced motion | no essential motion without `@media (prefers-reduced-motion: reduce)` honored | Playwright spec asserts animations suppressed under emulated reduced-motion | merge-blocking |
| 200% zoom / 320px reflow (SC 1.4.10) | no horizontal scroll, no content loss at 320 CSS px width / 400% text zoom | Playwright viewport spec (320×256) asserts `scrollWidth ≤ clientWidth` on `body` | merge-blocking |

### 1.1 Tool selection (decisions, not a survey)

- **axe-core** is the canonical rule engine — zero-false-positive policy, covers WCAG 2.2 AA, scoped via `--tags wcag22aa`. It powers Lighthouse and pa11y, so the three tools agree on the rule set. *Rejected: HTML_CodeSniffer as the pa11y runner — axe runner has materially better 2.2 coverage and no double-reporting against Lighthouse.*
- **Playwright** drives the dynamic gates (keyboard, reduced-motion, reflow) the static scanners can't see, and is already the cross-browser smoke driver in `QUALITY-AND-METRICS-STANDARD` §3 — no new dependency.
- **Lighthouse CI** gives the page-level score budget and a trend artifact. Its score is weighted and a pass does **not** prove AA conformance — it is a floor, never the proof. axe + pa11y + Playwright + the §2 review gates are the proof.
- **eslint-plugin-jsx-a11y** shifts the cheap violations (missing `alt`, unlabeled inputs, bad ARIA) to authoring time so they never reach CI.

### 1.2 Frontend CI snippet (`personal-site` / `davis-bike-hazard-map` / `trans-docs-navigator`)

`jsx-a11y` as a required, erroring rule set — not warnings:

```jsonc
// eslint.config.js (flat) — a11y block
import jsxA11y from "eslint-plugin-jsx-a11y";
export default [
  jsxA11y.flatConfigs.recommended,
  { rules: {
      "jsx-a11y/no-autofocus": "error",
      "jsx-a11y/anchor-is-valid": "error",
      "jsx-a11y/control-has-associated-label": "error",
      "jsx-a11y/no-static-element-interactions": "error",
  }},
];
```

axe via Playwright, failing on `moderate`+ (note: `axe` default critical/serious only — we widen it):

```ts
// a11y.spec.ts
import { test, expect } from "@playwright/test";
import AxeBuilder from "@axe-core/playwright";

for (const route of ["/", "/about", "/projects"]) {       // repo records its route list
  test(`axe AA: ${route}`, async ({ page }) => {
    await page.goto(route);
    const r = await new AxeBuilder({ page })
      .withTags(["wcag2a", "wcag2aa", "wcag22aa"])
      .analyze();
    const blocking = r.violations.filter(v =>
      ["critical", "serious", "moderate"].includes(v.impact ?? ""));
    expect(blocking, JSON.stringify(blocking, null, 2)).toEqual([]);
  });
}
```

```js
// lighthouserc.cjs
module.exports = {
  ci: {
    collect: { staticDistDir: "./dist", url: ["/", "/about", "/projects"] },
    assert: { assertions: { "categories:accessibility": ["error", { minScore: 0.9 }] } }, // gtfs-scorecard: 0.95
    upload: { target: "filesystem", outputDir: "./.lighthouseci" },
  },
};
```

```yaml
# .github/workflows/ci.yml — a11y job (actions SHA-pinned per SECURITY-AND-SUPPLY-CHAIN-STANDARD)
  a11y:
    runs-on: ubuntu-latest
    permissions: { contents: read }   # default-read per CI-CD-STANDARD
    steps:
      - uses: actions/checkout@<40-char-sha>          # v4.2.2
      - uses: actions/setup-node@<40-char-sha>        # v4.1.0
      - run: npm ci && npm run build
      - run: npx playwright install --with-deps chromium
      - run: npx playwright test a11y.spec.ts kbd.spec.ts reflow.spec.ts reduced-motion.spec.ts
      - run: npx @lhci/cli autorun
      - run: npx pa11y-ci --config .pa11yci.json
      - uses: actions/upload-artifact@<40-char-sha>   # v4.4.3  (axe + lhci + pa11y JSON)
        if: always()
        with: { name: a11y-reports, path: "{.lighthouseci,pa11y,axe}/**" }
```

```jsonc
// .pa11yci.json
{ "defaults": { "standard": "WCAG2AA", "runners": ["axe"], "level": "error",
                "chromeLaunchConfig": { "args": ["--no-sandbox"] } },
  "urls": ["http://localhost:4173/", "http://localhost:4173/about"] }
```

### 1.3 Python repos that emit HTML

The HTML is a build artifact, so the a11y check is part of the build: render it, then scan it. Wire into `make verify` so local == CI.

```makefile
# Makefile — runs in `make verify` for any repo emitting HTML
a11y: build-html            ## scan generated HTML for WCAG 2.2 AA violations
	npx --yes @axe-core/cli --tags wcag2a,wcag2aa,wcag22aa --exit \
	  $(shell find dist/reports -name '*.html')
	npx --yes pa11y-ci --config .pa11yci.json
```

This closes the gap where **eval harnesses ship user-facing HTML reports but never gate on their own output's accessibility**. The report page an analyst reads is in scope exactly like a frontend route. `civic-rag-starter-kit` / `fare-assistant` RAG answer pages: the rendered answer + citations are scanned (heading order, link names, contrast of citation chips — all axe-catchable).

### 1.4 Curated ignore list (the only escape hatch)

A real violation that cannot be fixed (third-party embed, upstream library bug) is suppressed **only** via a committed, justified ignore entry — never via `continue-on-error`. Each entry carries the rule id, the URL, a one-line reason, and a tracking issue. An empty `ignore: []` is the expected state.

```jsonc
// .pa11yci.json → "ignore"
"ignore": [
  // "WCAG2AA.Principle1.Guideline1_4.1_4_3.G18.Fail" — leaflet attribution chip, contrast fixed upstream in leaflet@2, tracked #214 (davis-bike-hazard-map)
]
```

---

## 2. REVIEW-GATES (human judgment + committed artifact)

Each is paired with a checklist item in the repo's `docs/RESPONSIBLE-TECH-AUDITS.md` (Accessibility audit, framework §E) and a **dated, committed artifact**, regenerated/refreshed per release. A review gate with no committed artifact is not a gate.

| Review gate | Artifact (committed, dated) | Cadence |
|---|---|---|
| **Screen-reader walkthrough** of every primary task | `docs/a11y/screen-reader-walkthrough-YYYY-MM-DD.md` — pass/fail per task, AT/browser pairing, announced name/role/value/state notes | per release |
| **Keyboard-only walkthrough** (beyond the automated path) | same file or `keyboard-walkthrough-YYYY-MM-DD.md` — verifies 2.4.11, 2.4.3, 2.1.1, focus traps, skip links | per release |
| **ARIA APG pattern audit** for each custom interactive widget | `docs/a11y/apg-<widget>.md` — APG pattern referenced, roles/states/keys verified, deviations justified | on add/change of the widget |
| **Accessibility Conformance Report (ACR/VPAT 2.4)** vs WCAG 2.2 AA + EN 301 549 | `docs/a11y/ACR.md` (VPAT 2.4 Rev or equiv.) | per major release |
| **Cognitive / plain-language review** of forms & auth flows | entry in release accessibility checklist — verifies 3.3.7, 3.3.8, 3.2.6 | per release (where forms/auth exist) |
| **Accessibility statement** published | `docs/a11y/STATEMENT.md` (linked from the site footer) — conformance level, known gaps, contact, date | per release |
| **Third-party / embedded content audit** | note in ACR | annually + on new embed |

### 2.1 Screen-reader matrix (the pairing is not optional)

A screen-reader pass means these AT/browser pairings, because AT behavior diverges and "works in one" proves nothing:

| Pairing | Platform | Required for |
|---|---|---|
| **NVDA + Firefox or Chrome** | Windows | every in-scope repo |
| **VoiceOver + Safari** | macOS | every in-scope repo |
| **VoiceOver + Safari** | iOS | any repo with a mobile-web/PWA surface or touch targets (`davis-bike-hazard-map` map UI, `personal-site`) |

JAWS + Chrome/Edge is the enterprise baseline; add it for any repo with a named government/enterprise client. NVDA and VoiceOver are free, so cost is never the reason a row is skipped.

**Resolve the pending rows now:** `habitable`, `nearmiss`, and `queer-the-stacks` carry pending NVDA/VoiceOver walkthrough rows in their audit docs. Each must ship a completed, dated walkthrough artifact (or a clean N/A-with-reason per §0) before its next release tag. A "pending" row is a failing review gate, not a placeholder.

### 2.2 The 6 WCAG 2.2 AA success criteria — explicit handling

These are new in 2.2 and most are partly review-gated because tooling under-covers them. Every in-scope repo states pass / N/A-with-reason for each:

| SC | Requirement | Primary gate |
|---|---|---|
| **2.4.11 Focus Not Obscured (Min)** | focused component not fully hidden by author content (sticky headers/cookie bars) | AUTO (Playwright focus-visibility spec) |
| **2.5.7 Dragging Movements** | every drag has a single-pointer alternative (acute for `davis-bike-hazard-map` pan/zoom, marker drag) | REVIEW (committed note) + AUTO where a click alt exists to assert |
| **2.5.8 Target Size (Min)** | pointer targets ≥ 24×24 CSS px | AUTO (axe `target-size` + stylelint) |
| **3.2.6 Consistent Help** | help mechanisms in same relative order across pages | REVIEW (multi-page navigation note) |
| **3.3.7 Redundant Entry** | previously entered info auto-populated/selectable | REVIEW (forms/auth checklist) |
| **3.3.8 Accessible Authentication (Min)** | no cognitive-function-test gate without an alternative | REVIEW (auth flows; N/A where no auth) |

> SC **4.1.1 Parsing** is obsolete in 2.2 — do **not** gate on it. The three AAA additions (2.4.12, 2.4.13, 3.3.9) are not required at AA; `personal-site` may opt in where already met.

---

## 3. Plain-language gate (civic content)

Civic repos serve a public that did not choose to be users and cannot route around bad copy: `gtfs-scorecard`, `fare-assistant`, `trans-docs-navigator`, `civic-rag-starter-kit`, `davis-bike-hazard-map`. WCAG 2.2 AA has no plain-language SC at AA (3.1.5 is AAA), but ADA Title II + the civic mission make readable, non-jargon content a hard requirement here.

| Metric | Target | Measured by | Gate |
|---|---|---|---|
| Reading level of public-facing prose & RAG answer scaffolding (labels, errors, help, disclaimers) | **≤ Grade 8** (US) for static UI copy | `textstat` Flesch-Kincaid check in CI over extracted strings | merge-blocking (auto) |
| RAG-generated answer readability | reported, not hard-gated (model output varies) | `textstat` logged per eval run; regression > 1 grade flagged | review-gated |
| Plain-language editorial review | clear, jargon-defined, action-oriented | committed reviewer sign-off in release checklist | review-gated |

```python
# tests/test_plain_language.py  (civic repos)
import textstat
from app.i18n import extract_ui_strings   # en + es catalogs (see INTERNATIONALIZATION-STANDARD)

def test_ui_copy_reading_level():
    failures = {k: g for k, v in extract_ui_strings("en").items()
                if (g := textstat.flesch_kincaid_grade(v)) > 8.0}
    assert not failures, f"UI strings above grade 8: {failures}"
```

For bilingual civic repos, the plain-language gate runs against the EN catalog; the ES catalog is reviewed by a human (no reliable automated ES grade-level metric — declared review-gated, not skipped). i18n catalog mechanics live in `INTERNATIONALIZATION-STANDARD`; this standard requires only that **both** locales clear an a11y screen-reader pass and that the language attribute (`lang`/`xml:lang`, SC 3.1.1/3.1.2) is correct per rendered locale (AUTO — axe `html-has-lang`, `valid-lang`).

---

## 4. Legal context (why these targets, not softer ones)

Not a compliance treatise — the floor and the deadlines that set it.

- **ADA Title II (2024 final rule, deadlines extended Apr 2026):** state/local-government web content must meet **WCAG 2.1 AA** — **Apr 26 2027** (pop. ≥ 50,000) / **Apr 26 2028** (< 50,000 + special districts). Our civic repos (`gtfs-scorecard`, `fare-assistant`, `davis-bike-hazard-map`, transit data for CA jurisdictions) are exactly the content this rule covers when adopted by or for a public entity. Any repo with a named public-entity client records its applicable deadline in `ROADMAP.md`. We target 2.2 AA (a superset) so a 2.1 AA deadline is met automatically.
- **EN 301 549:** v3.2.1 (current) incorporates WCAG 2.1 AA (Clause 9); **v4.1.1 (expected 2026) incorporates 2.2 AA** and becomes the binding EU EAA technical standard once in the Official Journal. The ACR (§2) cites v3.2.1 today and switches to v4.1.1 on harmonization.
- **Section 508:** WCAG 2.0 AA formal floor today; a 2.2 refresh is pending at the Access Board. The ACR/VPAT 2.4 artifact is what federal procurement requires — we ship it regardless.
- **WCAG 3.0:** Working Draft (Mar 2026), not enforceable, no W3C Recommendation expected before ~2029. **Monitor only — build no compliance program around it.** Continue enforcing 2.2 AA.

---

## 5. What goes in each repo (reference, don't repeat)

Cross-cutting rigor lives here. Each in-scope repo records only:

1. **`ROADMAP.md` Metrics rows** for axe (`0`), Lighthouse a11y (`≥ 0.9` / `0.95`), pa11y (`0`), keyboard path, and the §3 reading-level gate where civic — each marked merge-blocking or review-gated, owner named.
2. **Its route/URL list** consumed by the Playwright, LHCI, and pa11y configs.
3. **Its justified ignore list** (§1.4), expected empty.
4. **The §2 committed artifacts** under `docs/a11y/` — walkthroughs, APG audits, ACR, statement, all dated.
5. **N/A declarations with reasons** for any gate that does not apply (§0).

A no-HTML repo records one line: the N/A declaration. Nothing more.

---

Last verified: 2026-06-21 · Recheck cadence: on any WCAG 2.x revision, EN 301 549 publication (v4.1.1 watch), ADA Title II deadline change, or axe-core / pa11y / Lighthouse major release — and at minimum annually. Confirm current standard and tool versions at build time.
