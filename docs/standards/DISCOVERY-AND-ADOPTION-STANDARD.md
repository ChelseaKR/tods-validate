# Discovery & Adoption Standard

The single owning standard for whether a finished project can be *found* and *installed* by someone who does not already know it exists. The 2026-09-01 DevRel audit measured the portfolio at forty green CI runs and zero external referrers: supply was over-built and distribution was zero, because every distribution task depended on someone remembering to do it. This standard turns those tasks into controls the weekly conformance sweep checks by itself. Every other standard in this set owns what a project *is*; this one owns the six facts about a project that a stranger meets before its first line of code, plus the one send that must never be automated.

**Why this exists.** A task that needs a person to remember it competes with that person's job and loses. A control does not.

---

## 0. Scope and applicability

Applies to every public repository. A repository states `Discovery & Adoption: Applies` or `N/A — <one-line reason>` in its README conformance table once this standard is promoted (§8); until then the row is optional and recognized. Individual controls scope themselves:

| Control | Applies when |
|---|---|
| DISC-01, DISC-02 | The repository's GitHub About names a homepage. A repository with no published site is `n/a` for both. |
| DISC-03 | Always. |
| DISC-06 | The repository is public. A private repository shows no card and is `n/a`. |
| DISC-04 | A searched-for vocabulary is recorded for the repository in `distribution-terms.yml`; otherwise the control is `not measured`, never passed. |
| DISC-05 | The repository is public and ships a distributable: a `[project]` name in `pyproject.toml`, a publishable `package.json`, or an `action.yml`. A private repository distributes nothing and is `n/a`. |
| DISC-07 | Any outward-facing send is prepared. |
| DISC-08 | The repository has a money page — `SUPPORT.md`, `FUNDING.yml`, `docs/support.md`, or a `support/index.html` — that carries at least one http(s) link. A `FUNDING.yml` whose every key is deliberately empty, or a `SUPPORT.md` with no URLs, has nothing to check and is `n/a`. |

`n/a` and `not measured` are different states and are reported as such. A control the checker could not evaluate — no network, no `gh`, a fetch that failed — is `not measured`, and a report that rendered it as a pass or a fail would be reintroducing the defect this portfolio's own work names: an absence rendered as a value.

---

## 1. The published site

| Metric | Target | Measured by | Gate |
|---|---|---|---|
| Open Graph on the shareable URL [DISC-01] | The homepage named in the GitHub About emits `og:title`, `og:description`, and an `og:image` that is exactly 1200×630 pixels, on the exact URL a person would paste | `conformance_check.py` fetches the homepage, reads the `og:*` meta tags, fetches the image and reads its dimensions from the PNG/JPEG/GIF/WebP header | AUTO-GATE (advisory until promoted, §8) |
| Backlink to the source [DISC-02] | The homepage links to `github.com/<owner>/<repo>` | The fetched HTML contains that link | AUTO-GATE (advisory until promoted, §8) |

A homepage that neither links back to the repository nor carries the owner's name in its host cannot be told apart from an unrelated site, so DISC-01 is `not measured` rather than judged against a page that may belong to someone else; DISC-02 fails, which is the finding.

## 2. The README's first screen

| Metric | Target | Measured by | Gate |
|---|---|---|---|
| A runnable command in the first fifty lines [DISC-03] | Within the first 50 lines of `README.md`, a fenced block holds a command a visitor can paste and run, and it produces real output | `conformance_check.py` finds a fenced shell block, or a fenced block whose first non-comment line starts with a known command, in the first 50 lines. **Whether the command produces real output is not something a text scan can know**; that half is owned by the repository's own README test, the way `DOCUMENTATION-STANDARD.md` §9 already asks | AUTO-GATE (advisory until promoted, §8) |

## 3. Findability

| Metric | Target | Measured by | Gate |
|---|---|---|---|
| A searched-for term in the About [DISC-04] | The GitHub description and topics state at least one term people actually search for in the project's domain | `conformance_check.py` matches the About against the repository's entry in `distribution-terms.yml`; a term matches when every one of its words appears | AUTO-GATE (advisory until promoted, §8) |

`distribution-terms.yml` is the vocabulary and it is evidence-only: every term carries, in a comment, the query it came from and how the portfolio ranked for it. The checker never invents a term, and a repository with no entry is `not measured`. The audit's own finding is the reason this control exists: the portfolio ranked first on queries nobody types and was absent from every query with volume, because distinctive project names share no tokens with how people search.

