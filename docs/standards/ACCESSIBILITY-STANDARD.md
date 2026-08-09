# Accessibility Standard

The canonical accessibility floor for everything in this portfolio that renders
HTML to a human: web frontends, generated reports, RAG answer pages, scorecards,
maps, and generated `index.html` files. Repositories override the *values* (a
civic tool may serve a multilingual public; a local-only CLI may render no HTML
at all) but not the *structure* or the *gates*.

**Floor:** WCAG 2.2 Level AA. Not 2.0, not 2.1 — 2.2, because it is backward-compatible (2.2 AA ⊇ 2.1 AA ⊇ 2.0 AA) and is the standard EN 301 549 v4.1.1 will harmonize to under the EU EAA. Where a repository already exceeds this and declares a higher target, the higher bar is enforced, not relaxed. *Rejected: targeting 2.1 AA "because that's what ADA Title II mandates today" — the 6 new 2.2 SC are cheap to meet on greenfield and expensive to retrofit; we pay now.*

**Enforcement is binary.** Automated tooling mechanically catches ~30–57% of WCAG violations. That ~30–57% is **AUTO-GATED** (merge-blocking CI). The remainder requires accountable human judgment and is **REVIEW-GATED** (a checklist item + a committed, dated artifact). Direct human experience is the default evidence. Section 2.0 defines one bounded alternative disposition for eligible solo-maintained projects: synthetic evidence plus maintainer residual-risk acceptance may authorize a **provisional release** while the human walkthrough remains open. That disposition is not a third gate type, a walkthrough pass, or a conformance result.

This document is the single source of accessibility rigor. Repos record only project-specific values and findings (route lists, ignore-list justifications, the dated screen-reader walkthrough, the ACR). Reference, don't repeat.

---

## 0. Scope, applicability, and N/A declaration

**The scoping registry is `STANDARDS/applicability.yml`**: each repo's entry carries an `html` surface flag and marks this standard `applies` or `na: "<reason>"`. A new repo is scoped by adding a manifest entry, never by editing this prose. The classes below define *how* the standard attaches; repo names are illustrative examples only:

| Repo class | Examples | This standard applies to |
|---|---|---|
| **Frontend (TS/Vite/React)** | SPA, PWA, public map, or multilingual frontend | Everything below, full force. |
| **Python repo emitting user-facing HTML** | evaluation report, RAG answer page, or generated scorecard | §1 AUTO-GATEs run against the *generated* HTML (built in CI, then scanned). §2 REVIEW-GATEs apply to each primary task the page supports. |
| **Civic / public-facing content** | public-service answer, map, navigator, or data product | All of the above **plus** §3 plain-language gate. |
| **No-HTML repo** | local-only library or CLI | Declares **N/A with reason** (below and in `applicability.yml`). The standard does not silently skip. |

**N/A is a declaration, not a default.** A repo that renders no HTML to a human records, in its `ROADMAP.md` Metrics table:

```
| Accessibility (ACCESSIBILITY-STANDARD) | N/A — emits no human-facing HTML (CLI/library only). Re-enter scope if a report page, web UI, or HTML export is added. | n/a | n/a | — |
```

A repo that emits HTML but claims a specific gate is N/A (e.g. "no drag interactions, 2.5.7 N/A") records the SC and the reason. Silent omission is a defect.

> A local-first tool is not automatically out of scope. If it renders summary
> or report HTML that a human opens in a browser, that surface is in scope.

---

## 1. AUTO-GATES (merge-blocking CI)

Every gate below either blocks the merge or it is not a gate. `make verify` runs the same checks locally that CI runs remotely. No `continue-on-error`, no `|| true`: any advisory `pa11y`/`axe` pattern is retired, those flags are deleted, and the checks block.

