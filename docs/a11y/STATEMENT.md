# Accessibility statement

Last verified: 2026-09-02
Recheck cadence: every release, and whenever a surface in the table below gains
a page or an output format.

## The target, and what is claimed against it

The conformance **target** is **WCAG 2.1 Level AA**.

No conformance **claim** is made. WCAG's own conformance-claim requirements ask
for a full evaluation of each page, and the only evaluation this project has
run is automated. Automated tooling detects a minority of WCAG failures by
construction; it cannot tell you whether a page is usable with a screen reader.
Saying "WCAG 2.1 AA conformant" on the strength of two automated runners would
be the same kind of overclaim this validator exists to refuse, so this document
says what was checked and by what, and leaves the claim unmade.

`docs/a11y/2026-08-21-automated-only-not-a-substitute.md` records the same
position from the attempt at a manual walkthrough, and #74 tracks the real one.

## Surfaces, and what has actually been checked

| Surface | Target | Checked by | Blocking |
| --- | --- | --- | --- |
| Terminal output (`--format text`) | WCAG 2.1 AA where applicable | Design review only: severity is carried by a word, never colour, and no ANSI colour is emitted at all, so `NO_COLOR` has nothing to disable | Design invariant, pinned by `tests/test_report.py` |
| HTML report (`--format html`) | WCAG 2.1 AA | axe + HTML_CodeSniffer at `WCAG2AA`, on a freshly generated report, every pull request | Yes (`make a11y`) |
| Playground page (`web/index.html`) | WCAG 2.1 AA | The same two runners, **on the `?a11y-static=1` branch**, which deliberately skips the Pyodide boot. The booted state is not audited | Yes (`make a11y`) |
| Rule catalog (`web/rules/`, 45 published pages) | WCAG 2.1 AA | The same two runners, on the index and one rule page. All 44 come from one template in `scripts/generate_rules_doc.py`, which `--check` gates and `tests/test_generate_rules_doc.py` pins | Yes (`make a11y`), since 2026-08-27 |
| The deployed playground | WCAG 2.1 AA | `scripts/pa11y-ci-live.cjs` against the live URL after each deploy and weekly, plus `scripts/check-playground-boots.cjs`, which drives the real page in a real browser | Yes (`pages.yml`, `playground-deployment.yml`) |
| VS Code extension (`editor/vscode/`) | Not evaluated | Nothing. It is unpublished, and its UI is VS Code's own | No |
| Machine formats (JSON, SARIF, Markdown, GitHub) | Not applicable | Not human-rendered surfaces | No |

## What the last check found

The rule catalog entered the blocking gate on 2026-08-27 and failed it: 141
colour-contrast errors and 43 "links must be distinguishable without relying on
colour" errors across the index and a rule page. Both were one defect each in
one shared stylesheet. The pages declared `color-scheme: light dark` and then
set no `color` or `background` on `body`, so a user agent in dark mode painted
light text on an unpainted canvas and every text element failed, `<h1>` and
body copy included; and links were `color: inherit` with `text-decoration:
none`, which left them not distinguishable from body text by any means.

Both are fixed, every colour is now stated for both schemes with its computed
ratio recorded in the generator, and all four audited URLs pass. The 45 pages
had been published since the catalog shipped, behind the accessibility section
of the README, with no runner ever pointed at them. That is the honest reason
this table now names its surfaces one at a time.

## Known gaps

These are open, and none of them is closed by another scanner.

- **No screen-reader or keyboard walkthrough by a person** (#74). This is the
  gap that matters most and the one automation cannot fill. It is gated on a
  human with assistive technology, ideally a real AT user, and
  `docs/MULTIYEAR-PLAN.md` lists it under standing work that no phase owns
  rather than scheduling it.
- **No Lighthouse pass and no committed bundle baseline.** Tracked in the
  performance section of `docs/CONFORMANCE-GAPS.md`.
- **No ACR or VPAT.** Neither would be honest without the walkthrough above.
- **The booted playground is unaudited.** `?a11y-static=1` skips `boot()`, so
  what the runners see is the pre-Pyodide page. `scripts/check-playground-boots.cjs`
  proves the booted page *works*; nothing yet proves it is accessible.

## Reporting a problem

If an output is hard to read or operate with assistive technology, that is a
bug. Open an issue at
<https://github.com/ChelseaKR/tods-validate/issues>, or email the address in
`SECURITY.md` if you would rather not do so publicly. Please say which surface
and which assistive technology, including versions; both change behaviour.

<!-- doc-currency: sha256=b44812ff36bb -->