## 4. Distributables

| Metric | Target | Measured by | Gate |
|---|---|---|---|
| Install name reserved and stated [DISC-05] | If a distributable exists, its install name is reserved on the relevant registry *by this repository* and stated in the GitHub About description | `conformance_check.py` reads the install name from `pyproject.toml` or `package.json`, asks PyPI or npm for the project, and requires its project URLs to point at this repository — a name that exists but points elsewhere is a collision, not a reservation — then requires the About description to contain the name | AUTO-GATE (advisory until promoted, §8) |

GitHub Marketplace listings for Actions cannot be queried through an API. A repository whose only distributable is an `action.yml` is `not measured` for DISC-05, and its listing state is checked by a person.

## 5. The social preview

| Metric | Target | Measured by | Gate |
|---|---|---|---|
| Custom social preview [DISC-06] | A custom social preview image is uploaded; no repository ships GitHub's default card | `conformance_check.py` asks the GitHub GraphQL API for `usesCustomOpenGraphImage` | AUTO-GATE (advisory until promoted, §8) |

## 6. Outward-facing sends

| Metric | Target | Measured by | Gate |
|---|---|---|---|
| A dated human approval artifact per send [DISC-07] | Any outward-facing send — a post to a community, a pull request or issue on someone else's repository, an email, a CFP submission — carries a committed artifact recording who approved it and when, before it goes out | A file under `docs/outreach/` named `YYYY-MM-DD-<slug>.md`, stating the destination, the text as sent, and an `Approved by: <name>, <YYYY-MM-DD>` line. Reviewed, not parsed: the checker has no signal for this control and does not pretend to | REVIEW-GATE |

This is the one control in this standard that must never become automatic. The asset a maintainer actually owns in the rooms where these sends land is a reputation for saying true, checked things under their own name. An agent may get a send to one-click-ready. It may not click.

## 7. The money page

| Metric | Target | Measured by | Gate |
|---|---|---|---|
| The money page has no dead links [DISC-08] | A repository whose `SUPPORT.md`, `FUNDING.yml`, `docs/support.md`, or `support/index.html` carries http(s) links runs a link check over those files in CI | `conformance_check.py` reads the money-page files present; those with no http(s) link are `n/a`; for the rest it requires a workflow that both invokes a link checker and names at least one of them | AUTO-GATE (advisory until promoted, §8) |

Several repositories carry a `FUNDING.yml` whose every key is empty on purpose — the file exists to say the project takes no money. There is no link in it to break, and a link-check requirement would be the wrong ask; the control reports `n/a` for them.

This control was added alongside the six above from a different provenance: the 2026-09-01 monetization plan found the portfolio's best-trafficked support page linking to a URL that returned 404. The DevRel audit did not name it; the plan did.

---

## 8. Advisory phase and promotion

Every AUTO-GATE control in this standard lands **advisory**: `conformance_check.py` runs it, reports it in its own table with one of four states (`pass`, `fail`, `n/a`, `not measured`), and excludes it from the score, from `--strict`, from `--min-score`, and from regression detection. A repository's number cannot move because this standard was introduced, and the weekly sweep cannot turn red because of it.

A control is promoted — moved from `ADVISORY_CHECKS` into the scored set, with this document moved from `ADVISORY_STANDARD_DOCUMENTS` into the canonical set once every control in it has been — when, and only when:

1. four consecutive weekly sweeps show the control passing on at least 80% of the repositories it applies to (`n/a` and `not measured` excluded from the denominator), and
2. every remaining failure carries a waiver in `waivers.yml`, or an open issue the README's conformance row names, and
3. the promotion is recorded in `CHANGELOG.md` with the four sweep dates and the pass rate on each.

Promotion is one release of this repository. Consumers pinned to an earlier release keep the advisory behavior until they bump, which is the bump mechanism already in place for every other control.

---

## 9. What each repo actually ships

1. **Nothing new for a repository that already does these things.** The controls read what is there: the About, the homepage, the README, the registry, the workflows.
2. **A vocabulary entry** in `distribution-terms.yml` (this repository) for any project that wants DISC-04 measured, with the search evidence in a comment.
3. **An outreach record** under `docs/outreach/` for every outward-facing send (§6).
4. **A link-check workflow** naming the money page, for any repository that has one (§7).

---

Last verified: 2026-10-02 · Recheck cadence: quarterly, and on any change to how GitHub exposes the About, the social preview, or the Marketplace.
