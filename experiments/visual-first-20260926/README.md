# Visual-First experiment (2026-09-25/26) — archived source

Origin: local folder `Desktop\Medflux-VisualFirst-Experiment` (offline copy of the
JAMAL branch, never committed, no Git remote). Archived here during the branch
unification on 2026-10-04 so the work is versioned before that folder is retired.

What already reached the product code (main line):
- streaming Ollama provider, keep_alive, structured timeouts (`app/ai/providers/ollama.py`)
- Visual-First bridge with page re-anchoring and region degradation
  (`app/ai/harness/visual_first_bridge.py`, `visual_first.py`)
- the EUR 12.000 financial classification gate (Harness V3)

What exists ONLY here (Stage 2, not integrated, not wired into the app):
- `backend/app/ai/harness/{archive_records,lexical_archive,llama_archive}.py` and
  `backend/app/contracts/search/llama_adapter.py` — separate LlamaIndex
  lexical/metadata archive with original-source citations (requires the
  `llama-index` dependency, which is not in `backend/requirements.txt`)
- matching tests under `backend/tests/` and the evidence archive page under `frontend/`
- benchmark / probe scripts (`real_frankfurt_*.py`, `vision_probe.py`, ...) — they
  read a local contract PDF at runtime; no contract content is stored in them
- `ENGINEERING_REPORT.md`, `VISUAL_FIRST_STAGE1_INSTRUCTIONS.md`,
  `docs/VISUAL_FIRST_STAGE1_RESULT.md`

These files are excluded from the backend test run (`backend/pytest.ini`
`testpaths = tests`). Integrating the archive is an open plan item, see
`docs/BRANCH_UNIFICATION_20261004.md`.
