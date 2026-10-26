# Output contract and proposed live editor

Status: current contract inspected from frozen snapshot-1.2 code. Editor architecture below is a proposal, not implemented functionality.

## Current input bundle

Load the original AFF together with its `.sequence.json`. The JSON is standard UTF-8 JSON, with one operational-unit object per line for readability; it is not JSONL and does not contain dense 1 ms/4 ms trajectory samples. A unit is an operational task, not necessarily one source event or one scored note. Joined arc chains and unified arc-head presses can share one unit.

| JSON field | Current meaning |
|---|---|
| format | `arcaea-input-sequence/1`, exchange format version |
| algorithm_version | `snapshot-1.2`, generator version |
| chart | Source filename; display label, not unique identity |
| sha256 | Exact original AFF byte hash |
| structure_sha256 | Hash of unit definitions, excluding their hand field |
| coordinate_system, time_unit | Analysis-plane coordinates and AFF-clock milliseconds; AudioOffset is not applied |
| units | Allocation records |
| arc_geometry | Source arc segment IDs, times, raw AFF endpoint geometry, curve type, original color and timing group |
| extraction | Joining/alias records, hidden-input policy and provisional arc reductions |
| flow_context | Reset intervals, phrase information and hold policy |
| multitouch | Conservative demand episodes, grouped review windows, optional user-confirmed exclusion masks |
| review_windows | Solver-omission windows, distinct from multi-touch episodes |
| visual_review_markers, mechanic_review | Optional annotations |
| preferences, configuration | Generator settings |
| summary | Statistics from the generator run; stale after direct editing |
| limitations, certified_for_max | Explicit model limitations; no certification of perfect execution |

Unit fields:

| Field | Type / meaning |
|---|---|
| unit_id | String, stable within this exact extraction; not guaranteed across parser versions |
| kind | floor_tap, sky_tap, wide_sky_tap, hold, arc |
| start_ms, end_ms | AFF-clock times; equal for instantaneous operations |
| hand | `L`, `R`, or null for unresolved; no exact-finger assignment field currently |
| start_position, end_position | Two-number arrays in analysis coordinates |
| source_event_ids | References to source AFF records |
| action_ids | IDs of fresh input actions grouped into the operation |
| arc_color | String such as `0`, `1`, `neutral`, or null; independent of assigned hand |
| fresh_press | Whether a fresh discrete press is required |

The analysis x coordinate follows AFF coordinates, including positions outside 0–1. Ground y is 0; sky analysis y = (1 + 4.5 * AFF_y) / 8.5. `arc_geometry.geometry` retains raw AFF y values, so do not mix those coordinate systems. Reconstruct curved paths from the geometry records and original curve evaluator; straight lines between a unit's two endpoints are insufficient. Use original AFF timing data for BPM-dependent future metrics and explicit audio-clock conversion.

The compact sequence does not carry the full planner's `paths` or detailed unresolved explanations. Reconstruct paths from corrected unit order and arc geometry, respecting gaps, resets and exclusion boundaries. The original AFF remains required by the current coloring exporter.

## Proposed project data

Keep four layers:

1. Immutable original AFF and generated baseline sequence.
2. Small correction document bound to source hash, baseline structure hash and baseline sequence digest. Include project revision, changes by unit ID, explicit review/exclusion intervals, and edit history.
3. Effective sequence: baseline plus corrections. All editing views, preview exports and metric calculations consume this same revision.
4. Recomputable derived cache: paths, diagnostics and metric results. Never treat old generator summaries as updated editor results.

A correction should identify its kind, target, previous/new value and optional reason. L/R changes and a whole arc-chain hand change are assignment edits. Split/merge, bridge changes and arc-contact release changes are structural edits requiring a separate extraction revision and migration of corrections; do not bypass the structural hash. Reanalysis must report corrections whose targets cannot be mapped.

Multi-touch is a segment-level review state, not a third value of `hand`. Distinguish candidate, confirmed multi-finger, dismissed candidate and unresolved. Excluding a segment from difficulty does not delete its notes or imply that the entire arc belongs to a third finger. Future exact-finger assignments need a contact/effector ID extension; do not overload L/R/null.

Use relative asset paths for portability and hashes for identity after folders move. An asset index/database may be rebuilt from project files later. The editor and metric engine should not depend on the current workbench folder layout.

## Interaction matching the sketch

Main area: searchable, time-sorted unit list with timestamp, type, hand, review status and source links. One expandable row for a joined arc chain; source segments and attached fresh presses appear beneath it. An attached arc-head tap cannot silently receive a different hand while remaining part of the same unit.

Right inspector: L/R/unresolved controls, selected-range hand swap, multi-touch review/exclusion controls, reason/comment, revert to baseline. Show the original algorithm choice beside the corrected choice. Provide undo/redo, timestamp jump and atomic autosave to the correction document. Start with assignment and interval edits; defer editing timing, geometry and segmentation.

A hand edit immediately updates the effective sequence and in-app preview. Validate reservations and simultaneous assignments; warn about zero-time transfer to a different coordinate. Keep a conflicting edit as a visibly invalid draft if desired, but do not silently publish a valid-looking preview or metric score. Confirmed multi-finger sections can remain review-only until a richer contact model exists.

Hot editing means immediate in-app changes without rerunning allocation. It does not promise that ArcCreate reloads externally overwritten AFFs. Keep AFF export as an explicit action using the frozen exporter until external reload behavior is verified. Re-optimizing a selected section should be a separate command with manual choices locked, not a side effect of each edit.

## Difficulty-module boundary

Proposed interface:

`evaluate(effective_sequence, source_geometry_and_timing, exclusion_policy, metric_config, revision) -> result`

Return revision, metric-engine/config versions, validity/coverage, time-series channels, global summaries and diagnostics. Preserve the operation-frequency and displacement-intensity time series, including their paired 2D trajectory. Reserve outputs for distance, movement, note, Peak, Arc and later block. No final difficulty values are available until these modules are implemented.

Run evaluation in a background worker, briefly debounce rapid edits, cancel obsolete jobs and show results only when their input revision matches the current editor revision. Display pending/stale/unavailable explicitly. Aim for near-real-time local updates; benchmark before promising a latency target.

A changed hand alters neighboring transfers on both hands, potentially across a long hold/arc. Expand invalidation to dependency boundaries and to the metric's sliding-window support. Global maxima and normalizations may require whole-chart updates. A metric plugin must declare whether it supports local updates; otherwise recompute it asynchronously in full. The initial implementation can use whole-chart evaluation, then optimize from measured timings.

Choose exclusion and denominator policy explicitly: full song time versus included active time, and treatment of rests/resets. Do not bridge movement paths across exclusions. A solver preference cost is not itself the difficulty score; corrected assignments must be evaluated independently of the penalties that generated them.

## Decisions before implementation

1. Initial edit scope: hand/range swaps and multi-touch masks only (recommended), or also splitting/merging operational units?
2. Does “hot” mean immediate internal preview and metric updates, or must an external ArcCreate view refresh automatically?
3. Is a simple 2D movement preview beside the list sufficient initially, with ArcCreate retained for final chart presentation?

Default proposal: a local application using the sketch's list/inspector, a separate Difficulty tab, offline project files, assignment/mask edits with undo, and explicit AFF export. No new implementation or workbench migration is part of this freeze.