| Metric | Target | Measured by | Gate |
|---|---|---|---|
| axe-core violations (WCAG 2.2 AA) [A11Y-01] | **0** of impact `critical`, `serious`, `moderate` | `@axe-core/playwright` (frontends) / `@axe-core/cli` against built HTML (Python report pages); `--tags wcag2a,wcag2aa,wcag22aa` | merge-blocking |
| Lighthouse CI accessibility score [A11Y-02] | **≥ 0.90**; a repository that declares a higher floor enforces that higher value in LHCI | `@lhci/cli autorun`, assertion budget | merge-blocking |
| pa11y-ci errors [A11Y-03] | **0** errors; `--standard WCAG2AA`, `--level-cap-when-needs-review=AA`; warnings logged, not blocking | `pa11y-ci` over the route list | merge-blocking |
| Lint-time a11y (React) [A11Y-04] | **0** `jsx-a11y` errors | `eslint-plugin-jsx-a11y` `recommended` + key rules to `error` | merge-blocking (pre-commit + CI) |
| Color contrast [A11Y-05] | text ≥ **4.5:1** (large ≥ 3:1); non-text/UI ≥ **3:1** (SC 1.4.11) | axe `color-contrast` rule + design-token contrast unit test | merge-blocking |
| Target size (SC 2.5.8, **new in 2.2**) [A11Y-06] | all pointer targets **≥ 24×24 CSS px** (inline/equivalent/essential excepted) | axe `target-size` rule (verify enabled) + stylelint custom rule | merge-blocking |
| Keyboard path [A11Y-07] | every primary task completable Tab/Shift-Tab/Enter/Space/Arrow/Escape; visible focus; **focus never fully obscured** (SC 2.4.11, **new in 2.2**) | Playwright keyboard-only spec per primary task | merge-blocking |
| Reduced motion [A11Y-08] | no essential motion without `@media (prefers-reduced-motion: reduce)` honored | Playwright spec asserts animations suppressed under emulated reduced-motion | merge-blocking |
| 200% zoom / 320px reflow (SC 1.4.10) [A11Y-09] | no horizontal scroll, no content loss at 320 CSS px width / 400% text zoom | Playwright viewport spec (320×256) asserts `scrollWidth ≤ clientWidth` on `body` | merge-blocking |

### 1.1 Tool selection (decisions, not a survey)

- **axe-core** is the canonical rule engine — zero-false-positive policy, covers WCAG 2.2 AA, scoped via `--tags wcag22aa`. It powers Lighthouse and pa11y, so the three tools agree on the rule set. *Rejected: HTML_CodeSniffer as the pa11y runner — axe runner has materially better 2.2 coverage and no double-reporting against Lighthouse.*
- **Playwright** drives the dynamic gates (keyboard, reduced-motion, reflow) the static scanners can't see, and is already the cross-browser smoke driver in `QUALITY-AND-METRICS-STANDARD` §3 — no new dependency.
- **Lighthouse CI** gives the page-level score budget and a trend artifact. Its score is weighted and a pass does **not** prove AA conformance — it is a floor, never the proof. axe + pa11y + Playwright + the §2 review gates are the proof.
- **eslint-plugin-jsx-a11y** shifts the cheap violations (missing `alt`, unlabeled inputs, bad ARIA) to authoring time so they never reach CI.

### 1.2 Frontend CI snippet

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
    assert: { assertions: { "categories:accessibility": ["error", { minScore: 0.9 }] } },
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

An evaluation harness that ships a user-facing HTML report gates its own output's accessibility. The report page an analyst reads is in scope exactly like a frontend route. For a RAG answer page, the rendered answer and citations are scanned (heading order, link names, and contrast of citation chips are all axe-catchable).

### 1.4 Curated ignore list (the only escape hatch)

A real violation that cannot be fixed (third-party embed, upstream library bug) is suppressed **only** via a committed, justified ignore entry — never via `continue-on-error`. Each entry carries the rule id, the URL, a one-line reason, and a tracking issue. An empty `ignore: []` is the expected state.

```jsonc
// .pa11yci.json → "ignore"
"ignore": [
  // "WCAG2AA.Principle1.Guideline1_4.1_4_3.G18.Fail" — third-party attribution chip, fixed in the next upstream major, tracked in the consuming repository
]
```

