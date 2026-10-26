# User guide — Arcaea Workbench 2.4 RC3

## 1. What this project does

The Workbench explores a possible way of playing a chart and measures that proposed execution. You can correct the proposal and observe how the measurements change. It has no universal difficulty rating and does not learn automatically from importing more charts.

The workflow is: original AFF → hand assignment → proposed arc path → editable execution sequence → metrics and visualizations. The chart's drawn arc and the proposed finger path are different objects. Difficulty uses the saved execution sequence. Original AFF files are not rewritten by these operations.

## 2. Install and start

Extract the complete user ZIP into a writable folder. Do not launch from inside the ZIP. This is Python source, not an executable installer.

Windows: install Python 3.10+ including Tk, then run INSTALL_DEPENDENCIES.cmd and START_WINDOWS.cmd. Both scripts select the Python launcher when available. The dependencies are NumPy and SciPy. CHECK_INSTALLATION.cmd runs diagnostics and tests; it is not required at every launch.

macOS/Linux: use `python3 -m pip install -r requirements.txt`, then `sh start_unix.sh`. If Tk is absent, install it for that interpreter using your OS/Python distribution. If your Python prohibits global pip installation, create a virtual environment and run its Python directly.

A default workspace is created in the application folder. To keep data outside the program, run `python workbench.py --workspace "PATH_TO_WORKSPACE"`. When using a virtual environment, launch with its interpreter so installed dependencies and runtime match.

## 3. First successful run

1. In Assets & Batch, click **Load bundled example** and wait for the job to finish.
2. Double-click the synthetic demonstration row. Sequence Editor displays the assigned operations.
3. Open Results & Export and inspect the metrics. The imported constant 1.0 is deliberately fictional; it is not a calibration target.
4. Open Trajectory, choose **Load current result**, then **Play / Pause**. The horizontal axis is input frequency; the vertical axis is movement response. This is not a physical picture of the player's hands.
5. In Arc Paths, click **Load file** to inspect source and proposed arc geometry. Gray shows the source; blue shows the candidate.
6. Return to Assets & Batch, select the demo, then Results & Export → **Batch export selected assets**. Choose a destination parent folder and open summary.csv in the new export folder.

The demo contains alternating taps, a hold, moving and stationary arcs, an attached sky tap, and a short burst. It has no audio. ArcCreate preview playback needs an independently configured ArcCreate project and audio resource; it is not part of this first-run test.

## 4. Import real charts and reference constants

Choose a Song folder and click **Scan folder**. Scanning imports chart identities; it does not calculate them. Filenames such as song_id_2.aff or song_id/2.aff support metadata matching. Use **Load songlist** to import your metadata JSON. The public package includes only synthetic metadata.

Set the Difficulty .csv path and click **Load table**. Required columns are PST, PRS, FTR, BYD/INS and ETR, with a title column or song_id. The supplied synthetic CSV demonstrates the layout. BYD/INS and ETR both map to the _3 convention, so do not fill both in the same row. Missing constants remain unknown. Use **CSV match report** for ambiguous titles; adding song_id resolves many ambiguities. The displayed integer rating and decimal reference constant are separate fields.

## 5. Batch generation and one CSV

Set class/text filters and optional inclusive constant bounds. Highest constant per title is chosen within the text/class selection before the range filter. Unknown candidate constants can exclude a title in highest-only mode.

Click **Select all shown**, or use Ctrl-click and Shift-click. Then choose **Generate allocation + preview**. New charts get allocation, arc recognition, preview and difficulty calculation. Existing working sequences are preserved; this button is not a request to replace their allocation. Review log messages and status columns, including failures within otherwise completed batches.

To recalculate saved sequences after a formula change, select them and choose **Update difficulty**. To intentionally replace assignments, use **New allocation baseline**; old revisions remain archived, but the active sequence changes. For arc recognition on an existing sequence use Arc Paths → Recognize arc paths per chart; the CLI also supports multiple chart IDs.

