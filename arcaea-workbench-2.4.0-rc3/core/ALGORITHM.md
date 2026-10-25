# Allocation snapshot 1.2

This is a heuristic intent model, not an official judgement emulator or a certified physical simulation. The parser, arc-chain reconstruction, full-duration hold reservations, beam search and theme exporter derive from snapshot 1.1. No chart-specific hand overrides or timestamp exceptions were added.

## Decision order

1. Parse AFF and reconstruct operational units. Preserve canonical same-color arc chains and unified arc-head presses. Existing provisional adjacent-color reductions remain; hidden-group exclusions remain a review policy rather than an assertion about game judgement.
2. Calculate full-contact multi-touch demand from these units before allocation. Hold occupancy is not shortened to make a section fit two fingers. More than two required contacts creates candidate episodes, independent of which tasks the beam eventually omits. These candidates are not proof of required fingers under every game tolerance or arc trick.
3. Derive global idle gaps and singleton phrases from complete unit demand, including unassigned units. Compare permitted alternating and paired templates.
4. Search hand assignments with beam width 128. Minimize omissions first, then summed preference costs. Finger occupancy and incompatible simultaneous ownership remain constraints; comfort is a soft preference.
5. Export source-bound sequences and visualization copies; keep original files and backups. Added markers do not create playable notes.

## Changes from 1.1

### True idle reset

A gap of at least 160 ms, with no active or new operational input, clears decision-state endpoints, press-history, recent-run and pattern memory. The threshold is inclusive. Active holds/arcs prevent this reset. There is no new taper or relief across 100–159 ms. The old 150 ms relative-rhythm phrase break is removed.

Prior output stays in archival history, but the optimizer no longer scores travel from the old posture after a qualifying reset. The next phrase starts with natural-posture preferences. This is an explicit modelling approximation, not proof that a physical hand can return home in 160 ms. Full-plan reset transfers retain direct endpoint distance for inspection and are labelled `reset_gap_unmodelled`; they must not be scored as measured movement. Compact sequences expose these gaps in `flow_context.resets` for future metric consumers.

`reset_min_ms` controls the boundary. Legacy `reset_gap_multiplier` and `reset_move_ms` remain accepted for old configuration compatibility but no longer control resets. A BPM-dependent threshold is deliberately not guessed from this small corpus.

### Paired-template eligibility

Alternation remains the default. A paired template is admitted only if it has at least two repeat opportunities, mean close-pair affinity exp(-(distance / 0.20)^2) >= 0.65, and mean between-pair travel exceeds mean within-pair travel by at least 0.08 analysis-plane units. The last value tests repeated spatial contrast; it is not the old per-pair distance cutoff.

Eligible pairs retain smooth spatial relief and a phrase consistency penalty. Stationary streams and ordinary traversals no longer receive a paired template merely because repeated tapping is cheap. This is geometric evidence, not a learned chart-pattern classifier. Template consistency is still soft and feasibility can override it. Phrase boundaries at 200 ms and simultaneous packets remain limitations.

### Obstruction preference

Represent each arm by a segment from its bottom corner to its current contact. Penalize a contact approaching the opposite arm segment, including collinear overlap on the ground line. Cost = 10 * max(0, 1 - minimum_clearance / 0.12)^2. Simultaneous pairs are scored symmetrically once; sequential actions use the last opposite-hand contact or the currently active arc position.

This is a 2D endpoint/forearm clearance proxy, not a complete crossing or upper/lower-arm feasibility solver. It does not model hardware, arm width, acceleration or reversals, and does not prohibit out-of-bounds positions. Those omissions matter when interpreting a remaining awkward assignment.

### Multi-touch visibility

Green candidate diamonds are added to ground taps, hold starts and arc taps occurring in detected demand episodes, even when the search assigned those operations to a hand. The hand color is provisional in these regions. Instantaneous episodes use their exact timestamp; sustained episodes are half-open intervals. Existing green unresolved and player-review markers remain, so green is a review signal, not a unique diagnosis.

Read exact `multitouch.episodes` for demand; `multitouch.windows` joins nearby episodes within 200 ms for review convenience only. Do not use joined gaps as evidence of continuous extra-contact demand. Keep confirmed exclusion masks separate. Do not compute two-hand difficulty through candidate sections without resolving or explicitly masking them. Candidates are calculated after existing semantic arc reductions, whose provisional status is retained in extraction metadata.

## Unchanged costs and constraints

- Movement: direct endpoint distance / available seconds.
- Hold: immediate activation plus full source-duration reservation, no stationary duration exertion.
- Arc: blue-left/red-right weighted preference, not mandatory; geometry/occupancy may require exceptions.
- Costs also include rapid repeated presses, natural starts, simultaneous tap checkpoints, home-region comfort and ground-side preference.
- No acceleration, reversal or direction-switching penalty.
- Search confidence is agreement among retained alternatives, not a calibrated probability.

Manual corrections remain source-hash-bound `--hand-overrides` inputs. Backtests measure changes and structural validity, not community agreement. Player review is still needed.
