# Accessibility review, 2026-08-21 — automated and static only

This is **not** the VoiceOver/keyboard walkthrough #74 asks for. It records
what an automated coding-agent session could actually verify without a
screen reader or a working browser, and is explicit about what it could not
do, per that issue's own instruction: "Automated checks are not a
substitute for this task."

## Environment

This review ran inside a sandboxed CLI coding-agent session with no audio
output and no connected browser (the `claude-in-chrome` browser tool
reported "Browser extension is not connected" when invoked). There is no
macOS VoiceOver, no screen, and no way to hear or observe spoken output in
this environment. The tasks below that require a live screen reader are
explicitly marked not done, not approximated.

## What was actually verified

**`make a11y` (pa11y-ci: axe-core + HTML_CodeSniffer, WCAG 2.1 AA)**, run
live against a local copy of `web/index.html` and a freshly generated HTML
report: 0 errors on both pages. Then deliberately regressed — removed the
`<label for="files">` on the file input — and re-ran: the gate correctly
failed with 4 real violations naming the missing label, confirming it is a
working, non-rubber-stamp gate (see #75, closed with this evidence). The
regression was reverted immediately; nothing was committed.

**Static source review of `web/index.html`**:

- Landmark/heading structure: one `<main>`, `<h1>tods-validate playground</h1>`,
  `<h2 id="report-heading" tabindex="-1">Validation report</h2>`. The file
  input has an explicit `<label for="files">` plus `aria-describedby`
  pointing at help text. The status line is `<p id="status" role="status">`,
  so status changes are announced without moving focus.
- After validation completes, `reportHeading.focus()` is called
  (`web/index.html`), moving keyboard/screen-reader focus to the "Validation
  report" heading — the reason `tabindex="-1"` is on an `<h2>`. This is the
  correct pattern for telling an AT user results are ready without them
  having to hunt for them, *if* it actually fires — not exercised live here.
- Severity is carried in text, not color alone: `report.py`'s HTML renderer
  emits `<td class='sev sev-...'>{severity.name}</td>` — the literal word
  ERROR/WARNING/INFO is always in the cell's text content, with the CSS
  class only adding color. Verified by reading the renderer
  (`src/tods_validate/report.py`), not by looking at rendered output.

None of the above is a substitute for actually tabbing through the live
page or listening to VoiceOver read it. It is evidence the markup was
*authored* with accessibility in mind and that the automated scanner
agrees; it is not evidence of what the experience actually sounds or feels
like using assistive technology.

## Not done — genuinely blocked in this environment, not skipped

- Keyboard-only walkthrough of the *live* playground
  (`https://chelseakr.github.io/tods-validate/`): not performed. No working
  browser tool was available this session.
- VoiceOver walkthrough (macOS + browser + OS versions recorded, reading a
  generated report and the playground linearly): not performed at all. This
  needs a human with a Mac.
- Confirming `reportHeading.focus()` and the `role="status"` announcements
  actually produce sensible spoken output, as opposed to just being present
  in the markup: not performed.

## A discovered blocker, found while attempting this

While checking `web/index.html` for the walkthrough, its Pyodide boot
sequence turned out to hardcode `micropip.install("tods-validate==0.9.1")`.
PyPI's latest published version is 0.9.0 (v0.9.1 was tagged and signed but
never actually published — see #136); a direct check,
`pip install --dry-run "tods-validate==0.9.1"`, fails with "No matching
distribution found". If that holds in a real browser too (unverified here,
no working browser tool), **the deployed playground itself does not
currently boot for any visitor**, which would make any walkthrough of it
impossible until #136 is resolved — filed and escalated there, not
re-litigated here.

## What should happen next

1. Resolve #136 (v0.9.1/current publish gap), and specifically confirm
   whether the playground actually boots in a real browser afterward.
2. A human with a Mac, a browser, and VoiceOver performs the actual
   walkthrough this issue asks for, once (1) is confirmed. This document is
   scaffolding for that session, not a replacement for it.
3. File focused follow-up issues for anything that walkthrough finds
   blocked or confusing, per #74's own "Done when" list.

#74 is left open. Nothing here should be read as satisfying it.
