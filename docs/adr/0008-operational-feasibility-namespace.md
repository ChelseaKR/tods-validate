# 0008: checks that are not entailed by the spec get their own ID namespace

- Status: accepted (2026-09-07)
- Date: 2026-09-07
- Relates to: #208 (the check that forced the decision), #189 (local-policy
  thresholds, which should reuse this namespace), ADR 0004 (rules as a
  registry), ADR 0007 (a partial companion read is not a read)

## Context

`TODS-W409` carries this argument in its own description:

> Within one run, an event ends at one location but the next event in
> `event_sequence` order starts somewhere else. An operator is one person who
> cannot teleport...

Its implementation compares two location **identifiers** for equality. It
answers "do these two events name the same place?" — not "could a person get
from the first place to the second in the time given?". A pick in which an
operator finishes downtown at 14:00, declares a correct five-minute deadhead,
and starts a run thirty kilometres away at 14:05 satisfies W409 and every other
rule in the registry, and is not something a human being can do. It is the exact
failure the rule's prose describes and the one it cannot see.

Closing that gap requires asserting a travel-time model. **The TODS spec says
nothing about travel time.** There is no section to cite, no threshold the
standard states, and no reading of the standard under which a slow deadhead is
non-conformant.

That collides with a promise this project has made everywhere it renders a
finding. Every `TODS-` rule carries a `spec_section` URL; `docs/rules.md`, SARIF
`helpUri`, the editor hover and the published rule catalog all surface it. A
producer who receives a `TODS-` finding is entitled to read it as *the standard
requires this*. Issuing an opinion under a `TODS-` ID would spend that promise
on a judgement, and would do so invisibly — the finding would look exactly like
the forty-five that are genuinely spec-cited.

## Decision

### 1. A second namespace, `OPS-`, for checks the spec does not entail

`OPS-x0xx` is operational feasibility: does the schedule describe something a
person and a vehicle can actually do? Its rules cite the ADR that decided them,
not the spec.

Both halves of the citation promise are now enforced in
`tests/test_registry.py`:

- every `TODS-` rule's `spec_section` is a URL under the TODS specification;
- **no rule outside `TODS-` carries one.**

The second assertion is the one that matters. Testing only the first would pass
vacuously for an `OPS-` rule that cited the spec anyway, which is precisely the
misrepresentation the namespace exists to prevent.

`#189` (local-policy thresholds an agency declares) should reuse `OPS-` rather
than opening a third namespace. It answers a different question with the same
standing: not entailed by the spec, worth checking, and honest about which it
is.

### 2. Its own category, not `advisory`

`feasibility` is a new value in `CATEGORIES`, opt-in like `coverage` and
`advisory`, and deliberately not folded into either. `coverage` and `advisory`
are judgement calls *about how to read the spec*. `feasibility` is not about the
spec at all. Keeping them apart is what lets `--enable advisory` remain a
statement about spec interpretation, and it gives the band its own line in the
coverage manifest.

Consequence, and it is intentional: the `strict` and `ingest-ready` profiles
enable `coverage` and `advisory` and are therefore **unchanged**. A feed that
validated clean yesterday validates byte-identically today. Nothing about the
default path moves.

### 3. Straight-line distance, and the ceiling is stated in every finding

Distance is great-circle between companion-GTFS stop coordinates: standard
library, no projection, no road network, no network access, still deterministic
and offline.

Great-circle **understates** road distance, so the implied speed it computes is
a lower bound on the speed actually required. The check can therefore only ever
make a movement look *more* feasible than it is — the right direction of error
for a tool asserting that a schedule cannot be worked.

The default ceiling is **120 km/h straight-line**
(`DEFAULT_MAX_IMPLIED_SPEED_KPH`), overridable with `max-implied-speed-kph`. It
is set high on purpose. A "realistic" ceiling measured against road distance
would fire on movements that are genuinely workable, because the distance being
divided is the straight line and not the route. At 120 km/h straight-line, a
flagged movement is one no ground vehicle could make regardless of the route it
took.

The number is a judgement, not a fact, so **every finding quotes the ceiling in
force**, the way the severity-remap disclosure already works. An impossible
configured value (zero, negative, non-finite, or a boolean) is a config error
and exits 2 rather than being clamped into a different check than the operator
asked for.

### 4. Both kinds of movement, not only the gap between events

The check evaluates two things per run:

- the movement declared **within** one event (its own start to its own end);
- the gap **between** two consecutive events.

Only the second was in the original proposal. The first is the one the
motivating case needs: a correctly-declared five-minute deadhead across thirty
kilometres declares the impossible movement *inside itself*, and every
consecutive pair around it connects perfectly. A between-events-only check
would have been unable to fire on the example that justified it.

### 5. What cannot be measured is reported, never passed

This is the load-bearing part. Two stops without coordinates are not "close
together", and a package with no companion GTFS has not been checked and found
fine.

`Measurement` records, per rule, how many units it reached a verdict on and how
many it could not, and `validate()` folds it into that rule's `RuleOutcome`.
`unmeasurable` is never added to `measured` and never counted as a unit that
passed. A measurement reporting unmeasurable units must carry a reason —
enforced in `__post_init__`, because an undisclosed gap reads as a clean result.

`gtfs_companion.parse_coordinate` returns `None` for a blank, malformed,
non-finite or out-of-range coordinate rather than a default. `(0, 0)` is a real
point in the Gulf of Guinea: a blank latitude coerced to zero does not fail
loudly, it produces a confident finding about an operator who is not at fault.
A `NaN` is the mirror image — every comparison against it is false, so the
movement would silently pass.

The project's own valid fixture demonstrates the result. Its run events start
and end at `garage`, which is not a GTFS stop, so a clean run reports
`14 of 20 movements measured; 6 unmeasurable`. Nothing is wrong with that feed.
The point is that "no problems found" now also says how much of the check it was
able to apply.

## Consequences

- The rule catalog generator now raises on a rule it cannot place in a
  documented band. It previously grouped by a single digit and **silently
  skipped** anything that did not match, so a rule in a new namespace would
  have been dropped from `docs/rules.md` and from the published catalog with no
  error, and `--check` would have compared that incomplete catalog against
  itself and passed.
- Two tests that asserted the `TODS-` prefix as a proxy for something else were
  rewritten to assert the thing itself: the workspace privacy test now checks
  that stored IDs are registered rule IDs, which is both the property it meant
  and strictly stronger.
- The distance model is straight-line and will stay that way. Anything better
  needs a road network, which would change what this project depends on and what
  it can promise about running offline.

## Alternatives considered

**Extend `TODS-W409`.** Rejected: it would put an uncitable judgement behind a
spec-cited ID, and would change the meaning of an existing rule's findings for
every consumer already baselining against it.

**Hard-code the ceiling with no configuration.** Rejected: the number is the
most contestable thing in the check, and an agency in dense urban traffic and
one running interurban coaches do not share it.

**Require the agency to declare a ceiling, with no default.** Defensible, and
rejected for a narrower reason than it looks: with no default the check is off
in practice, and a check nobody runs finds nothing. The compromise is a default
that is generous enough to be uncontroversial, disclosed in every message it
produces.
