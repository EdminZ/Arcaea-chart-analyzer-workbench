# Input sequence format: arcaea-input-sequence/1

Standard UTF-8 JSON, not JSONL. Each `units` entry occupies one line for scanning.
`format` identifies this contract; `algorithm_version` identifies the generator.
`sha256` binds the sequence to the exact original file bytes. Renaming the original
is allowed; changing its bytes requires re-analysis. `structure_sha256` detects
accidental changes to operation definitions. It is not a digital signature.

Each operation contains:

| Field | Meaning |
| --- | --- |
| unit_id | Deterministic operation ID within this parser/algorithm version |
| kind | floor_tap, sky_tap, wide_sky_tap, hold or arc |
| start_ms, end_ms | Operational interval; holds retain full source duration |
| hand | L, R or null (unresolved) |
| start_position, end_position | [x,y] in the documented analysis plane |
| source_event_ids | Source AFF records represented by the operation |
| action_ids | Fresh input actions grouped into the operation |
| arc_color | Original color, neutral for a provisional shared pair, or null |
| fresh_press | Whether the operation has a fresh discrete press requirement |

`arc_geometry` stores source curve/time/color definitions for arc operations;
`extraction` records joining, aliases, excluded hidden sources, legacy hold-release metadata (empty under this snapshot)
and provisional adjacent-color groups. The original AFF remains authoritative.
`multitouch` separates conservative demand candidates and confirmed exclusions.
`review_windows` records solver omissions. `visual_review_markers` preserves
explicit review markings. `summary` and review diagnoses describe the original
analysis run; manually changing a hand does not recompute them. Manual-edit workflow
is deferred; re-analysis is the supported way to regenerate consistent metadata.

The coloring command needs only this sequence plus its original AFF. It does not
need the analyzer's intermediate parsed data, reconstructions or full search trace.
It validates enum values and conflicting reservations as well as the structural
hash. This catches common mistakes; it is not a proof of physical playability.
