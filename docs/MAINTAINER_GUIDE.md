# Taking over development

## Scope and starting point

This is a local Python/Tk proof-of-concept, built iteratively with AI assistance and player review. It is suitable for experiments and forks. There is no hosted service, trained weight checkpoint, telemetry backend, or automatic learning system.

Start by running the synthetic workflow and tests. Keep your workspace outside the repository. Change one layer at a time and preserve source identities and manual corrections. Reproduce a reported failure before tuning a heuristic.

## Repository map

| Path | Responsibility |
|---|---|
| workbench.py | CLI arguments, workspace lock, GUI startup |
| manage.py | Headless import/generate/recognize-arcs/calculate/preview/export |
| app/gui.py, asset_ui.py, lab_ui.py | UI and background-task coordination |
| app/store.py | Index, revisions, stage state, file routing and export |
| app/adapters.py | Allocator/preview CLI boundary and integrated arc stage |
| core/engine/audit.py, reconstruct.py | AFF syntax and reference input/judgment reconstruction |
| core/engine/assign.py, preferences.py | Heuristic/beam hand allocation |
| app/arc_solver.py | Fixed-assignment path optimization and endpoint pass |
| app/sequence.py, arc_paths.py | Editable sequence and portable path validation |
| app/model2.py, signals.py, difficulty.py | Feature extraction, evaluation, restricted functions |
| app/metadata.py | Song/class identification and CSV constants |
| app/aff_compat.py | Preview-only compatibility normalization |
| defaults/ | Model/profile defaults and synthetic metadata |
| tests/, core/tests/ | Workbench and core regressions |

## Data contracts

Original AFF bytes determine chart SHA256. Source event IDs refer to that exact parse; never transfer corrections to a changed chart without remapping/review. arcaea-input-sequence/1 is the core allocator interchange; arcaea-editable-sequence/2 is the operational editable document. arcaea-arc-paths/1 stores AFF-coordinate source/candidate arrays with a source hash and sequence binding. arcaea-difficulty/2 is the active frequency/movement definition; /1 compatibility behavior is retained.

Do not confuse AFF y with sequence y. Time values use AFF milliseconds; AudioOffset is not applied to execution timestamps. Sequence reservations, input onsets and source arc geometry have different purposes. A geometry change must invalidate metrics/previews; changing review labels alone does not prove feasibility.

The Store preserves revisions and writes individual files atomically. There is no multi-file transactional commit across SQLite and the filesystem. Absolute pointers, cross-file recovery and large-batch resume are known limitations. Current preprocess caching reuses chart-facts.json: if reconstruction semantics change, plan an explicit facts/cache migration rather than silently reusing it.

## Extend a layer

Recognition: add a synthetic counterexample and a reviewed expected alternative, then modify the heuristic/preferences. The current arc stage runs after allocation; it cannot retroactively improve which hand was chosen. The path solver uses nominal tight timestamps with zero added timing slack. Non-null timing-tolerance/speed-limit settings are rejected, not silently used. Do not describe convergence as continuous-contact feasibility. Neutral/unknown/manual paths can be retained as fallbacks.

Labeling: separate solver outcome, ownership, human review, mechanical uncertainty and extra-contact hypotheses. Prefer explicit reason/provenance fields. Preserve user edits and permit multiple acceptable solutions.

Metrics: change JSON when the feature already exists; change the engine for new measurements. Bump feature/engine contracts and invalidate caches when semantics change. Recognition's fixed movement objective is separate from customizable scoring curves. Window-count Peak still has boundary effects; a timestamp-rate replacement needs chord/rest/burst tests before adoption.

Visualization: keep source drawings, execution paths and display smoothing distinct. Preserve original source files. Compatibility removals should be logged and limited to generated views. ArcCreate version-specific support needs actual playback validation.

## Validation commands

From the repository root:

```
python -m unittest discover -s tests -q
python -m unittest discover -s core/tests -q
python tests/integration_release.py
```

The integration check creates temporary workspaces, evaluates the demo and exports 100 synthetic charts. Tests provide regression evidence, not player-validity certification. Verify native UI scaling, file dialogs, Unicode paths, Ctrl/Shift selection and ArcCreate playback separately.