---

## 2. REVIEW-GATES (accountable judgment + committed artifact)

Each is paired with a checklist item in the repo's `docs/RESPONSIBLE-TECH-AUDITS.md` (Accessibility audit, framework §E) and a **dated, committed artifact**, regenerated/refreshed per release. A review gate with no committed artifact is not a gate. Human experiential evidence remains the normal path. Section 2.0 may authorize a provisional release for an eligible solo maintainer, but it leaves the human walkthrough controls open and cannot upgrade an ACR or accessibility statement to a conformance claim.

| Review gate | Artifact (committed, dated) | Cadence |
|---|---|---|
| **Screen-reader walkthrough** of every primary task | `docs/a11y/screen-reader-walkthrough-YYYY-MM-DD.md` — pass/fail per task, AT/browser pairing, announced name/role/value/state notes | per release |
| **Keyboard-only walkthrough** (beyond the automated path) | same file or `keyboard-walkthrough-YYYY-MM-DD.md` — verifies 2.4.11, 2.4.3, 2.1.1, focus traps, skip links | per release |
| **ARIA APG pattern audit** for each custom interactive widget | `docs/a11y/apg-<widget>.md` — APG pattern referenced, roles/states/keys verified, deviations justified | on add/change of the widget |
| **Accessibility Conformance Report (ACR/VPAT 2.4)** vs WCAG 2.2 AA + EN 301 549 | `docs/a11y/ACR.md` (VPAT 2.4 Rev or equiv.) | per major release |
| **Cognitive / plain-language review** of forms & auth flows | entry in release accessibility checklist — verifies 3.3.7, 3.3.8, 3.2.6 | per release (where forms/auth exist) |
| **Accessibility statement** published | `docs/a11y/STATEMENT.md` (linked from the site footer) — conformance level, known gaps, contact, date | per release |
| **Third-party / embedded content audit** | note in ACR | annually + on new embed |
| **Solo-maintainer provisional synthetic evidence** [A11Y-27] | `docs/a11y/synthetic-accessibility-evidence-YYYY-MM-DD.md` plus its validated JSON manifest — exact-artifact evidence, limitations, expiry, and maintainer residual-risk acceptance | each accessibility-affecting provisional release; maximum 90-day currency |

### 2.0 Solo-maintainer provisional synthetic-evidence path

The normal release evidence is a human assistive-technology walkthrough. A project with one active
maintainer **MAY** deploy before that walkthrough only through this path. The result is a
**provisional accessibility release**, not a completed screen-reader review and not verified WCAG,
Section 508, or EN 301 549 conformance. Controls A11Y-11, A11Y-12, A11Y-14, and A11Y-18 remain open.

“Human-reviewed,” “screen-reader tested,” “NVDA passed,” “VoiceOver passed,” “user-tested,” and
equivalent phrases are reserved for work personally performed by the named reviewer. CI, browser
automation, accessibility-tree or DOM inspection, emulation, scripted assistive-technology output,
and model-assisted review are **synthetic evidence**. Signing their report does not convert them into
human experience.

#### Eligibility — every condition is required

1. The repository has one active maintainer and no independent reviewer on the project team. A
   current `docs/governance/solo-maintainer-YYYY-MM-DD.md` declaration names that human and repository;
   hosted release validation authenticates its current-head PR attestation and proves through the
   GitHub collaborators API that the declared owner is the only push/maintain/admin-capable account.
   That attestation is bound to the active protect-main ruleset identity/update time and explicitly
   declares its hosted bypass actor set empty.
2. The release is an independent portfolio or open-source project, not a contractual deliverable,
   procurement submission, formal conformance package, or legally required accessibility claim.
3. The changed surface does not determine access to employment, payment, healthcare, emergency
   response, a public benefit, or another essential transaction.
4. Every primary visual task has a tested semantic or native-control equivalent. A missing equivalent
   makes this path unavailable.
