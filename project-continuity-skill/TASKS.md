---
project: MTI Medical Knowledge Chatbot
sprint: Seven-day assessment build — Nov 3–9, submission Nov 10, 2026
last_updated: 2026-11-09
---

# Tasks and Antigravity Phase Prompts

Read `BRIEF.md`, the newest `PROGRESS_LOG.md` entry, and `REQUESTS.md` before each session. Statuses: `[ ]` not started, `[~]` in progress, `[x]` done, `[!]` blocked (explain why inline and log it). The phase prompts below are to be sent one at a time. After each phase Antigravity stops for Codex critique; it may continue only after Codex explicitly releases the next phase. No phase is authorized to exceed the Nov 10 submission deadline.

## Schedule note

The authorized work window is Nov 3–9 and submission is due Nov 10; do not extend it. As of Nov 9, Phases 3–6 code is implemented, but live model results and some acceptance evidence remain pending. Adham directed Codex to stop before Phase 7/containerization so he can review factual accuracy on the RTX 3090 PC. Hardware now known: Dell Latitude 3410 (i5-10210U, integrated graphics, 16 GB RAM) is the development machine; the benchmark PC has an RTX 3090, 32 GB RAM, and 12th-gen-or-newer i9. Both are Windows 11; PC is 26H2 and the laptop is 25H2. The external E: HDD is shared as F: on PC for project data. Keep repository, model cache, source copies, index, SQLite, and eval outputs under the configurable project root. Evaluator hardware remains unknown. MedGemma was evaluated only after Adham accepted its terms.

## Phase 1 — Tue Nov 3 — Scope, corpus, runtime and model gate

