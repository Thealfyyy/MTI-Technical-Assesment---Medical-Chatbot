---
project: MTI Medical Knowledge Chatbot
owner: Adham
status: implementation in progress; awaiting pre-containerization PC accuracy gate
last_updated: 2026-11-09
---

# Project Brief: Medical Knowledge Chatbot

This brief translates the MTI AI Solutions technical assessment into a seven-day implementation plan for Antigravity. It is the current source of truth for scope, constraints, architecture direction, acceptance measures, and review gates. The assessment PDF and nine supplied Word documents in `Docs/Data/` remain the authoritative source for the required behavior and knowledge base. Read `PROGRESS_LOG.md`, `TASKS.md`, and `REQUESTS.md` at the start of each session.

## 1. What this product is

A web-based drug-information chatbot for pharmacy staff and doctors. It must answer only from the nine approved knowledge-base documents, show source citations for supported answers, and safely decline or escalate questions that are unrelated, unsupported, sensitive, or emergencies. It must accept English, Arabic (including Egyptian dialect and Franco-Arabic), and mixed-language questions.

This is an individual technical assessment, not a production medical device. No diagnosis, dosing, or treatment advice may be supplied unless that information is explicitly present in the approved documents. No real patient data may be used anywhere in the project or its evaluation.

## 2. Business context and deadline

- Assessment brief: `Docs/Agent Context/MTI_AI_SOLUTIONS_AI_ENGINEER_TECHNICAL_ASSESSMENT-Brief.pdf`.
- The assessment itself specifies seven calendar days (its original March 2026 dates are historical and expired).
- Adham reset the working window to seven days from November 3, 2026. Plan seven workdays, November 3–9, and target submission by November 10, 2026 (seven elapsed days after November 3). The plan is already underway as of November 4.
- Submission: a Git repository with Docker setup, README, `MODEL_DECISION.md`, `TOKEN_USAGE.md`, and reproducible test results.
- All core and all stretch items named in the assessment are included in this plan. There is no authorized extension beyond the seven-day window; time-box and prioritize in the order in §7.

## 3. Assessment requirements and locked constraints

| Requirement | Acceptance condition | Why it matters |
|---|---|---|
| Approved corpus only | Ingest the supplied nine KB documents; retrieval and answer generation use no other medical source | Enforces the assessment's evidence boundary |
| Open-weight models | Select and identify an open-weight LLM and embedding model; record license and measured choice in `MODEL_DECISION.md` | Explicit assessment rule and reproducibility |
| Exact API contract | `POST /chat`, `GET /health`, exact fields/status values/citation rules in §5 | Hidden evaluation calls the same contract |
| Multilingual UX | English, Arabic, Egyptian dialect, Franco-Arabic, and mixed-language inputs; answer language is `ar`, `en`, or `mixed` | Explicit user population and API field |
| Safety | Unsupported questions are `out_of_scope`; sensitive/emergency questions are `escalated`; no unsupported diagnosis, dose, or treatment direction | Medical risk boundary |
| Web chat | Simple browser chat calling the API | Mandatory core deliverable |
| Docker | Whole project runs from one documented command on a clean machine with Docker | Mandatory evaluator workflow |
| Documentation | README, one-page model decision record, token/performance report, own test script/set/results | Mandatory submitted artifacts |
| Stretch admin | Upload, replace, and delete documents without code changes | Optional in the assessment; included by Adham's direction |
| Stretch analytics | Conversation logging and basic volume, top-question, unanswered, token, and latency analytics | Optional in the assessment; included by Adham's direction |
| Stretch escalation handoff | Capture short summary and contact details | Optional in the assessment; included by Adham's direction |
| Stretch evaluation harness | Test set, executable script, and recorded results | Optional in the assessment; included by Adham's direction |

Never hard-code answers to the ten public dev questions. They may be used as test cases, but the system must answer by retrieval and generation. Keep credentials out of source control and images. No external medical APIs or non-starter medical corpus.

## 4. Decisions, proposed architecture, and open gates

The assessment locks the constraints, but it does not prescribe a framework, database, vector store, model, hosting target, or hardware. The following is the recommended simplest architecture; Antigravity must document any deviation before implementing it.