5. Every applicable §1 AUTO-GATE passes against the exact immutable candidate artifact. No
   accessibility failure is ignored, suppressed, waived, or downgraded to use this path.
6. There is no known critical, serious, or high-impact accessibility barrier and no primary task
   known to require vision or a pointer. An open `Critical`, `Serious`, `High`, or `Blocker` finding
   makes this path unavailable.
7. The release has a tested rollback path stored as a tracked repository reference present at the
   tested source, a public HTTPS accessibility-reporting channel, and an accessibility statement that
   labels the release provisional.
8. The maintainer commits a dated residual-risk acceptance bound to the tested source commit,
   immutable candidate-artifact digest, and canonical SHA-256 of the full material evidence record.
9. Every other applicable accessibility REVIEW-GATE is current, completed, or recorded N/A with a
   specific applicability reason. “N/A,” “not applicable,” and equally circular text are not reasons.
   This path leaves only the human experiential controls named below open; it is not a blanket
   substitution for editorial, APG, statement, third-party, or ACR completeness review.

A human review cannot override a failed AUTO-GATE, a known inaccessible primary task, or a missing
semantic equivalent.

#### Minimum evidence packet

The committed Markdown record and machine-readable manifest **MUST** include:

- tested source commit SHA, artifact digest and digest scope, current solo-governance declaration
  path, tracked rollback reference, HTTPS reporting channel, absolute same-origin route list,
  canonical BCP-47 locale list, data/release versions, date, and exact dotted tool and browser versions;
- structural inspection and rendered axe/pa11y results with zero critical, serious, or moderate
  violations;
- scripted keyboard completion of every primary task, including focus order, visibility,
  redraw/restoration, destructive actions, inactive-panel exclusion, and no traps;
- Chromium, Firefox, and WebKit rendered checks for every changed custom interactive widget;
- 320 CSS-pixel reflow, the 200%-equivalent layout proxy, text resize, forced colors, reduced motion,
  contrast, and 24×24 target-size checks, each named accurately rather than relabeled as a human zoom
  pass;
- programmatic name, role, value/state, heading, landmark, table-header, and live-region contracts.
  Live-region timing or wording **MUST NOT** be described as “announced correctly” without human AT;
- automated parity proving every visualized value and status exists in the semantic equivalent,
  including suppressed or unknown values never becoming numeric zero;
- locale parity and rendered `lang` correctness for every shipped language;
- exact-artifact smoke tests, failure-path simulations, findings, remediation commits, and regression
  coverage, with every result bound to a committed `docs/` path or immutable GitHub Actions run/job
  URL;
- untested behaviors, known limitations, residual risks, and the rollback trigger; and
- the model or automation named as an evidence producer, never as a reviewer, user, or person with a
  disability.

The evidence record uses a two-PR, non-self-referential chain:

1. Merge the product PR first. Its protected-main result is source commit **P**. Build and test **P**,
   producing immutable artifact **A** with digest **G** and signed SLSA provenance that binds **A**
   to **P** and the GitHub repository.
2. From **P**, open an evidence-only PR whose net change is exactly one new current evidence record
   **E** naming **P** and **G**. Public status, policy adoption, tests, and every shipped-surface
   change must already be present in **P**.
3. Draft **E** with a temporary syntactically valid `acceptance_ref` for that evidence PR and render
   the canonical hosted acceptance. Its `synthetic-accessibility-record-v1` digest removes HTML
   comments as non-record content, deletes only the circular `risk_acceptance.acceptance_ref` from a
   canonicalized JSON manifest, normalizes line endings/trailing whitespace, and hashes every other
   material visible character of **E**, including prose and tables. Post that exact digest-bound
   comment from the named human account, then replace the temporary reference with the resulting
   comment URL. Any other material edit requires a new comment.
4. Commit and push **E**, then post the separate canonical solo-governance current-head owner
   attestation. Hosted validation requires both authenticated comments, exact repository/owner
   parity, a current declaration, and exactly one push-capable collaborator. Run the full synthetic
   `--release-validation` gate at this current evidence-PR head; it is deliberately not run against a
   later deployment-decision commit.
