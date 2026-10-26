# Arcaea Workbench

A note from the creator:

This is my first "vibe coding" project, aimed at the quantitative analysis of Arcaea chart difficulty. The project is still in its early stages; much work remains to be done regarding its utility and extensibility. For instance, the current pattern-recognition algorithm fails to identify certain techniques—such as the "arc tech" found at the beginning of Abstruse Dilemma—and the difficulty-calculation model lacks sufficient granularity, as a truly effective set of quantitative metrics has yet to be implemented.
As I am currently unable to make the necessary refinements myself, I have decided to public project code. I hope this serves those who are curious about this type of analysis, as well as players who are interested in pursuing similar work but aren't sure where to begin. It would be my honor if this project—or any work inspired by it—proves to be of significant value to the Arcaea community. To be honest, I’m not really familiar with things like licenses or how collaboration works in open-source communities; I still have a lot to learn—my apologies.

The above is the only passage I left behind in this project. What follows are Astra's annotations:

An experimental desktop workbench for exploring chart execution and difficulty attributes. It parses AFF charts, assigns contacts to hands, proposes arc paths, visualizes movement, and evaluates editable frequency/movement functions.

**2.4.0-rc3 · public proof-of-concept · Python source distribution**

This is an independent, AI-assisted project. It is not affiliated with Arcaea or ArcCreate. Outputs are hypotheses for inspection, not certified gameplay solutions or calibrated official ratings. There is no trained machine-learning model.

## Try it

Install Python 3.10+ with Tk. Extract the whole archive. On Windows run `INSTALL_DEPENDENCIES.cmd`, then `START_WINDOWS.cmd`. On macOS/Linux run `python3 -m pip install -r requirements.txt`, then `sh start_unix.sh`. Tk may require a separate OS package.

Choose **Assets & Batch → Load bundled example**. The synthetic demonstration needs no game assets. Open its row, inspect Results & Export and Trajectory, and read the [user guide](docs/USER_MANUAL.md) (also available offline as HTML).

For a separate workspace: `python workbench.py --workspace PATH`. Preserve an existing workspace and its external sequence folders when upgrading; do not copy personal workspaces into this repository.

## Choose your path

- [User guide](docs/USER_MANUAL.md): first run, batch processing, corrections, files and troubleshooting.
- [Function tutorial](docs/FUNCTIONS_TUTORIAL.md): change the model without editing Python.
- [Maintainer guide](docs/MAINTAINER_GUIDE.md): architecture, tests, extension points and packaging.
- [Known limits](docs/KNOWN_LIMITS.md) and [roadmap](ROADMAP.md).

## What is included

Runtime Python source, configurable definitions, synthetic chart/metadata, tests and documentation. The source archive also includes documentation-rendering tools and repository ignore settings. No game audio, artwork, commercial chart collection, copied wiki difficulty table, private workspace or personal annotation database is included. Both archives use the same runtime code.

The synthetic constant 1.0 is a schema example, not a measured difficulty. Import your own songlist and reference table for real charts. Tests use artificial inputs; numerical convergence is not proof of playability. See VALIDATION.json for the locally executed checks and unverified platforms.

Project code, documentation and synthetic fixtures are offered under Creative Commons Attribution-NonCommercial 4.0 International (CC BY-NC 4.0). Noncommercial sharing and adaptation are permitted with attribution and the other license conditions; commercial use is not granted by this license. This is source-available software, not an OSI open-source release. Dependencies retain their own licenses; see THIRD_PARTY_NOTICES.md.

See [LICENSE](LICENSE) for the full legal text and [NOTICE.md](NOTICE.md) for attribution and scope.
