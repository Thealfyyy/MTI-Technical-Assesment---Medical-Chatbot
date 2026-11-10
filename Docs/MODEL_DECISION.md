# Model Decision Record (Phase 1 Baseline & Dual-Device Benchmark)

> **Status:** Phase 1 Benchmarks Completed on Both Target Environments across all 4 LLMs + 2 Embedding Candidates:
> 1. Dell Latitude 3410 (CPU Fallback Baseline — all 4 LLMs + 2 embedding models measured)
> 2. Alienware Aurora R13 PC (NVIDIA GeForce RTX 3090 24GB + Vulkan GPU Offload `-ngl 99` — all 4 LLMs + 2 embedding models measured)
> 
> **MedGemma (`google/medgemma-4b-it`)**: Adham explicitly confirmed review and acceptance of Google Health AI Developer Foundations terms on 2026-11-07. Weights (`medgemma-4b-it-Q4_K_M.gguf`, 2.49 GB, SHA256 `d842e8d2...`) downloaded and verified on disk. Tested on both Dell Laptop CPU and Alienware RTX 3090 PC.
> 
> **Model Selection Gate Status:** Per Adham's direction, all 4 models have been empirically evaluated on both devices, the top 3 models are identified for system integration, and 1 final test will be executed after the full remaining system is completed.

---

## 1. Candidate Model Artifact Provenance, Licensing & Sizes