5. Merge the evidence-only PR through the repository's ordinary protected squash, rebase, or merge
   policy. Verify **P** remains an ancestor of the release head and the net `P..HEAD` change is exactly
   the one added record **E**. A rewrite that breaks **P** ancestry, base-branch drift, modified record,
   or any second changed file invalidates the chain; squash or rebase does not invalidate it merely by
   changing **E**'s commit identity.
6. After **E** merges, create the separate final decision-only descendant **D** required by
   `CI-CD-STANDARD.md` §8a and pass its full **P→E→D** deployment gate. Only then promote **A** by
   digest **G**; do not rebuild the deployable payload from **E** or **D**. The tag/release may select
   evidence head **E**, while **D** remains the durable deployment authorization on `main`. Release
   metadata records all three commit identities without implying that **A** was built from either
   post-test record.

The digest scope must cover every deployed executable and user-visible byte. It may exclude only the
new evidence record and inert provenance metadata whose value cannot change runtime or accessibility
behavior. The release gate downloads the promoted artifact, recomputes its SHA-256, and rejects any
mismatch. This makes the record commit possible without creating a circular commit hash and prevents
post-test product changes from riding on earlier evidence.

Validate the manifest with `automation/check_synthetic_a11y_evidence.py` from this standards release
[A11Y-28], and wire that command against the current record into the consumer's `make verify` and CI.
Release verification uses a full-history checkout, forbids `--structure-only`, and invokes
`--release-validation --artifact <immutable-candidate> --attestation-bundle <bundle>`. That mode
recomputes the SHA-256, runs `gh attestation verify` against the signed SLSA bundle, repository/signer
identity, protected-main source ref, and source digest, rechecks the verified statement's P/repo/digest
bindings, fetches the exact digest-bound accessibility acceptance through the GitHub API, validates
the current solo-governance declaration, authenticates its current-head owner attestation, and proves
the hosted collaborator set contains only that same owner while the committed and hosted protect-main
profiles match and the digest-bound owner attests that hosted bypass actors are empty. `--artifact`
or `--attestation-bundle` without `--release-validation` is rejected. Missing network access,
authentication, declaration, artifact, bundle, signature, provenance field, identity/ruleset parity,
collaborator/no-bypass proof, or comment verification fails closed. Structural validation without
this mode is not a qualifying release gate.
An expired, malformed, misleading, or ineligible record blocks the provisional path. A schema-valid
manifest does not establish that its referenced checks are true; the immutable logs and artifacts it
names remain the evidence.

The command names the one current record explicitly; it **MUST NOT** validate a historical-record
glob. Prior records remain immutable audit history and may be expired without falsifying the release
they documented. A renewal adds a new dated file whose `renewal_of` names the tracked prior record;
the evidence lake reports freshness from the newest record.

#### Required disposition and claims

The accessibility statement, release audit, and PR use this status as visible text, exactly and
without an additional claim; an HTML comment does not satisfy it:

> **Accessibility status: WCAG 2.2 AA target. Automated and synthetic evidence passed for this
> release; human assistive-technology review remains pending.**

The audit disposition uses this language:

> **Provisionally released through the solo-maintainer synthetic-evidence path. This record authorizes
> deployment through residual-risk acceptance; it is not a human accessibility review or a
> conformance finding.**

Until the human matrix in §2.1 passes, the project **MUST NOT** claim “WCAG compliant/conformant,”
“Section 508 conformant,” “screen-reader tested,” or “human-reviewed”; show an unqualified green WCAG
badge; or upgrade AT-dependent ACR rows to unqualified `Supports`.

The accountable maintainer records the following visible text exactly in the evidence record
(replacing placeholders with manifest values):