Keep the charts selected, switch to Results & Export, and choose **Batch export selected assets**. Open summary.csv in arcaea-export-… under your chosen destination. One row per selected chart includes reference chart_constant, computed metrics, provenance/status and errors. Blank values are not zero. Leave Include stale metric values off for current outputs. Additional detail files are exported alongside the consolidated CSV.

## 6. Read results correctly

| Term | Meaning |
|---|---|
| Reference constant | Number imported from your table; not predicted by this program |
| note | Default maximum of active-period frequency mean and mode |
| Peak | Duration-qualified frequency peak under the current window estimator |
| distance | Integrated movement response; not literal finger travel distance |
| movement | Peak of the movement signal |
| Arc | Integrated contribution from arc movement |
| Invalid volume | Estimated judgment inflation relative to operational input; based on reference judgment hypotheses |
| Current / stale | Whether outputs match the saved inputs/definition; not a confidence score |
| Reviewed | A human review label; not proof of mechanical feasibility |

Default functions are examples. Compare charts only under the same model and interpretation settings. Display smoothing changes the trajectory picture, not scores. Calculation caps can suppress differences between intense passages; inspect Movement warnings.

## 7. Correct assignments and paths

In Sequence Editor select an operation and change its hand/property. Autosave edits is initially enabled; otherwise use Save revision. Undo/Redo and History support review. Recalculate difficulty and regenerate previews after corrections. Structural edits may require Execution overlay instead of the coloring adapter.

In Arc Paths, Recognize arc paths saves a new sequence revision and a generated asset. Load the displayed file to inspect it. The solver uses configurable ±0.1 x/±0.25 y reference regions by default. The endpoint pass can remove movement to exact starts/ends while retaining times, attached inputs and shared seams.

Candidate points are editable as [time_ms, x, y] arrays in original AFF coordinates. Saving an asset alone does not apply it to execution. Edit → Save edited asset → review the changed path → mark it reviewed → Apply reviewed selected path. Point edits clear review. Stale sequence hashes or execution conflicts block application; reload/review against the current sequence. Automatically generated geometry can be recomputed; manually changed geometry is retained on reruns.

For arc paths in AFF previews, blue means allocated left hand, red right hand, green unresolved ownership. Other green review markers can flag multitouch candidates or unresolved situations. Green alone does not establish a confirmed extra-finger requirement. In the Arc Paths comparison canvas blue simply means candidate geometry.

## 8. Files and backup

| File/location | Purpose |
|---|---|
| Original .aff | Source chart; kept unchanged |
| Working .sequence.json | Active execution used for metrics and playback |
| .arc-paths.json | Source/candidate paths, recognition profile and decisions |
| .preview.aff / .overlay.aff | Generated ArcCreate views, normally beside the chart |
| Workspace runs/revisions | Generation records and sequence history |
| Workspace definitions | Draft and versioned active difficulty models |
| summary.csv | Consolidated batch export |

The workspace index and external sequence/output folders belong together. Close the app before copying both for backup. Paths are currently absolute: moving a project may need manual path repair. Export is useful for sharing results but is not a full restorable workspace backup. A failed export must not be treated as a completed backup.

## 9. Troubleshooting

- Missing NumPy/SciPy: install requirements with the same interpreter used to start the app.
- Missing Tk: install Tk for that Python; pip alone usually is not the solution.
- Unknown metadata: verify song IDs, filenames and the loaded songlist; the demo metadata contains no real songs.
- Saved settings seem ineffective: a draft is not the active model. Activate, then recalculate. Recognition profiles require a recognition rerun, not just a new preview.
- Preview destination conflict: an ownership/hash receipt protects externally edited files. Move your manual copy aside, then generate; do not overwrite it blindly.
- ArcCreate rejects group attributes: the compatibility exporter removes the known unsupported tracecol/bare angle syntax only in previews, logging changes. Decorative effects may differ. Other new mechanics may still need adapter work.
- Windows UI or playback problem: report version, steps, traceback and a minimal synthetic reproduction. Native Windows/Tk and ArcCreate testing is still limited.

See the maintainer guide if you want to change behavior beyond the exposed parameters.