- [x] Record known hardware: Dell i5-10210U/integrated graphics/16 GB (Laptop `Alfy`, Windows 11 25H2, C: 10.2 GB free / E: 792 GB free, Docker CLI 28.4.0, engine stopped, `docker_data.vhdx` 8.5 GB); RTX 3090 PC verified (`DESKTOP-TD0BULG`, Alienware Aurora R13, 12th Gen Intel Core i9-12900KF [16C/24T], NVIDIA GeForce RTX 3090 24GB [Driver 617.42], 31.8 GB RAM, Windows 11 build 26300.9818 [26H2], shared external drive mounted as `F:\` with 787.66 GB free, internal C: with 163.34 GB free, Docker CLI 29.7.2 installed with Linux engine stopped, `docker_data.vhdx` 1.68 GB on C:, `docker-desktop` WSL2 distro Stopped); evaluator GPU + internet remain unknown. Model cache strictly configured on `<PROJECT_ROOT>\.cache\`.
- [x] Initialize the Git repository at the project root on the external HDD and create the planned folder scaffold from `BRIEF.md`, a README placeholder, `.gitignore`, and non-secret configuration example; this is setup only, with no application behavior yet.
- [x] Confirm the external drive is present and writable on both laptop (`E:`) and PC (`F:`) (`app/core/config.py:validate_storage_paths()`). Keep repository, model cache, source-data copies, vector index, SQLite data, and evaluation output under its configurable project root. Verified Docker Desktop's internal VM disk storage on both machines (`C:\Users\User\AppData\Local\Docker\wsl\disk\docker_data.vhdx` 8.5 GB on laptop; `C:\Users\Dell\AppData\Local\Docker\wsl\disk\docker_data.vhdx` 1.68 GB on PC).
- [x] Inspect all nine DOCX documents and map to KB-01…KB-09 in a manifest (`data/kb_manifest.yaml`); inspect overlap between combined pain/headache/IBS/arthritis file (`KB-03`, which contains only Pain & Fever and Headache & Migraine) and separate IBS/arthritis file (`KB-09`, which contains only IBS and Arthritis), plus shared NSAID/Paracetamol drug tables across `KB-03`, `KB-09`, `KB-04`, and `KB-06`.
- [x] Benchmark open-weights LLM candidates (`Qwen3-4B-Instruct-2507-Q4_K_M`, `gemma-4-E4B-it-Q4_0`, `Qwen3-8B-Q4_K_M`) and embedding candidates (`MiniLM` vs `BGE-M3`) on both laptop (CPU fallback) and PC (RTX 3090 Vulkan GPU offload `-ngl 99`). Side-by-side results recorded in `Docs/MODEL_DECISION.md`, `Docs/TOKEN_USAGE.md`, `evaluation/results/phase1_benchmark_laptop.json`, and `evaluation/results/phase1_benchmark_rtx3090_pc.json`.
- [x] Benchmark `google/medgemma-4b-it`: Adham explicitly reviewed and accepted Google Health AI Developer Foundations terms on 2026-11-07 and authorized evaluation. Download of `medgemma-4b-it-Q4_K_M.gguf` (2.49 GB, SHA256 verified) complete; benchmark executed across all 16 cases on both Dell Latitude 3410 CPU (load 6.82s, peak RSS 7319.6 MB, prefill 25.58 t/s, gen 4.03 t/s, p50 88.83s, max 129.79s, accuracy 9/16 [56.2%], citation validity 16/16, safety violations 1) and Alienware Aurora R13 RTX 3090 PC (load 47.56s, peak RSS 6081.2 MB, prefill 4,505.54 t/s, gen 143.00 t/s, p50 1.62s, max 2.34s, 0/16 calls >30s, accuracy 10/16 [62.5%], citation validity 16/16, safety violations 1). Results recorded in `Docs/MODEL_DECISION.md`, `Docs/TOKEN_USAGE.md`, `evaluation/results/phase1_benchmark_laptop.json`, and `evaluation/results/phase1_benchmark_rtx3090_pc.json`.
- [x] Run candidate benchmark on both laptop and PC where feasible; record OOM, model-load failure, and >30s latency as results, not as omitted rows. (Both laptop CPU and RTX 3090 PC benchmarks are 100% complete across all 4 LLMs + 2 embedding models).
- [x] Record Python/runtime/tool versions, folder ownership, config, environment variables and model download approach (`Docs/MODEL_DECISION.md`, `Docs/TOKEN_USAGE.md`, `.env.example`, `evaluation/phase1_benchmark.py`).
- [x] **Gate evidence:** Dual-device corpus mapping, model/license matrix, side-by-side benchmark results (`evaluation/results/phase1_benchmark_laptop.json` and `evaluation/results/phase1_benchmark_rtx3090_pc.json`), and updated reports (`Docs/MODEL_DECISION.md`, `Docs/TOKEN_USAGE.md`) are complete across all 4 LLMs (`Qwen3-4B-Instruct-2507-Q4_K_M`, `gemma-4-E4B-it-Q4_0`, `Qwen3-8B-Q4_K_M`, `medgemma-4b-it-Q4_K_M`) and both embeddings (`MiniLM`, `BGE-M3`). Top 3 models selected per Adham's direction: 1. `Qwen3-8B-Q4_K_M` (Primary Quality), 2. `medgemma-4b-it-Q4_K_M` (High Throughput Clinical), 3. `Qwen3-4B-Instruct-2507-Q4_K_M` (Compact Baseline). Phase 1 gate complete and ready for Codex review release to Phase 2.

**Antigravity prompt — Phase 1**

> Read the assessment PDF, all nine files in `Docs/Data/`, and all four continuity files before editing. Perform Phase 1 only. Do not implement chatbot behavior yet. Initialize the Git repository at the project root on the external E: HDD and create the planned folder scaffold from `BRIEF.md`, plus a README placeholder, safe `.gitignore`, and non-secret configuration example. Confirm the HDD is present/writable on both machines; make paths configurable and keep repo, model cache, source-data copies, vector index, SQLite data, and evaluation outputs under that drive. Check Docker Desktop's internal image/VM storage separately; bind mounts do not automatically relocate it from C:. Do not download the full model set until storage requirements are checked. Build an evidence-backed corpus-to-KB-ID manifest and explicitly analyze the apparent KB-03/KB-09 overlap. Known machines: Dell Latitude 3410, i5-10210U, integrated graphics, 16 GB RAM (development machine); second PC, RTX 3090, 32 GB RAM, 12th-gen-or-newer Core i9 (benchmark machine); both Windows 11 25H2 with Docker installed; evaluator has internet and a GPU but exact specs are unknown. Confirm Docker Desktop/WSL2/GPU passthrough, free disk, PC exact CPU SKU and evaluator hardware. Benchmark on both the laptop and PC where each candidate can be run. Compare all four LLMs: Qwen3-4B-Instruct-2507 Q4, Gemma 4 E4B-it Q4_0, Qwen3-8B Q4, and MedGemma 4B-it. Before MedGemma download, stop until Adham has reviewed/accepted the separate Health AI Developer Foundations terms; do not accept terms on his behalf. Compare MiniLM multilingual with BGE-M3 embeddings on both machines if feasible. Verify exact artifact, license, revision, quantization provenance, and chosen `llama.cpp` compatibility. Report memory, load time, token generation and end-to-end latency, groundedness/citation and safety results; record failed loads, OOM, and >30s latency rather than omitting them. Do not call a model the winner without this evidence. Do not use external medical sources. Update this phase's tasks and append a progress entry with inspected files, facts, uncertainties, commands/results, and next gate. Stop and submit the manifest, repository/scaffold inventory, candidate table, evidence, and any open blocker for Codex review.

## Phase 2 — Wed Nov 4 — Ingestion and multilingual retrieval

- [x] Parse DOCX headings, paragraphs, and 153 embedded tables via `iter_block_items()` while preserving Arabic Unicode (NFC), document hierarchy, and source metadata (`app/ingestion/docx_parser.py`).
- [x] Implement deterministic section-aware chunking (eliminating 85 stub headings; 414 rich chunks), local embedding (`BAAI/bge-m3`), and persistent index (`data/chroma`). WAL recovery uses actual live/staging/backup state and is tested at pre/post rename process-restart states; 10 targeted pytest tests pass. Physical power-loss durability is not claimed. Targeted replace verifies new IDs before pruning; an interruption can leave both generations until retried, while preserving prior data.
- [x] Create multilingual retrieval evaluation across English, Modern Standard Arabic, Egyptian Arabic dialect, Franco-Arabic, and mixed language. Results: document R@1=100%, fact-proxy R@1=72.2%, R@3=83.3%, MRR=0.778; proxy is disclosed, not gold relevance. Applying `min_score=0.50` to all 18 in-scope and five OOS cases yielded 100% in-scope retention (18/18) and 80% OOS rejection (4/5). Franco normalizer rules remain Adham-owned; rerun after his edits.
- [x] Verify retrieved IDs, titles, sections, snippets and source metadata are carried through `RetrievedChunk.to_citation_dict()`; note this does not itself validate passage relevance.
- [x] **Gate evidence:** Full-corpus report has 414 chunks across nine documents. Ten local tests pass, including recovery states before/after both renames. The same threshold was measured on in-scope and OOS cases (18/18 retained; 4/5 rejected). Phase 2 review is complete; Phase 3 is released. See Session 21. Re-run Franco cases after Adham's normalizer edits.

**Antigravity prompt — Phase 2**

> Proceed with Phase 2 only, after the Phase 1 review release. Implement the agreed DOCX ingestion and multilingual retrieval design from the approved manifest. Preserve exact KB IDs, titles, headings/sections, and source text; make chunking and embedding configuration explicit and reproducible. Add persistent indexing and safe re-index/delete primitives needed by the later admin work. Build a labeled retrieval evaluation set from the public questions and varied paraphrases, including Arabic dialect, Franco-Arabic, English, and mixed input; never hard-code answers or branch on literal prompts. Report Recall@1, Recall@3, MRR, corpus coverage, and failure examples. Update continuity files, run the phase checks, then stop for Codex critique.

## Phase 3 — Thu Nov 5 — Exact API contract, RAG answer and safety

- [x] Implement `POST /chat` and `GET /health` with exact response fields, enum values, citation constraints, and configured model names (`app/api/`, `app/schemas/api.py`). Health returns 503 while the local LLM server is unavailable; live readiness remains unverified here.
- [x] Implement retrieval-grounded extractive quote selection with local quote verification, language label, status classification, citation provenance, abstention, and pre-generation escalation (`app/services/chat_service.py`, `app/generation/llm_client.py`, `app/safety/guards.py`).
- [x] Add input validation, request timeout/error response, session creation, and prompt-safe server logging.
- [~] Contract and safety checks pass, but live model answers over the ten public questions and paraphrases have not been evaluated; await full PC run. Franco normalizer remains unchanged.
- [~] **Gate evidence:** 27 local tests pass, including API contract, safety, admin input validation, and analytics paths. End-to-end status confusion, citation/fact review, per-language quality, and latency require a live local model run on the PC.

**Antigravity prompt — Phase 3**

> Phase 2 is released. Perform Phase 3 only. First read `BRIEF.md` §5 and the latest continuity entries. Implement `/chat` and `/health` with typed schemas that match the brief exactly, including status enums, language values, citation rules, and exact 500 response. Run retrieval with the reviewed `min_score=0.50`; an empty result means no supporting evidence. A non-empty result is not sufficient by itself: ground each answer claim in returned chunk text, cite only those chunks, and return `out_of_scope` when the asked drug/fact is unsupported (specifically test the Franco `makin` query, which retrieves asthma passages because it mentions `rebo`). Add a deterministic pre-LLM emergency/sensitive escalation guard that returns `escalated` without clinical instructions. Never generate diagnosis, dose, or treatment advice absent from the supplied corpus; use no external medical sources and do not hard-code public question strings. Keep the configured model swappable among the three retained Phase 1 candidates; use the currently selected default and defer the final cross-model selection benchmark to the agreed full-system PC test. Do not modify Adham's Franco normalizer. Add unit/API tests for contract, empty retrieval, irrelevant-but-nonempty retrieval, unsupported drug, citations, emergency/sensitive queries, malformed input, timeout/error, and all ten public questions plus paraphrases in English, Arabic, Egyptian dialect, Franco, and mixed language. Check per-request and end-to-end latency against 30 seconds. Record result counts, confusion matrix, citation audit, safety failures, per-language metrics, latency, and model/runtime settings. Update `TASKS.md` and append `PROGRESS_LOG.md`; stop for Codex review and do not begin Phase 4 until explicitly released.

## Phase 4 — Fri Nov 6 — Chat UI and escalation handoff

- [x] Build web chat interface that calls the API, keeps session ID, and renders citations and API states (`app/static/`).
- [x] Add Arabic direction handling, mixed-script text, English, responsive styling, loading/error states.
- [x] Add demo handoff capture for summary/contact details and explicitly disclose that no clinician has been contacted.
- [~] API/static asset and synthetic handoff tests pass; full browser walkthrough across statuses and real model outputs remains for PC verification.
- [~] **Gate evidence:** automated UI route/static and handoff tests are included in the 25 passing tests; human visual walkthrough pending.

**Antigravity prompt — Phase 4**

> Proceed with Phase 4 only after review release. Build the simplest maintainable browser chat UI consistent with the architecture, calling the real API rather than mocking answers. Preserve session ID, render answer/status/citations, and distinguish out-of-scope and escalated responses. Handle Arabic RTL, mixed-script text, loading, timeout, and API errors. Add the assessment's escalation handoff flow to capture a short summary and contact details; use synthetic test details only and make no claim that anyone was contacted. Do not add unrelated product features. Run and report the required UI/API flow checks, update continuity files, and stop for Codex critique.

## Phase 5 — Sat Nov 7 — Document admin and operational analytics

- [~] Implement `.docx` upload/replacement limited to existing manifest IDs, 15 MiB cap, verify-before-prune Chroma updates, source overrides used by full rebuilds, and persistent deletion tombstones. Cross-store source/index updates are not a single transaction; see `Docs/API_CONTRACT.md` for crash/retry limits.
- [x] Add conversation volume, top questions, unanswered/escalated count, runtime input/output tokens, and per-stage/end-to-end latency metrics in SQLite.
- [x] Implement `/admin/documents`, `/admin/analytics`, and per-session evaluation metrics endpoints. No admin UI was built; routes are unauthenticated and must remain loopback-only.
- [x] Keep automated records synthetic; chat metrics store question strings as documented, so only public/synthetic prompts are permitted for this assessment build.
- [~] **Gate evidence:** analytics aggregation test passes. Upload/delete recovery and live model metrics still require PC/API acceptance; do not call the admin phase fully crash-safe.

**Antigravity prompt — Phase 5**

> Proceed with Phase 5 only after review release. Implement the assessment's document admin operations and conversation analytics. Upload/replace/delete must update the stored original and index consistently, validate type/size/ID, prevent traversal, and recover safely if indexing fails. Analytics must cover volume, top questions, unanswered questions, model token usage, and latency; make the source and granularity of each metric explicit. Use only supplied KB content plus synthetic/public test questions; do not ingest real patient information. Never expose secrets. Implement the optional assessment routes and admin view within the time box. Demonstrate index updates and analytics reconciliation, update continuity files, then stop for Codex critique.

## Phase 6 — Sun Nov 8 — Evaluation harness and technical reports

- [x] Use versioned `evaluation/cases.jsonl` with expected statuses, source IDs, language, required facts, and forbidden claims (16 end-to-end cases; Phase 2 retrieval set has 23 cases).
- [x] Implement live API runner recording model/config via session metrics, returned source IDs, status, language, citations, fact proxy, forbidden claims, latency, and token counters (`evaluation/run_eval.py`).
- [~] No live report was generated because this laptop has no running llama.cpp model server. Synthetic runner smoke passes 16/16 only as a mechanics check; this is not system performance or accuracy evidence.
- [ ] Write one-page `MODEL_DECISION.md` with observed comparison and licenses.
- [ ] Write `TOKEN_USAGE.md` with per-call/per-request input/output tokens, latency, hardware, method/precision limits, production-analytics suitability, largest call, and optimization.
- [~] **Gate evidence:** `python -m evaluation.run_eval` is implemented; saved live output, human factual review, and PC token/latency results are pending.

**Antigravity prompt — Phase 6**

> Proceed with Phase 6 only after review release. Build the assignment's own repeatable evaluation harness and recorded test results. Cover the 10 public cases plus paraphrases and safety, multilingual, no-hit, citation, and malformed-input cases without matching exact public strings in application behavior. Record expected and actual status, relevant/returned KB IDs, language, reviewer safety/citation labels, model/embedding versions, retrieval config, latency, and token counts per call. Write `MODEL_DECISION.md` as a concise measured comparison with license details, and `TOKEN_USAGE.md` explaining measurement method, hardware, warm/cold conditions, mean/p50/p95, production suitability, largest token call, and optimization. Clearly distinguish runtime counters from tokenizer estimates. Do not invent scores or claim clinical validation. Run the harness, save results, update continuity files, and stop for Codex critique.

## Phase 7 — Mon Nov 9 — Docker, clean run and submission package

- [!] Docker work is intentionally held at Adham's direction until the full system is reviewed on the RTX 3090 PC and factual accuracy is concrete.
- [ ] Dockerize full project with one documented command; persistent weight/data volumes; clean secret handling.
- [ ] Verify on a clean Docker volume/environment and document internet/preload model requirements.
- [ ] Complete README, repository organization and safe `.gitignore`; remove generated data/keys.
- [ ] Verify all artifacts: API, UI, admin, handoff, evaluation runner/results, `MODEL_DECISION.md`, `TOKEN_USAGE.md`, README, Docker files.
- [ ] Run full acceptance suite twice; freeze submission by Nov 10; record limitations.
- [ ] **Gate evidence:** exact commands and outputs, health model names, startup time, endpoint compatibility, final artifact checklist.

**Antigravity prompt — Phase 7**

> Proceed with final phase only after review release. Dockerize and document the complete project so a clean machine with Docker can start it with one command. Keep secrets outside images and Git; persist model weights/data via documented mounts or volumes. Verify the actual clean-start mode, health endpoint model names, API contract, chat UI, admin operations, handoff, and evaluation runner. Finish README with prerequisites, exact commands, model download/preload behavior, configuration, endpoints, data handling, model/license details, and troubleshooting. Run the full acceptance suite twice on the named hardware/runtime and save outputs. Do not add scope. List known limitations and any unmet criteria honestly. Update TASKS/PROGRESS_LOG and stop for final Codex review; do not claim submission until the repository package is ready.

## Pre-containerization checkpoint — Adham PC fact-accuracy review

- [~] Phase 3–6 code and evaluation runner are implemented; the live system evidence needed to close Phases 3, 4, 5 and 6 is still pending because the laptop has no local model server.
- [ ] Stop before Phase 7 / containerization. Adham runs the complete system on the RTX 3090 PC and reviews answer facts, citations, unsupported-question handling, and latency. Resolve observed fact errors before writing final result claims.
- [ ] After PC results are reviewed, jointly finalize `MODEL_DECISION.md`, `TOKEN_USAGE.md`, evaluation results, and known limitations. Only then resume Phase 7 containerization and clean-machine verification.

## Deferred learning deliverable — file-by-file code walkthrough

- [ ] After project implementation and review are complete, walk through every project source/config/test file with Adham: explain purpose, control/data flow, important design choices, failure modes, and how to defend the implementation. Include critique and learning notes; keep this educational walkthrough separate from assessment claims and the seven-day implementation schedule.

## Cross-phase acceptance checklist

- [ ] API contract exact and all contract cases pass.
- [ ] Only approved knowledge base used; source IDs and citations trace to actual evidence.
- [ ] Safety suite has no observed unsupported diagnosis/dose/treatment; status and language coverage reported.
- [ ] All required stretch elements are functional and documented.
- [ ] 30-second response limit met under reported test conditions.
- [ ] Docker one-command clean-machine run documented and verified; model weights behavior disclosed.
- [ ] README, `MODEL_DECISION.md`, `TOKEN_USAGE.md`, evaluation script, and recorded results are present.
- [ ] No secrets or real patient data are present in source, logs, images, or submitted test artifacts.

## Out of scope

Production clinical validation or deployment, real patient data, external medical sources/APIs, model fine-tuning, authentication beyond any minimal admin protection needed for the assessment, production-grade compliance/security certification, and features not required by the assessment. Do not pull these into the seven-day window.