> I authorize promotion of immutable artifact `<digest>` built from tested source commit `<sha>` based
> on the automated and synthetic evidence identified above. No human NVDA, VoiceOver, uninterrupted
> no-pointer, or actual browser-zoom walkthrough was performed. No human assistive-technology review
> was performed. I do not represent this release as verified WCAG or Section 508 conformance. This is
> not a human accessibility review or a conformance finding. I accept the listed residual risks through
> `<expiry>`, will prioritize reported barriers, and will use `<rollback-reference>` if a primary task
> is blocked.
>
> - **Accepted by:** `<Human Name (@github-login)>`
> - **Accepted on:** `<YYYY-MM-DD matching the comment's UTC creation date>`

The authenticated GitHub comment is generated with
`--structure-only --print-acceptance`. It contains that exact decision plus the v1 machine marker and
the canonical material-record digest. Hand-written, stale-digest, or otherwise edited comment text
does not satisfy the release gate.

This is a truthful risk decision. It is not an assertion that an unperformed test passed.

#### Currency and mandatory return to human review

- The evidence and risk acceptance expire no later than **90 days** after generation.
- Any change after the tested source commit other than addition of the exact current evidence record,
  or any change to the relevant UI, ARIA behavior, browser dependency, locale, data semantics, digest
  scope, or release artifact, invalidates the record immediately; every accessibility-affecting release
  regenerates it.
- An eligible solo maintainer may renew the path while every eligibility condition still holds. Each
  renewal is a fresh evidence packet and risk decision, never a carry-forward checkbox.
- Expiry does not falsify the historical record or force takedown without a known barrier, but it
  blocks the next accessibility-affecting release until renewed.

A genuine human walkthrough becomes mandatory before issuing a formal ACR for the provisional
version or making any unqualified conformance claim. The synthetic evidence record is the release's
provisional accessibility status report; it is not an ACR/VPAT and cannot populate an AT-dependent
conformance verdict. Human review is also mandatory for
government, enterprise, client, procurement, contractual, or legally regulated use; an essential
transaction described above; release after a second active maintainer or reviewer joins; closing a
verified AT-specific complaint; relying on an ignored violation; or shipping without a complete
semantic equivalent. Remediation for a verified AT-specific failure must be retested with the affected
AT/browser pairing.

#### Residual-risk baseline

| Risk | Likelihood | Impact | Level | Required mitigation | Owner / status |
|---|---|---|---|---|---|
| AT-specific announcement or interaction failure escapes synthetic checks | Medium | High | High | complete semantic/native path, three-engine checks, public reporting channel, rollback trigger | maintainer · accepted provisionally |
| A reader mistakes provisional evidence for conformance | Medium | High | High | required status text, prohibited-claim rules, qualified ACR rows | maintainer · mitigated |
| Evidence becomes stale after a surface or dependency change | Medium | Medium | Medium | tested-source ancestry, evidence-only delta, artifact-digest promotion, immediate invalidation, 90-day maximum | maintainer · mitigated |
| The provisional path becomes invisible permanent debt | Medium | Medium | Medium | human gate stays open in every artifact; fresh acceptance on renewal; mandatory-return triggers above | maintainer · open |

### 2.1 Screen-reader matrix (the pairing is not optional)

A human-validated screen-reader pass or conformance claim means these AT/browser pairings, because AT behavior diverges and "works in one" proves nothing. The §2.0 provisional path records unavailable pairings as **not performed**, never pass:

| Pairing | Platform | Required for |
|---|---|---|
| **NVDA + Firefox or Chrome** | Windows | every in-scope repo |
| **VoiceOver + Safari** | macOS | every in-scope repo |
| **VoiceOver + Safari** | iOS | any repository with a mobile-web/PWA surface, map UI, or touch targets |

JAWS + Chrome/Edge is the enterprise baseline; add it for any repo with a named government/enterprise client. NVDA and VoiceOver are free, so cost is never the reason a row is skipped.

**Resolve pending rows honestly:** each release either ships a completed, dated
human walkthrough, remains blocked, or qualifies for and explicitly invokes
§2.0. A pending row stays open under a provisional release; synthetic evidence
never checks it off.