All open-weights artifacts were verified against Hugging Face metadata, downloaded to `<PROJECT_ROOT>/.cache/` on the shared external HDD (`E:\` on laptop / `F:\` on PC), and SHA256-verified on disk.

### 1.1 Embedding Candidates

| Candidate ID | HF Commit Revision | License | Max Seq Len | Dim | Cached Footprint | Runtime Compatibility |
|---|---|---|---:|---:|---:|---|
| `sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2` | `e8f8c211226b894fcb81acc59f3b34ba3efd5f42` | Apache-2.0 | 128 | 384 | ~471 MB | `sentence-transformers` 6.2.0 (`torch` 2.15.0+cpu) |
| `BAAI/bge-m3` | `5617a9f61b028005a4858fdac845db406aefb181` | MIT | 8192 | 1024 | ~2.27 GB | `sentence-transformers` 6.2.0 (`torch` 2.15.0+cpu) |

### 1.2 LLM Candidates

| Candidate ID | Base Model (Revision) | GGUF Repo (Revision) | Artifact Filename | Quantization | Exact Size (Bytes / GiB) | SHA256 Checksum | License | Gate Status |
|---|---|---|---|---|---:|---|---|---|
| `Qwen3-4B-Instruct-2507-Q4_K_M` | `Qwen/Qwen3-4B-Instruct-2507` (`cdbee75f17c01a7cc42f958dc650907174af0554`) | `unsloth/Qwen3-4B-Instruct-2507-GGUF` (`a06e946bb6b655725eafa393f4a9745d460374c9`) | `Qwen3-4B-Instruct-2507-Q4_K_M.gguf` | `Q4_K_M` | `2,497,281,120` (2.33 GiB) | `3605803b982cb64aead44f6c1b2ae36e3acdb41d8e46c8a94c6533bc4c67e597` | Apache-2.0 | Verified & Cached |
| `gemma-4-E4B-it-Q4_0` | `google/gemma-4-E4B-it` (`4ecc2ba63bcac23ba4a767fc87025b1450f84c9c`) | `ggml-org/gemma-4-E4B-it-GGUF` (`a69f018d7678a2b9f5e705f8903d6fb29b9b25dc`) | `gemma-4-E4B-it-Q4_0.gguf` | `Q4_0` | `4,590,807,392` (4.28 GiB) | `a555b900214b477d8880e7832e0b8925e139b0159640036b09fe472b6f2097f2` | Apache-2.0 | Verified & Cached |
| `Qwen3-8B-Q4_K_M` | `Qwen/Qwen3-8B` (`b968826d9c46dd6066d109eabc6255188de91218`) | `Qwen/Qwen3-8B-GGUF` (`7c41481f57cb95916b40956ab2f0b139b296d974`) | `Qwen3-8B-Q4_K_M.gguf` | `Q4_K_M` | `5,027,783,488` (4.68 GiB) | `d98cdcbd03e17ce47681435b5150e34c1417f50b5c0019dd560e4882c5745785` | Apache-2.0 | Verified & Cached |
| `medgemma-4b-it` | `google/medgemma-4b-it` (`290cda5eeccbee130f987c4ad74a59ae6f196408`) | `unsloth/medgemma-4b-it-GGUF` (`fa17ea2647ef236db91adfe1465a61ab6562cf2c`) | `medgemma-4b-it-Q4_K_M.gguf` | `Q4_K_M` | `2,489,894,720` (2.32 GiB) | `d842e8d2aca3fc5e613c5f9255e693768eeccae729e5c2653159eb79afe751f3` | Health AI Dev Foundations Terms | Verified & Cached |

---

## 2. Benchmark Environments & Test Protocol

Both benchmarks evaluated the exact same 16 labeled evaluation cases (`DEV-01`..`DEV-10` public dev questions + `CHAL-11`..`CHAL-16` challenge cases) across 247 section chunks parsed from the 9 DOCX documents (`data/kb_manifest.yaml`).

> **Chunking note:** every figure below is a Phase 1 measurement on that 247-chunk section-level index. Phase 2 re-chunked the same nine documents at sub-section level, and the active `data/chroma` index now holds 414 chunks, so current prompt-token and latency numbers will differ from these baselines.


- **Laptop Environment (CPU Fallback)**:
  - **Host / Model**: `Alfy` / `Dell Inc. Latitude 3410`
  - **CPU**: Intel Core i5-10210U (4 physical cores / 8 logical processors @ 1.60 GHz)
  - **GPU**: Intel UHD Graphics (integrated, 1 GB AdapterRAM, CPU-only execution)
  - **RAM**: 16 GB DDR4
  - **OS**: Windows 11 25H2 (`Build 10.0.26200.9711`)
  - **Storage**: External HDD `E:\` (NTFS, 792 GB free), Internal `C:\` (10.2 GB free)
  - **Runtime**: `llama-server.exe` build `b12110` (`win-cpu-x64`), `-c 4096 -t 4 -tb 8 -np 1 --temp 0.0 --reasoning-budget 0`
  - **Raw Output**: `evaluation/results/phase1_benchmark_laptop.json`

- **PC Environment (RTX 3090 GPU Offload)**:
  - **Host / Model**: `DESKTOP-TD0BULG` / `Alienware Alienware Aurora R13`
  - **CPU**: 12th Gen Intel Core i9-12900KF (16 physical cores [8P+8E] / 24 logical processors)
  - **GPU**: NVIDIA GeForce RTX 3090 (24,576 MiB VRAM, Driver `617.42`)
  - **RAM**: 31.8 GB DDR5
  - **OS**: Windows 11 (`Build 10.0.26300.9818`, DisplayVersion `26H2`)
  - **Storage**: External HDD `F:\` (NTFS, 787.66 GB free), Internal `C:\` (163.34 GB free)
  - **Runtime**: `llama-server.exe` build `b12110` (`win-vulkan-x64`), `-ngl 99 -c 4096 -t 8 -tb 16 -np 1 --temp 0.0 --reasoning-budget 0`
  - **Raw Output**: `evaluation/results/phase1_benchmark_rtx3090_pc.json`

---

## 3. Side-by-Side Dual-Device Benchmark Comparison

### 3.1 Embedding Model Comparison (Laptop CPU vs. RTX 3090 PC)

Both embedding models were benchmarked on CPU in Python via `sentence-transformers`:

| Embedding Candidate | Environment | Model Load (s) | 247-Chunk Encode (s) | Peak RSS (MB) | Query Latency p50 / p95 / max (ms) | Recall@1 | Recall@3 | MRR@5 | Key Diagnostic |
|---|---|---:|---:|---:|---|---:|---:|---:|---|
| `paraphrase-multilingual-MiniLM-L12-v2` | Dell Laptop (i5-10210U) | 123.19s | 16.75s | 1017.4 MB | 39.06 / 635.31 / 1155.57 ms | 0.50 | 0.60 | 0.5333 | Lightweight; 128-token cap truncates longer chunks; misses `DEV-01`, `DEV-04`, `CHAL-11`, `CHAL-12` |
| `paraphrase-multilingual-MiniLM-L12-v2` | RTX 3090 PC (i9-12900KF) | 4.96s | 2.36s | 1161.2 MB | 9.12 / 10.89 / 11.67 ms | 0.50 | 0.60 | 0.5333 | 7.1× faster encode, 4.3× lower p50 latency; identical retrieval scores |
| `BAAI/bge-m3` | Dell Laptop (i5-10210U) | 332.75s | 428.42s | 1499.8 MB | 273.72 / 449.80 / 486.96 ms | **0.70** | **0.80** | **0.7333** | Strong multilingual retrieval (hits 8/8 non-franco queries); missed only pure Franco-Arabic `CHAL-11` & `CHAL-12` |
| `BAAI/bge-m3` | RTX 3090 PC (i9-12900KF) | 2.05s | 51.01s | 2070.2 MB | 47.13 / 60.45 / 61.55 ms | **0.70** | **0.80** | **0.7333** | **8.4× faster encode** (51.0s vs 428.4s); **5.8× faster query p50** (47.1ms vs 273.7ms); identical retrieval scores |

### 3.2 LLM Candidate Comparison (Laptop CPU vs. RTX 3090 PC Vulkan GPU Offload)

LLMs evaluated on frozen `BGE-M3` top-3 retrieved context with grammar-constrained JSON schema:

| LLM Candidate | Environment & Backend | Load Time (s) | Peak RSS (MB) | Prompt Prefill (t/s) | Token Gen (t/s) | E2E Latency p50 / p95 / max (s) | Calls >30s SLA | Status Accuracy | Citation Validity | Safety Violations | Operational Verdict |
|---|---|---:|---:|---:|---:|---|---|---|---|---:|---|
| `Qwen3-4B-Instruct-2507-Q4_K_M` | Laptop (CPU `-t 4 -tb 8`) | 4.13s | 5463.4 | 18.49 | 3.05 | 81.93 / 128.58 / 130.19s | **16/16 (100% fail)** | 6/16 (37.5%) | 16/16 (100%) | **0** | CPU prefill too slow for full context (>80s) |
| `Qwen3-4B-Instruct-2507-Q4_K_M` | **PC (RTX 3090 Vulkan `-ngl 99`)** | **5.10s** | 4793.1 | **2,137.86** | **70.58** | **2.21 / 7.93 / 15.25s** | **0/16 (0% fail)** | 6/16 (37.5%) | 16/16 (100%) | **0** | **115.6× prefill speedup**, **23.1× gen speedup**, 100% SLA compliant |
| `gemma-4-E4B-it-Q4_0` | Laptop (CPU `-t 4 -tb 8`) | 45.76s | 5830.6 | 22.86 | 2.71 | 60.53 / 105.74 / 117.71s | **16/16 (100% fail)** | 10/16 (62.5%) | 15/16 (93.8%) | **0** | Strong classification accuracy; CPU generation too slow (>60s) |
| `gemma-4-E4B-it-Q4_0` | **PC (RTX 3090 Vulkan `-ngl 99`)** | 50.44s | 4696.4 | 1,900.17 | 36.67 | 2.35 / 15.50 / **40.14s** | **1/16 (6.25% fail)** | **10/16 (62.5%)** | 16/16 (100%) | **0** | Strong accuracy; 1 call (`DEV-01`) exceeded 30s SLA (40.14s); lowest GPU gen speed (36.7 t/s) |
| `Qwen3-8B-Q4_K_M` | Laptop (CPU `-t 4 -tb 8`) | 141.78s | 6721.8 | 9.79 | 1.63 | 157.79 / 240.01 / 240.02s | **16/16 (100% fail)** | 9/16 (56.2%) | 16/16 (100%) | **0** | 2 timeouts at 240s; CPU fallback unusable without chunk trimming |
| `Qwen3-8B-Q4_K_M` | **PC (RTX 3090 Vulkan `-ngl 99`)** | 44.90s | 7008.2 | 1,072.82 | 38.64 | 3.91 / 7.21 / **7.31s** | **0/16 (0% fail)** | 9/16 (56.2%) | 16/16 (100%) | **0** | **109.6× prefill speedup**, **23.7× gen speedup**, max latency **7.31s**, 100% SLA compliant |
| `medgemma-4b-it` | Laptop (CPU `-t 4 -tb 8`) | 6.82s | 7319.6 | 25.58 | 4.03 | 88.83 / 122.01 / 129.79s | **16/16 (100% fail)** | 9/16 (56.2%) | 16/16 (100%) | **1** | Fastest CPU generation (4.03 t/s); answered CHAL-16 overdose with clinical guideline instead of escalating |
| `medgemma-4b-it` | **PC (RTX 3090 Vulkan `-ngl 99`)** | 47.56s | 6081.2 | **4,505.54** | **143.00** | **1.62 / 2.22 / 2.34s** | **0/16 (0% fail)** | **10/16 (62.5%)** | 16/16 (100%) | **1** | **Fastest throughput (143 t/s)**, max latency **2.34s**; requires deterministic pre-LLM escalation guard for overdose/poisoning (`CHAL-16`) |

---

## 4. Key Architectural Evidence & Top 3 Model Selection

Per Adham's direction (*"keep the top 3 models, and we will do 1 final test after the full remaining system is done"*), the 4 benchmarked candidates are ranked based on empirical speed, accuracy, SLA compliance, and safety:

### Recommended Top 3 Models to Retain:

1. **`Qwen3-8B-Q4_K_M` (Primary High-Quality Grounding Candidate)**:
   - **Strengths**: Highest reasoning capacity, Apache-2.0 open-weights license, non-thinking instruction model, zero safety violations across both testbeds, 100% citation validity, and consistent sub-8s latency on the RTX 3090 (p50: 3.91s, max: 7.31s, 0/16 calls >30s).
   - **Role**: Primary candidate for high-accuracy Arabic medical RAG on evaluator environments with a discrete GPU.

2. **`medgemma-4b-it-Q4_K_M` (Lead Medical Domain Throughput Candidate)**:
   - **Strengths**: Highest token generation speed on the RTX 3090 (**143.0 t/s**, ~3.8× faster than Qwen3-8B and Gemma-4-E4B), fastest end-to-end response time (p50: 1.62s, max: 2.34s), tied for highest status accuracy (62.5%), 100% citation validity, and specialized clinical terminology comprehension.
   - **Required Guard**: Produced 1 safety violation on `CHAL-16` (answering acute toxic overdose management instead of escalating). In Phase 3, pairing MedGemma with a deterministic pre-LLM regex/keyword escalation guard for red-flag symptoms/overdose eliminates this vulnerability entirely while retaining its 143 t/s inference speed.

3. **`Qwen3-4B-Instruct-2507-Q4_K_M` (Lead Compact Candidate for Constrained Hardware)**:
   - **Strengths**: Compact 2.33 GB file size, fastest cold-load time (4–5s), Apache-2.0, zero safety violations, 100% citation validity, and 100% SLA compliance on RTX 3090 (p50: 2.21s, max: 15.25s).
   - **Role**: Essential lightweight fallback candidate if evaluator hardware has limited VRAM or strict memory caps.

### Candidate Dropped from Top 3:
- **`gemma-4-E4B-it-Q4_0`**:
  - Exceeded the 30-second assessment SLA on `DEV-01` (40.14s) even on the RTX 3090.
  - Slowest token generation speed on GPU among the 4 candidates (36.67 t/s vs 143.0 t/s for MedGemma and 70.58 t/s for Qwen3-4B).
  - At 4.28 GiB, it consumes nearly twice the storage/memory of `medgemma-4b-it` (2.32 GiB) without matching its generation throughput.
