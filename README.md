# MTI Medical Knowledge Chatbot

> **Current state:** Phases 3–6 implementation is in place; live model acceptance on the RTX 3090 PC remains outstanding. Containerization is intentionally not started until that review is complete.

## Purpose and boundaries

A local multilingual retrieval-augmented chatbot for pharmacy staff, grounded only in the nine supplied documents (`KB-01` through `KB-09`). It returns verified source excerpts, abstains when it cannot verify a supporting quote, and short-circuits emergency or patient-specific dose patterns to an escalation response. This is an assessment prototype, not a clinically validated product. Use only public assessment questions or synthetic data; never enter real patient information.

See [the project brief](project-continuity-skill/BRIEF.md) for architecture, decisions, metrics and boundaries, and [the task board](project-continuity-skill/TASKS.md) for current phase/gate status.

## Local PC run (pre-containerization)

Prerequisites: Windows 11, Python 3.11+, shared HDD mounted, the Qwen3-8B Q4 GGUF and BGE-M3 cache present, and the bundled llama.cpp Vulkan server executable.

1. Create a machine-local virtual environment so the shared HDD does not reuse the laptop's Windows/Python environment on the PC, then install dependencies:

   ```powershell
   py -3 -m venv .venv-pc
   .\.venv-pc\Scripts\python.exe --version
   .\.venv-pc\Scripts\python.exe -m pip install -e ".[dev]"
   ```

   The displayed version must be at least 3.11.

2. Copy `.env.example` to `.env`. Leave `PROJECT_ROOT` unset to use the checkout path automatically (E: on the laptop or F: on the PC). If a prior `.env` pins the other machine's drive letter, remove or update that line. Shell environment variables override `.env` values. Keep `APP_HOST=127.0.0.1`; the assessment admin routes have no authentication.
3. In PowerShell from the project root, start the local Qwen server in its own terminal:

   ```powershell
   .\.cache\tools\llama-b12110-vulkan\llama-server.exe `
     -m .\.cache\models\Qwen3-8B-Q4_K_M.gguf `
     --host 127.0.0.1 --port 8080 -c 4096 -t 16 -tb 24 -ngl 99 `
     --temp 0.0 --reasoning-budget 0
   ```

4. Start the API in another terminal:

   ```powershell
   .\.venv-pc\Scripts\python.exe -m uvicorn app.main:app --host 127.0.0.1 --port 8000
   ```

5. Open `http://127.0.0.1:8000/`. Check `http://127.0.0.1:8000/health`; it should report ready only when the configured local LLM server responds.
6. After the app is responding, run the public/synthetic end-to-end set:

   ```powershell
   .\.venv-pc\Scripts\python.exe -m evaluation.run_eval
   ```

   The runner writes `evaluation/results/end_to_end_eval.json` with case outcomes, status confusion, citation checks, required-fact substring proxy, forbidden-claim hits, latency and available per-session token counters. Review every answer and citation manually before drawing factual-accuracy conclusions. The automated fact matcher is not a human gold-label evaluation.

The existing shared Chroma index and model caches are expected to be reused. Do not run a full ingestion rebuild unless intentionally rebuilding; it can take time and replaces the active index. If the index is absent, run `.venv-pc\Scripts\python.exe -m app.ingestion.run_ingestion --rebuild` after confirming the configured BGE-M3 model cache and manifest paths.

## API routes

- `POST /chat` — question, optional session ID; returns answer, citations, status and language.
- `GET /health` — configured model labels and local LLM readiness.
- `POST /admin/documents` — multipart `doc_id` plus `.docx`, only for existing manifest IDs, max 15 MiB.
- `DELETE /admin/documents/{doc_id}` — removes the document from the active index and records a deletion tombstone.
- `GET /admin/analytics` — aggregate local operational counts.
- `GET /admin/analytics/sessions/{session_id}` — token and latency counters for a single session.
- `POST /handoff` — stores synthetic demo contact details; it does not contact a clinician.

The admin routes are unauthenticated. Bind the service to loopback and do not expose it to a network. Admin source files and Chroma are separate persistence systems; a crash between commits may require an operator retry/rebuild. See [API and recovery notes](Docs/API_CONTRACT.md).

## Dependencies and project layout

Install the pinned project dependencies into a machine-local venv with `python -m pip install -e ".[dev]"`. The `app/` package contains API, safety, retrieval, ingestion, generation, storage and static UI modules. `evaluation/` contains model/retrieval benchmarks, labeled cases, and the live evaluation runner. `tests/` contains API, safety, analytics and Chroma recovery tests. Model/cache/index/SQLite/output locations are configurable in `.env` and remain under the shared project root by default.

Docker files are still scaffolding; no clean-container run is claimed. The report and file-by-file teaching walkthrough are intentionally deferred until the PC accuracy review and containerization phase.