### 2.2 The 6 WCAG 2.2 AA success criteria — explicit handling

These are new in 2.2 and most are partly review-gated because tooling under-covers them. Every in-scope repo states pass / N/A-with-reason for each:

| SC | Requirement | Primary gate |
|---|---|---|
| **2.4.11 Focus Not Obscured (Min)** | focused component not fully hidden by author content (sticky headers/cookie bars) | AUTO (Playwright focus-visibility spec) |
| **2.5.7 Dragging Movements** | every drag has a single-pointer alternative, including map pan/zoom and marker movement | REVIEW (committed note) + AUTO where a click alternative exists to assert |
| **2.5.8 Target Size (Min)** | pointer targets ≥ 24×24 CSS px | AUTO (axe `target-size` + stylelint) |
| **3.2.6 Consistent Help** | help mechanisms in same relative order across pages | REVIEW (multi-page navigation note) |
| **3.3.7 Redundant Entry** | previously entered info auto-populated/selectable | REVIEW (forms/auth checklist) |
| **3.3.8 Accessible Authentication (Min)** | no cognitive-function-test gate without an alternative | REVIEW (auth flows; N/A where no auth) |

> SC **4.1.1 Parsing** is obsolete in 2.2 — do **not** gate on it. The three AAA additions (2.4.12, 2.4.13, 3.3.9) are not required at AA; a repository may opt in where already met.

---

## 3. Plain-language gate (civic content)

Civic repositories serve a public that did not choose to be users and cannot route around bad copy. WCAG 2.2 AA has no plain-language SC at AA (3.1.5 is AAA), but ADA Title II and the civic mission make readable, non-jargon content a hard requirement here.

| Metric | Target | Measured by | Gate |
|---|---|---|---|
| Reading level of public-facing prose & RAG answer scaffolding (labels, errors, help, disclaimers) [A11Y-23] | **≤ Grade 8** (US) for static UI copy | `textstat` Flesch-Kincaid check in CI over extracted strings | merge-blocking (auto) |
| RAG-generated answer readability [A11Y-24] | reported, not hard-gated (model output varies) | `textstat` logged per eval run; regression > 1 grade flagged | review-gated |
| Plain-language editorial review [A11Y-25] | clear, jargon-defined, action-oriented | committed reviewer sign-off in release checklist | review-gated |

```python
# tests/test_plain_language.py  (civic repos)
import textstat
from app.i18n import extract_ui_strings   # en + es catalogs (see INTERNATIONALIZATION-STANDARD)

def test_ui_copy_reading_level():
    failures = {k: g for k, v in extract_ui_strings("en").items()
                if (g := textstat.flesch_kincaid_grade(v)) > 8.0}
    assert not failures, f"UI strings above grade 8: {failures}"
```

For bilingual civic repos, the plain-language gate runs against the EN catalog; the ES catalog is reviewed by a human (no reliable automated ES grade-level metric — declared review-gated, not skipped). i18n catalog mechanics live in `INTERNATIONALIZATION-STANDARD`; a human-validated accessibility status requires **both** locales to clear the screen-reader pass. A §2.0 provisional release instead records human locale review as pending, runs locale parity and rendered semantic checks for both locales, and keeps the language attribute (`lang`/`xml:lang`, SC 3.1.1/3.1.2) correct per rendered locale (AUTO — axe `html-has-lang`, `valid-lang`).

---

## 4. Legal context (why these targets, not softer ones)

Not a compliance treatise — the floor and the deadlines that set it.

- **ADA Title II (2024 final rule, deadlines extended Apr 2026):** state/local-government web content must meet **WCAG 2.1 AA** — **Apr 26 2027** (pop. ≥ 50,000) / **Apr 26 2028** (< 50,000 + special districts). Civic scorecards, public-service applications, maps, and transit data products can fall within this rule when adopted by or for a public entity. Any repository with a named public-entity client records its applicable deadline in `ROADMAP.md`. We target 2.2 AA (a superset) so a 2.1 AA deadline is met automatically.
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
