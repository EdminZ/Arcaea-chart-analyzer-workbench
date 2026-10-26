# Core allocator

This directory contains the original parser/reconstruction/heuristic beam allocator and coloring CLI. Workbench adds the arc path stage through app/adapters.py after allocation. Directly running core/analyze_aff.py does not run that additional stage.

Read ../docs/MAINTAINER_GUIDE.md for the current architecture and limits. ALGORITHM.md, BASELINE_ALGORITHM.md, OUTPUT_AND_EDITOR_DESIGN.md and SEQUENCE_FORMAT.md are historical design references for the core; they do not supersede current Workbench documentation.
