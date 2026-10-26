# Allocation algorithm — frozen MVP 1.0

This is a deterministic beam-search heuristic for candidate two-finger execution.
It is neither a learned model nor a globally optimal physical simulation. There
are no song names or hand overrides tied to particular timestamps in the solver.

## 1. Parse and preserve

`audit.py` reads UTF-8 AFF (optional BOM), the header separator, timing groups,
timing, tap, hold, arc and arctap records. It preserves original statements and
source spans. Structural warnings stop the public analysis command. Supported
arc curves are `s`, `b`, `si`, `so`, `sisi`, `siso`, `sosi`, `soso`.
Unsupported special effects are not certified merely because parsing succeeds.

Times use the AFF clock; AudioOffset is retained in the original, not added to
operation timestamps. Floor lane k maps to x = 0.5k − 0.75, y = 0. Arc/sky x is
AFF x, and y = (1 + 4.5 AFF_y)/8.5. Coordinates can extend beyond [0,1]. This is an
unprojected analysis plane, not a physical screen or biomechanical length model.

## 2. Extract contact operations

No-input groups are excluded. A reversible policy additionally excludes an input
whose entire source interval lies in a hidden group. This is an **intent-review
assumption**, not a claim that `hidegroup` disables official judgement. Source IDs
of excluded records remain in the sequence; use `--include-hidden` to restore them.

Matching-color arc segments join only across unique endpoint links, within 1 ms
and 0.01 AFF units per coordinate. Zero-duration connectors can preserve ownership
but disconnected connectors never imply a link. Coincident duplicate geometry is
canonicalized with recorded aliases. All original source IDs are retained.

A floor tap is a point operation. A hold starts at its source activation time.
Only holds for which both existing provisional schedules agree on one tick can
release at the later candidate tick; other holds reserve their source duration.
Ordinary arcs reserve the entire operational chain. There is no blanket single-
tick arc early release. Exact coincident sky taps can join an arc head; ambiguous
multiple heads are explicitly recorded when one head takes the composite tap.

## 3. Provisional adjacent-color exception

`adjacent_arcs.py` recognizes opposite-color, translation-identical parallel
segments, equal start time and end time within 1 ms. A maximum 0.18 AFF horizontal
separation is a **recognition hypothesis**, not a measured game hitbox. Diverging
arcs and arbitrary intersections are not merged. If sky taps on the midpoint
path cover both provisional tick schedules within the bounded timing window,
those taps support the pair. Otherwise a provisional shared-contact task remains.
Source geometry, support actions and assumptions remain in `extraction`.

This does not solve every performance arc, overlap, collision or coloring-state
case. Breach's passage around 151394 is still a known tolerance-model limitation.

## 4. Phrase context

Singleton action runs use a 200 ms continuation threshold. Hold activations and
new arc acquisitions participate in this context; continuous reserved contact
cannot be treated as idle time. A sufficiently long gap relative to neighboring
rhythm gives a soft phrase/reset candidate. True global idle gaps use the larger
of 1500 ms, eight median start gaps and three reset-movement intervals.

Spatial pair candidates have successive compatible tap types, interval below
200 ms, and separation at most 0.08 analysis units. Neighbors separated by more
than 0.2 units, a packet boundary or a longer gap delimit the pair. In runs of six
or more actions, pair relief is enabled only if pairs cover at least 60% of that
run. Sparse local pairs in a traversal therefore retain the stream's alternation
cost. This changes costs, not feasibility: a sufficiently favorable physical
alternative can still use repeated inputs. Mid-stream strategy changes are not
formally optimized as a separate cognitive metric.

## 5. Search and penalties

Each beam state stores the last reserved operation per hand, recent press times,
recent hand history and accumulated score. At each simultaneous packet, enumerate
feasible allocations to L/R plus explicit unresolved outcomes. Rank first by
unresolved-operation count and then total cost. Keep 128 states by default; retain
alternative agreement as an internal diagnostic, not calibrated confidence.

Hard restrictions include one reserved operation per finger, no nonzero movement
in zero available time, and the current same-color ownership restriction. The
provisional adjacent-color exception is handled separately during extraction.

Soft costs combine distance/available-seconds, recent repeated-press strain,
alternation preference, arc-color/hand preference, natural starts and checkpoint
posture. Isolated pair relief reduces repeat penalties; a sustained stream keeps
its alternation preference from the beginning. Recent activity is measured over
600 ms. Hold activation is an action even though sustained hold exertion is not
being scored here.

Ground-side aversion grows quadratically with cross-body reach and fades with
height. Recent opposite-hand activity on its own side adds a ground takeover
cost. Simultaneous packet territory costs are evaluated jointly to avoid source-
order bias. These are ergonomic heuristics, not a full arm-intersection solver.

Because the beam explores both starting hands, a locally counter-intuitive start
can win when the whole phrase is smoother. New arc acquisition now participates
in phrase continuity: avoiding a repeated hand at the closing arc can outweigh
starting on the note's natural side. No extra per-chart forced-hand repair is used.

## Latest audit points

- Pragmatism 77327–77844 now remains alternating rather than mixing pair/stream
  approaches. The earlier 31724–32672 pair-dominated phrase retains pair relief.
- Breach 48487 begins L and alternates through the L arc at 48836; 51976 begins R
  and alternates through the R arc at 52325. Both are general-context outcomes.
- Pragmatism 146894 remains an extreme trade-off example, not a solved policy for
  intentional strategy switching. Its current result is provided for review.
- Riven's difficult residual cases and green regions remain review cases.

## Output and visualization

The public sequence is a compact JSON interchange document: one operation per
line, original-source hash, preferences, provenance, arc geometry and review data.
It omits intermediate geometry samples, beam traces and duplicated movement paths.

`color_aff.py` verifies the source hash and operation structure, checks hand
reservations, writes/verifies a backup, renders to a temporary output, and validates
input-center/time and sustained-geometry multisets before committing the output.
It never changes judged arc colors to represent hands. Added markers use no-input
geometry. Runtime rendering and official judgement equivalence are not certified.

No distance/movement/note/Peak/Arc/block difficulty scores are calculated here.
Raw model candidates, search omissions and player-confirmed exclusions are separate;
future scoring must not bridge movement paths across an applied exclusion mask.
