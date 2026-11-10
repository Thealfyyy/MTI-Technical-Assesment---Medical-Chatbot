# Phase 1 Handoff Document & Prompt for the RTX 3090 PC

> **Archive notice:** this is the Phase 1 record and the prompt that was used for the Phase 1 GPU benchmark. Its `.venv` / `run_pc_benchmark.ps1` steps are historical and must not be followed now. Current run and acceptance steps live in [`README.md`](../README.md) (machine-local `.venv-pc`, Qwen3-8B Vulkan llama-server, uvicorn, `/health`, `evaluation.run_eval`).

This file is stored on the shared external drive (`docs/PHASE1_LAPTOP_REPORT_AND_PC_HANDOFF.md`) so you can open this exact context in Antigravity on the **RTX 3090 PC** without needing to manually copy local `C:\Users\User\.gemini\antigravity` app data between machines.

---

## Part 1 — Copy-Paste Prompt for Antigravity on the RTX 3090 PC

Open the project folder (`MTI Technical Assesment - Medical Chatbot` on the external drive) in **Antigravity on the RTX 3090 PC**, start a chat, and paste the following prompt:

```markdown
Read these files first before doing anything:
- `project-continuity-skill/BRIEF.md`
- `project-continuity-skill/TASKS.md`
- `project-continuity-skill/REQUESTS.md`
- `project-continuity-skill/PROGRESS_LOG.md` (especially Session 10)
- `docs/PHASE1_LAPTOP_REPORT_AND_PC_HANDOFF.md`
- `docs/MODEL_DECISION.md`
- `docs/TOKEN_USAGE.md`
- `evaluation/results/phase1_benchmark_laptop.json`

We are in **Phase 1 only** of the MTI AI Solutions AI Engineer Technical Assessment. The Dell Latitude 3410 laptop setup, corpus manifest (`data/kb_manifest.yaml`), `KB-03` vs `KB-09` overlap analysis, and laptop CPU benchmark (`evaluation/results/phase1_benchmark_laptop.json`) are already complete on this shared external drive, and all open-weights GGUF models, embedding models, and the Vulkan GPU build of `llama-server.exe` (`b12110`) are already cached in `.cache/`.

On this RTX 3090 PC, perform ONLY the remaining Phase 1 PC verification and benchmark tasks:
1. Run `powershell -ExecutionPolicy Bypass -File .\evaluation\run_pc_benchmark.ps1` (which adapts `.venv\pyvenv.cfg` if the PC's Python path differs, probes this PC's exact Intel Core i9 CPU SKU, NVIDIA RTX 3090 driver/VRAM, RAM, OS build, external drive mount letter, internal `C:` free disk, Docker Desktop engine/VHDX path, and WSL2 status, and runs `evaluation/phase1_benchmark.py --stage all` with Vulkan GPU offload `-ngl 99`, saving results to `evaluation/results/phase1_benchmark_rtx3090_pc.json`).
2. Also verify whether Docker Desktop's Linux engine is running on this PC and whether container GPU passthrough (`docker info` / NVIDIA runtime) is active; record anything not running or unverifiable honestly.
3. Do NOT accept terms for or download `google/medgemma-4b-it` unless Adham explicitly confirms he has reviewed and accepted the Health AI Developer Foundations terms.
4. Update `docs/MODEL_DECISION.md` and `docs/TOKEN_USAGE.md` to add the side-by-side RTX 3090 PC vs. Dell Latitude 3410 laptop benchmark tables.
5. Update `project-continuity-skill/TASKS.md` Phase 1 checkboxes and append **Session 11** to `project-continuity-skill/PROGRESS_LOG.md` (strictly append-only; do not edit Sessions 0–10).
6. Stop at the Phase 1 gate (do not start Phase 2) and output a structured Phase 1 report for this RTX 3090 PC matching the exact sections in `docs/PHASE1_LAPTOP_REPORT_AND_PC_HANDOFF.md` (Machine/Runtime/Docker/WSL2/GPU facts on the PC, Side-by-Side Laptop vs. RTX 3090 PC Embedding & LLM Benchmark Table including load time, memory, prefill/gen t/s, p50/p95/max latency, calls >30s, status accuracy, citation validity, safety violations, MedGemma status, and updated continuity files).
```

---

## Part 2 — Printout of the Dell Latitude 3410 Phase 1 Report (Session 10)

### 1. Repository Location & Scaffold Created
- **Git Repository Root**: Initialized (`git init -b main`) at `E:/Projects/MTI Technical Assesment - Medical Chatbot/.git/` on the shared external HDD.
- **Writable Path Validation**: Implemented `Settings.from_env()` and `validate_storage_paths()` in `app/core/config.py`.
- **Scaffold Created**: `.gitignore`, `.env.example`, `pyproject.toml`, `README.md`, `Dockerfile`, `compose.yaml`, `app/` module placeholders, `data/kb_manifest.yaml`, `evaluation/cases.jsonl`, `evaluation/phase1_benchmark.py`, `evaluation/run_pc_benchmark.ps1`, `evaluation/results/phase1_benchmark_laptop.json`, and `docs/{MODEL_DECISION.md,TOKEN_USAGE.md,API_CONTRACT.md,SAFETY_AND_DATA.md}`.