| Area | Recommended direction | Reason / decision gate |
|---|---|---|
| API | Python + FastAPI + Pydantic response models | One service can serve the chat UI, validate the exact contract, and expose OpenAPI; FastAPI response models validate/filter output ([official docs](https://fastapi.tiangolo.com/tutorial/response-model/)) |
| Browser UI | Static HTML/CSS/vanilla JS served by the API | Assessment says simple is fine; avoids a second build/runtime service while still exercising the real API |
| LLM runtime | `llama.cpp` server with quantized GGUF open weights, called through its local HTTP API | Supports CPU/GPU inference and an OpenAI-compatible API, allowing an independent API layer and model swap ([project docs](https://github.com/ggml-org/llama.cpp/tree/master/tools/server)) |
| LLM candidate A | Qwen3-4B-Instruct-2507, Q4 GGUF candidate | Smallest viable benchmark baseline; Apache-2.0, 4B, updated instruction model, non-thinking generation. Qwen3 family reports 119 languages/dialects including Egyptian Arabic. Verify the exact quantized artifact and runtime compatibility. ([model card](https://huggingface.co/Qwen/Qwen3-4B-Instruct-2507), [Qwen3 language statement](https://qwenlm.github.io/blog/qwen3/)) |
| LLM candidate B | Gemma 4 E4B-it, Q4 GGUF | Independent multilingual challenger. Apache-2.0; Google states 35+ languages supported out of the box and pretraining in 140+; official GGUF repo lists Q4_0 at about 4.59 GB plus a small MTP file. The 4.5B effective / 8B total parameter distinction and additional context/runtime memory matter. Arabic performance still requires direct test. ([model card](https://ai.google.dev/gemma/docs/core/model_card_4), [GGUF files](https://huggingface.co/ggml-org/gemma-4-E4B-it-GGUF)) |
| LLM candidate C | Qwen3-8B Q4 GGUF | Compare alongside the smaller models as requested. Its larger size may improve instruction following or evidence handling but increases compute/VRAM needs, relevant because evaluator GPU memory is unknown. Apache-2.0; official Qwen docs provide GGUF use. ([model card](https://huggingface.co/Qwen/Qwen3-8B), [Qwen llama.cpp guide](https://qwen.readthedocs.io/en/latest/run_locally/llama.cpp.html)) |
| LLM candidate D | MedGemma 4B-it | Include in the requested comparison because it has medical-text training. Access requires review/acceptance of separate Health AI Developer Foundations terms. Its public evaluation was primarily English; Arabic/Egyptian performance is not established. Medical tuning does not replace approved-corpus grounding or safety rules. ([model card](https://huggingface.co/google/medgemma-4b-it), [terms](https://developers.google.com/health-ai-developer-foundations/terms)) |
| Embedding candidate A | `sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2` | Low-footprint baseline: 0.1B parameters, 384 dimensions, Apache-2.0, 50 languages including Arabic. Its model card has max sequence length 128, so chunking must keep evidence in-window or use a longer-context candidate. Franco-Arabic remains an empirical risk. ([model card](https://huggingface.co/sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2)) |
| Embedding candidate B | `BAAI/bge-m3` dense embeddings | Multilingual challenger: MIT, 100+ languages, 1024 dimensions and up to 8192 tokens; offers sparse and multi-vector functions, but this project should begin with dense retrieval to contain integration work. Larger footprint than MiniLM; compare on this small corpus before keeping it. ([model card](https://huggingface.co/BAAI/bge-m3)) |
| Vector retrieval | Embedded persistent Chroma collection, with `doc_id`, title, section, chunk ID, and source snippet metadata | Small corpus; persistent local index supports citations and admin re-indexing without a separate vector-service container |
| Documents and analytics | SQLite for document registry, sessions, redacted/approved analytics records, handoff records, and measured usage | Keeps a small assessment deployment self-contained; isolate persistence on a Docker volume |
| Ingestion | `python-docx`; heading-aware chunking; preserve document ID/title/section; chunk and embedding parameters in config | Inputs are Word documents and citation fields must map back to their source |
| Containers | Docker Compose for API and model server; volumes for weights and persistent app data | Clean-machine one-command startup and separation of model runtime from API/UI |
| Testing | pytest + FastAPI TestClient/httpx for contract/safety tests; standalone evaluation runner for corpus questions | Separates fast deterministic checks from model-dependent evaluation |
| Model choice | **Not locked.** Run the comparison in §4.1 on the 3090 PC; measure a CPU fallback on the laptop. | Choose only after observing accuracy, latency, memory, license, and clean-run behavior; the evaluator GPU model/VRAM remains unknown. |

### 4.1 Model comparison and hardware plan

**Known development machines:** Dell Latitude 3410, Intel Core i5-10210U, integrated Intel graphics, 16 GB RAM; and a second PC with 32 GB RAM, an NVIDIA RTX 3090, and a 12th-generation-or-newer Intel Core i9 (exact SKU unknown). Adham confirmed both machines run Windows 11 25H2 and have Docker installed. NVIDIA specifies 24 GB of memory for the RTX 3090 ([specification](https://www.nvidia.com/en-us/geforce/graphics-cards/30-series/rtx-3090-3090ti/)). Adham confirmed the external `E:` HDD has ample capacity, will move between both machines, and must hold all project data; the current workspace reports about 806 GB free on `E:` and 16 GB free on `C:`. The repository, downloaded model cache, input copies/manifests, vector index, SQLite data, and evaluation outputs must therefore be rooted on the external drive. Make the root path configurable and validate that the drive is present/writable at startup because drive letters and mounts can differ. Keep Docker Desktop's own image/VM storage location distinct from bind-mounted project data: verify and relocate it to the external drive if supported and practical, since bind mounts alone do not move Docker's internal image storage off `C:`. Treat the HDD as persistent storage, not as a benchmark-speed guarantee. Both Windows 11 25H2 machines have Docker installed, but Docker Desktop engine state, WSL2 GPU passthrough, and PC free disk remain to be verified. **Evaluation machine:** has a GPU and internet, but GPU model/VRAM, CPU, RAM, OS, and Docker GPU runtime are unknown.

**Adham's machine choice:** use the Dell laptop for development, and benchmark on both the laptop and RTX 3090 PC. This provides an integration path on the intended daily machine and performance evidence on the stronger GPU. Both machines are Windows 11 25H2 with Docker installed. On Windows, Linux-container GPU access in Docker Desktop requires the WSL 2 backend, a supported/up-to-date NVIDIA driver, and an updated WSL kernel; verify this before planning GPU inference inside Compose ([Docker GPU guidance](https://docs.docker.com/desktop/features/gpu/), [Microsoft CUDA on WSL guidance](https://learn.microsoft.com/en-us/windows/ai/directml/gpu-cuda-in-wsl)). Current workspace checks could not verify Docker daemon or WSL readiness, so use a native Windows model server for initial PC benchmarking if necessary, then verify the actual Compose GPU path separately. Docker Desktop/WSL2 running state, PC free disk, and exact PC CPU SKU remain unknown. The evaluator hardware remains the deployment constraint, so select the smallest model that passes safety, grounding, Arabic, and timing checks; record measured conditions and limitations.

| Candidate | Why keep it in the experiment | Main risk / why not preselect |
|---|---|---|
| Qwen3-4B-Instruct-2507 Q4 | Open Apache-2.0; 4B; current instruct release is non-thinking which avoids a reasoning-token overhead; Qwen3 reports Arabic dialect coverage including Egyptian; likely best first balance for the 30-second requirement | Performance on Egyptian medical wording, Franco-Arabic, strict abstention, and Q4 quantization must be tested. A community quantization requires recording source, revision, and integrity hash. |
| Gemma 4 E4B-it Q4_0 | Open Apache-2.0; multilingual model with official GGUF; stronger multilingual pretraining claim and compact deployment size; useful independent comparison | It has 8B total weights despite 4.5B effective parameter label; Google does not establish this corpus-specific Arabic/medical performance; the chosen `llama.cpp` image/version must actually support the architecture. |
| Qwen3-8B Q4 | Adds a larger Qwen checkpoint to the direct size/quality comparison | More weight and runtime demand with evaluator GPU memory unknown; record any OOM/timeout on laptop and measured GPU/CPU results. |
| MedGemma 4B-it | Adds a medical-text-tuned alternative to the direct comparison | Requires user acceptance of separate Health AI Developer Foundations terms before download; public evaluation is primarily English; Arabic/Egyptian performance must be measured. |
| MiniLM multilingual embeddings | Low resource use, 50 languages incl. Arabic; sensible baseline for nine documents | 128-token input limit may clip longer medical chunks; evaluate chunk size and retrieval recall. |
| BGE-M3 dense embeddings | 100+ languages and long input support; stronger retrieval candidate on Arabic/mixed queries; MIT | Larger runtime and vector footprint; sparse/multi-vector features are unnecessary initially. Keep only if it measurably improves retrieval enough to justify cost. |

**Benchmark protocol:** compare all four requested LLMs (Qwen3-4B-Instruct-2507, Gemma 4 E4B-it, Qwen3-8B, MedGemma 4B-it) on both laptop and PC where each model can be run; record load failures, memory exhaustion, or >30-second calls as results. MedGemma download is blocked until Adham reviews/accepts its separate terms. Freeze one retrieval corpus manifest, chunking version, prompt, decoding settings, and labeled test set while comparing LLMs. Compare both embedding candidates independently on the same query set on both machines if feasible. Include the ten public questions as regression cases but add paraphrases and safety/language cases; never branch on exact question strings. Treat safety/API correctness as hard gates: zero observed critical unsupported medical claims, valid citations for every answered result, and correct empty citations for non-answered results. Among passing candidates, compare human-reviewed answer support/completeness, language quality, per-class status results, and then latency/resource use; select the smallest/fastest model that passes rather than inventing weighted scores. Track (1) answer status accuracy by class, (2) unsupported medical-claim count and citation/source entailment, (3) language and Arabic/dialect quality with human review, (4) Recall@1/3 and MRR for embeddings, (5) warm and cold p50/p95/max response latency, (6) prompt/output tokens, model load time, peak RAM/VRAM, and disk footprint. Only promote a candidate with zero observed critical unsafe claims in the regression suite and under-30-second responses on the declared target; report test-set size and limitations rather than implying clinical validation.

**Provisional model hypothesis (not a selection):** Qwen3-8B Q4 is the quality candidate I would expect to lead on the RTX 3090, while Qwen3-4B-Instruct-2507 Q4 is the safer first deployment candidate when evaluator hardware is unspecified. Qwen's published language coverage includes Arabic dialects, and its technical report provides multilingual benchmark evidence, but those results do not establish Egyptian medical RAG quality or safety. Independent user reports comparing similar small models show different speed/detail preferences on unrelated devices/tasks; treat those as anecdotes only. For embeddings, BGE-M3 is the stronger initial hypothesis for Arabic/mixed-script retrieval because its model card reports 100+ languages and long input support, and its published MIRACL results cover Arabic; this does not guarantee improvement on these nine documents. MiniLM remains the low-cost baseline, especially if BGE's footprint or latency outweighs measured retrieval gains. Source/citation accuracy, status behavior, Arabic quality, and under-30-second latency on the actual target remain decisive; revise this hypothesis from the project benchmark, not general-purpose leaderboard scores.

**Deployment:** evaluator internet allows first-run public weight downloads. The first `docker compose up` may fetch two separate things: container images (runtime/API software, stored in Docker Desktop's internal disk) and model weights (large files, stored in a persistent cache). Use a named Docker volume for evaluator model weights by default, with an optional configurable host path; on the development machines, bind the model cache and all project persistence to the external HDD. Download weights idempotently at startup, pin model/revision/quantization, expose progress/errors, and wait for the model health check before serving requests. Subsequent starts reuse cached weights; document that a fresh evaluator machine needs internet and disk for the first download, while a warm machine should start without fetching them again. A Docker named volume survives container replacement but is removed if explicitly deleted. Keep model ID, quantization, context length, cache location, and GPU offload configurable. Test clean startup on GPU and CPU modes. Since evaluator VRAM and CUDA/Docker support are unknown, document the tested GPU and CPU path; do not claim compatibility based only on “has a GPU.” If the evaluator GPU cannot meet the 30-second target, select a smaller passing quantized candidate or report the constraint rather than relying on hidden external inference.

**Implementation status and current behavior (Nov 9):** The application currently calls a local OpenAI-compatible llama.cpp server using the configured `Qwen3-8B-Q4_K_M` model and `BAAI/bge-m3` embeddings. The generation client asks the model to compose a short answer in the question's language (Arabic for Arabic, Egyptian-dialect or Franco-Arabic input; English for English; Arabic with English medical terms for mixed) and to return verbatim evidence quotes. Every quote is checked against the chunk it names, and an answer without a verified quote returns `out_of_scope`. A deterministic post-check then compares numbers and drug/proper names in the composed text against the cited chunk text and falls back to the verified quotes if anything is unsupported. This is a provenance guard, not semantic entailment; answer accuracy and Arabic/Franco wording quality still require the agreed RTX 3090 PC review. Pre-generation emergency and personal-dose patterns short-circuit to `escalated`; empty retrieval or no verified quote returns `out_of_scope`. This is a conservative interim answer policy, and its usefulness, multilingual correctness, and factual accuracy still require the agreed RTX 3090 PC run. The laptop has no local LLM server/model artifacts, so the live end-to-end model path has not been verified there. Document admin uploads are fixed to existing KB IDs; local admin routes have no authentication and must remain loopback-only. Chroma indexing and uploaded-source persistence are not one cross-store transaction; a crash between commits may require an operator retry/rebuild.

**Shared-drive runtime:** The source repository, model cache, Chroma index, SQLite database, and reports live on the external HDD. Its drive letter changes from E: on the laptop to F: on the PC, so `PROJECT_ROOT` is optional and defaults to the source checkout path. Create a separate ignored Windows virtual environment per machine (`.venv` on the laptop and `.venv-pc` on the PC); do not rely on one machine's Python venv being portable to the other.

### Knowledge-base mapping note

Appendix A assigns KB-01 through KB-09. The nine supplied files are recognizable by topic, but `pain headache ibs arthritis.docx` appears to combine Pain & Fever, headache/migraine, IBS, and arthritis, while `ادويه القولون و التهابات المفاصل.docx` separately covers IBS and arthritis. Preserve the assessment's KB IDs, inspect each document's complete headings, and define a deterministic mapping in a manifest. Do not split, merge, or assign conflicting content to IDs silently. Document the chosen mapping and any unresolved ambiguity in the implementation notes and evaluation report.

## 5. API contract

### `POST /chat`

Request JSON:

```json
{
  "session_id": "abc123",
  "message": "في الفعالة المادة ايه Controloc؟"
}
```

`session_id` is optional; missing means start a session. `message` is required plain text.

Response JSON uses exactly these top-level fields:

```json
{
  "answer": "...",
  "citations": [
    {
      "doc_id": "KB-02",
      "title": "...",
      "section": "...",
      "snippet": "..."
    }
  ],
  "status": "answered",
  "language": "ar"
}
```

- `status` is exactly `answered`, `out_of_scope`, or `escalated`.
- `citations` contains at least one valid starter-corpus citation when answered; it is `[]` otherwise.
- `doc_id` must be one of the starter KB IDs, `KB-01` through `KB-09`.
- `language` is `ar`, `en`, or `mixed`, describing the generated answer.
- Response time must be under 30 seconds. On failure return HTTP 500 with `{"error":"..."}`.
- Never fabricate citation metadata or a snippet. Citation must identify retrieved evidence actually used in the answer.

### `GET /health`

HTTP 200 with `{"status":"ok","llm":"<model name>","embedding":"<model name>"}`. Values must reflect the models actually loaded/configured.

### Stretch endpoints

- `POST /admin/documents`: upload/index or replace a supplied document.
- `DELETE /admin/documents/{doc_id}`: remove a starter document from the active index and persist a tombstone so full rebuilds retain the removal. The original assessment source under `Docs/Data/` remains untouched and can be restored by uploading a replacement.
- `GET /admin/analytics`: expose volume, top questions, unanswered questions, token usage, and latency.
- Escalation handoff UI/API: collect the short summary and contact details when a question is escalated. Keep it separate from assistant medical guidance; no claim that a clinician was actually contacted.

## 6. Safety, privacy, and operational rules

- Treat the retrieved approved corpus as the only source of drug facts. If evidence is absent or retrieval confidence is inadequate, return `out_of_scope` instead of guessing.
- Escalate emergency/sensitive questions with non-advisory next-step language. Do not diagnose or invent a dose/treatment. Emergency phrasing must be reviewed against the assessment examples.
- Use the ten public questions as visible regression cases, including out-of-scope and emergency cases; add varied paraphrases, Arabic dialect, Franco-Arabic, mixed language, unsupported drug facts, misleading prompts, no-hit retrieval, and malformed requests. Never branch on the literal public question text.
- Do not use real patient data. Evaluation records and admin analytics must use assessment questions or synthetic examples only. Avoid retaining contact details outside the handoff demonstration dataset; state storage behavior in README.
- Validate uploaded files (type, size, extension, KB ID), reject malformed/unsupported documents with a clear error, and use verify-before-prune re-indexing so a failed replacement does not silently remove working indexed chunks. Source-file and Chroma commits remain separate and need a recovery/retry note.
- Keep model weights and application state in explicit volumes; secrets via environment files excluded from Git; no secrets baked into images.
- Apply request timeouts so API requests respect the 30-second assessment limit and expose actionable errors in logs without leaking prompts or secrets.

## 7. Seven-day work plan and prioritization

Plan days are November 3–9, with submission by November 10. Each phase ends with an Antigravity handoff; it must stop, update `TASKS.md` and `PROGRESS_LOG.md`, and provide evidence. Codex reviews the changed code/docs and evidence, sends critique and required corrections, and explicitly releases the next phase only after acceptance. Do not run phases ahead or merge their scopes.

### Day 1 — Scope lock, corpus map, model/runtime benchmark gate

- Confirm the 3090 PC's OS/CPU SKU and test environment; record the Dell/evaluator facts below and leave evaluator GPU/VRAM unresolved.
- Inspect all nine DOCX files, create KB-ID/source manifest, resolve or explicitly flag the overlapping KB-03/KB-09 content.
- Benchmark all four LLMs: Qwen3-4B-Instruct-2507 Q4, Gemma 4 E4B-it Q4_0, Qwen3-8B Q4, and MedGemma 4B-it (after Adham reviews/accepts its access terms). Check exact artifact/revision/license and runtime compatibility.
- Benchmark MiniLM multilingual vs BGE-M3 embeddings on both machines if feasible. Test multilingual, Franco-Arabic, citation faithfulness, and safety labels. Select model/quantization only if it fits measured memory and deadline.
- Define config, dependency lock, `.env.example`, and container boundary.

**Exit gate:** agreed source mapping, model IDs/quantization/license and hardware recorded or explicitly listed as unresolved; Phase 1 latency/memory baseline captured. No model choice by reputation alone.

### Day 2 — Ingestion and retrieval foundation

- Build parser for DOCX to stable normalized sections; preserve Arabic Unicode and source hierarchy.
- Implement deterministic heading-aware chunking, metadata, persistent multilingual embeddings/index, re-ingestion, and ID validation.
- Build retrieval evaluation labels from the public set plus varied paraphrases; measure Recall@k and MRR.
- Verify every chunk returns the correct source ID/title/section/snippet.

**Exit gate:** all nine files ingest reproducibly; retrieval evidence and metrics recorded; no missing or invented KB IDs.

### Day 3 — API contract and grounded answer/safety path

- Implement `/chat` and `/health` exactly; schema validation, optional session IDs, status/language determination.
- Add retrieval, citation construction, bounded context, answer generation, abstention, escalation, timeout/error handling.
- Add deterministic contract/safety tests and run all ten public cases plus multilingual paraphrases.

**Exit gate:** response schema/status/citation rules pass; unsupported and escalated cases have empty citations; no unsupported diagnosis/dose/treatment observed in the recorded suite; latency stays below 30 seconds or has a documented, actionable model/runtime adjustment.

### Day 4 — Chat UI and conversation flow

- Build responsive, accessible simple chat UI that calls `/chat`, renders language-appropriate text and citation source/section/snippet, and preserves session ID.
- Add clear out-of-scope and escalated states; create handoff form to capture short summary and contact details after escalation.
- Verify loading, API error, empty answer, RTL Arabic, mixed content, and long citation behavior.

**Exit gate:** full user flow works in browser against the API and clearly distinguishes answer, abstention, and escalation.

### Day 5 — Admin documents and analytics

- Build admin upload, replace, delete flows; validate files and KB IDs; re-index and roll back failures.
- Persist minimally necessary event/usage records; provide analytics for volume, top questions, unanswered questions, prompt/completion token counts, per-stage and end-to-end latency.
- Implement `GET /admin/analytics` and admin UI if time permits; all assessment-stated metrics must be available through an admin view or documented API.
- Keep all logs test/synthetic only; exclude secrets and real patient content.

**Exit gate:** upload/replace/delete changes retrieval without code edits; analytics numbers reconcile with recorded test interactions and model usage.

### Day 6 — Evaluation harness and reports

- Create versioned test set with expected status, answer evidence, required/forbidden claims, language, and relevant source IDs; use public questions plus paraphrases and challenge cases.
- Implement repeatable runner recording model/version, embedding/version, retrieval config, latency, tokens, predicted status, citation IDs, and human review labels.
- Produce results and failure analysis; write `MODEL_DECISION.md` (one page) and `TOKEN_USAGE.md`.
- Include per-model-call input/output tokens and timing where available; disclose tokenizer-estimated vs runtime-reported values and whether each number is suitable for production analytics.

**Exit gate:** evaluation script runs from clean state; results are recorded; model choice reflects measured safety/retrieval/latency trade-offs.

### Day 7 — Docker, clean-machine run, documentation, submission freeze

- Finalize Dockerfiles and Compose; one startup command; health check waits for model/API; persistent weight and data volumes; secrets remain external.
- Test from a clean Docker environment with the documented model download/preload mode and full hidden-set-compatible API contract.
- Finish README (prerequisites, one-command run, configuration, model/license, endpoints, data policy, admin use, evaluation, troubleshooting).
- Run acceptance suite twice, fix only assessment blockers, record final results and known limitations, freeze repository submission.

**Exit gate:** clean-machine `docker compose up` path is documented and verified; `/health` returns real model names; all deliverables exist; final test and performance report are reproducible.

### Daily scorecard and metrics

| Metric | How to measure | Target / use |
|---|---|---|
| API schema conformance | Automated request/response schema tests for required and forbidden keys/values | 100% of contract tests pass; hidden evaluator compatibility |
| Answer status classification | Labeled answered/out_of_scope/escalated test set; confusion matrix, per-class precision/recall | Report per-class values; zero unsafe answered outcomes in suite; no invented overall score threshold without baseline |
| Citation validity | Citation doc-ID membership, retrieval provenance, source-span match; human audit for entailment | 100% citations map to KB and returned evidence; report citation precision/coverage |
| Retrieval | Recall@1, Recall@3, MRR on labeled relevant source/chunk cases | Tune on dev set; publish counts/results, not an unsupported target |
| Safety | Count unsupported diagnosis/dose/treatment, emergency misclassification, answer leakage on out-of-scope prompt | Zero observed critical violations in regression set; human review required |
| Language handling | Per-language/dialect expected-language and retrieval result matrix | Include Arabic/English/mixed/Franco-Arabic separately; report failures |
| Latency | `perf_counter` stage and end-to-end timing; p50/p95 and max by hardware/test size | Every request under 30s or assessment failure; report machine and warm/cold state |
| Token usage | Runtime usage fields or exact tokenizer for each LLM call; separate prompt/completion and per-stage totals | Report mean/p50/p95 per request and identify largest call; mark approximations |
| Resource use | Peak process/container RAM and GPU VRAM; model load time; image/weight disk size | Measured on named machine; supports evaluator reproducibility |
| Admin correctness | Upload/replace/delete test with re-index consistency and rollback | 100% tested transitions correct; no stale citation after replacement/delete |
| Analytics correctness | Compare stored event aggregates with evaluation runner's source records | Exact reconciliation on seeded test interactions |
| Docker reproducibility | Clean volume startup, health readiness, one-command run, repeat start | Two clean runs; record startup time, download requirements, and failure path |

## 8. Tool and workflow inventory

Recommended tools: Python, FastAPI, Pydantic, `python-docx`, Sentence Transformers, Chroma, SQLite, `llama.cpp` server, Docker Compose, pytest, HTTPX/TestClient, and a deterministic Python evaluation runner. Pin package versions and container/model revisions. Use Git for commits and keep generated weights, databases, logs, and secrets out of version control.

Workflow per feature: inspect source and acceptance criteria → implement one phase only → run phase-specific checks → record command/results and changed files → update `TASKS.md` and append `PROGRESS_LOG.md` → stop for Codex critique. On critique, Antigravity fixes only the listed findings, reruns affected checks, reports evidence, and waits for release. Do not let later phases begin while a critical safety, schema, reproducibility, or data-loss issue remains open.

## 9. Proposed codebase structure

```text
medical-knowledge-chatbot/
├── app/
│   ├── main.py                       # FastAPI app, static UI, readiness wiring
│   ├── api/
│   │   ├── chat.py                   # POST /chat
│   │   ├── health.py                 # GET /health
│   │   ├── admin_documents.py        # stretch document endpoints
│   │   ├── analytics.py              # stretch analytics endpoint
│   │   └── handoff.py                # escalation contact capture
│   ├── schemas/                      # Pydantic request/response contracts
│   ├── core/                         # settings, logging, errors, timeouts
│   ├── ingestion/                    # DOCX parser, KB manifest, chunking, indexing
│   ├── retrieval/                    # multilingual embedder, vector search, thresholds
│   ├── generation/                   # local model client, prompt, output validation
│   ├── safety/                       # scope/status rules, emergency handling, guards
│   ├── services/                     # chat orchestration, session and handoff service
│   ├── storage/                      # SQLite repositories and Chroma persistence
│   └── static/                       # HTML, CSS, JavaScript, admin and chat UI
├── data/
│   ├── kb_manifest.yaml              # KB IDs, titles, original relative file paths
│   └── .gitkeep                      # runtime data supplied/mounted, no user data
├── tests/
│   ├── contract/
│   ├── safety/
│   ├── ingestion_retrieval/
│   └── fixtures/
├── evaluation/
│   ├── cases.jsonl                   # public cases + paraphrases/challenge set
│   ├── run_eval.py
│   └── results/                      # sanitized recorded test results
├── docs/
│   ├── MODEL_DECISION.md
│   ├── TOKEN_USAGE.md
│   ├── API_CONTRACT.md
│   └── SAFETY_AND_DATA.md
├── project-continuity-skill/         # BRIEF.md, TASKS.md, REQUESTS.md, PROGRESS_LOG.md
├── Dockerfile
├── compose.yaml
├── pyproject.toml / lockfile
├── .env.example
├── .gitignore
└── README.md
```

Each folder has a clear owner: API handlers adapt HTTP, services orchestrate, ingestion/retrieval deal with the corpus, safety makes status/guard decisions, and storage persists state. This keeps citations and safety independently testable without introducing production-scale service boundaries.

## 10. Antigravity execution and review rules

- Antigravity may use the user's stated Gemini model mix, but must explain and verify code rather than treating generated output as evidence.
- Provide one phase prompt at a time from `TASKS.md`. Each prompt names allowed scope, exact acceptance criteria, tests/evidence, files to update, and the stop condition.
- Antigravity stops after each phase and submits a concise handoff with diff summary, commands and results, unresolved risks, and continuity-file updates.
- Codex critiques each completed phase and sends concrete blockers/corrections. Antigravity does not start the next phase until Codex explicitly releases it after review.
- No coding by Codex unless Adham explicitly instructs it. Planning and continuity-file maintenance are authorized.
- At the beginning of every session, read this file, recent `PROGRESS_LOG.md`, `TASKS.md`, and `REQUESTS.md`. At end, update task status and append a log entry. `PROGRESS_LOG.md` is append-only; never rewrite past entries.