### 2. Corpus-to-KB Manifest & `KB-03` vs `KB-09` Overlap Findings
- **Deterministic 1-to-1 Mapping (`data/kb_manifest.yaml`)**:
  - `KB-01`: `asthma w copd.docx` (622 paras, 21 headings)
  - `KB-02`: `gerd& vomiting.docx` (399 paras, 22 headings)
  - `KB-03`: `pain headache ibs arthritis.docx` (419 paras, 8 headings in Part 2 only) — contains **ONLY** `1. Pain & Fever – الألم والحرارة` (paras 000–245) and `2. Headache & Migraine – الصداع` (paras 246–418); zero IBS or dedicated Arthritis sections.
  - `KB-04`: `pharyngitis.docx` (201 paras, 11 headings)
  - `KB-05`: `أدوية الالتهاب الرئوي.docx` (294 paras, 10 headings)
  - `KB-06`: `ادويه الحساسيه و الجيوب الانفيه.docx` (620 paras, 18 headings)
  - `KB-07`: `ادويه السكر.docx` (516 paras, 37 headings)
  - `KB-08`: `ادويه الضغط و الكوليسترول.docx` (824 paras, 58 headings)
  - `KB-09`: `ادويه القولون و التهابات المفاصل.docx` (509 paras, **0 Word Heading styles** — all `Normal` style) — contains **ONLY** `1. أدوية القولون العصبي – IBS` (paras 000–238) and `2. أدوية التهاب المفاصل – Arthritis` (paras 239–508).
- **Cross-Document Pharmacological Overlap**: Systemic NSAIDs (`Brufen`, `Cataflam`, `Voltaren`, `Mobic`, `Celebrex`, `Arcoxia`, `Naprosyn`, `Xefo`) and `Paracetamol` (`Panadol`, `Cetal`, `Adol`, `Paramol`, `Fevadol`, `Abimol`) appear in `KB-03`, `KB-09`, `KB-04`, and `KB-06`.

### 3. Dell Latitude 3410 Machine, Runtime & Storage Facts Verified
- **Host / Model**: `Alfy` / `Dell Inc. Latitude 3410`
- **CPU**: `Intel(R) Core(TM) i5-10210U CPU @ 1.60GHz` (4 cores / 8 logical processors)
- **GPU**: `Intel(R) UHD Graphics` (`31.0.101.2135`, 1 GB AdapterRAM, CPU-only inference)
- **RAM**: 16.0 GB (`16,928,935,936` bytes)
- **OS**: Windows 11 25H2 (`Build 26200.9711`)
- **Disk Free Space**: `E:\` has ~788 GB free of 1863 GB; `C:\` has ~10.2–19.7 GB free of 475.71 GB.
- **Docker & WSL2**: Docker CLI `28.4.0`, Compose `v2.39.2-desktop.1`; Linux engine Stopped; `docker_data.vhdx` is 8.5 GB on `C:\Users\User\AppData\Local\Docker\wsl\disk\docker_data.vhdx`. WSL `3.0.3.0` (`Ubuntu` WSL1 Stopped, `docker-desktop` WSL2 Stopped).

### 4. Dell Latitude 3410 Benchmark Summary (`evaluation/results/phase1_benchmark_laptop.json`)
- **Embeddings**:
  - `paraphrase-multilingual-MiniLM-L12-v2` (rev `e8f8c211...`, Apache-2.0): load `123.19s`, encode `16.75s`, peak RSS `1017.4 MB`, query p50 `39.06 ms` / p95 `635.31 ms`, `Recall@1 = 0.50`, `Recall@3 = 0.60`, `MRR@5 = 0.5333`.
  - `BAAI/bge-m3` (rev `5617a9f6...`, MIT): load `332.75s`, encode `428.42s`, peak RSS `1499.8 MB`, query p50 `273.72 ms` / p95 `449.80 ms`, `Recall@1 = 0.70`, `Recall@3 = 0.80`, `MRR@5 = 0.7333`.
- **LLMs (CPU-only, `-t 4 -tb 8`, frozen `BGE-M3` top-3 context)**:
  - `Qwen3-4B-Instruct-2507-Q4_K_M`: load `4.13s`, peak RSS `5463.4 MB`, prefill `18.49 t/s`, gen `3.05 t/s`, e2e p50 `81.93s` / p95 `128.58s` / max `130.19s`, calls >30s `16/16`, status accuracy `6/16 (37.5%)`, citation validity `16/16 (100%)`, safety violations `0`.
  - `gemma-4-E4B-it-Q4_0`: load `45.76s`, peak RSS `5830.6 MB`, prefill `22.86 t/s`, gen `2.71 t/s`, e2e p50 `60.53s` / p95 `105.74s` / max `117.71s`, calls >30s `16/16`, status accuracy `10/16 (62.5%)`, citation validity `15/16 (93.8%)`, safety violations `0`.
  - `Qwen3-8B-Q4_K_M`: load `141.78s`, peak RSS `6721.8 MB`, prefill `9.79 t/s`, gen `1.63 t/s`, e2e p50 `157.79s` / p95 `240.01s` / max `240.02s`, calls >30s `16/16` (2 timeouts at 240s), status accuracy `9/16 (56.2%)`, citation validity `16/16 (100%)`, safety violations `0`.
  - `medgemma-4b-it`: `blocked_pending_terms`.
