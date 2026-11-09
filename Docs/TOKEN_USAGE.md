# Token Usage and Performance Report (Phase 1 Baseline & Dual-Device Benchmark)

> **Status:** Phase 1 Baselines Complete on Both Dell Latitude 3410 (CPU Fallback) and Alienware Aurora R13 (RTX 3090 GPU Offload) across all 4 LLM candidates. Phase 6 End-to-End Pipeline Profiling Pending.

---

## 1. Side-by-Side Dual-Device Token & Latency Benchmark Table

Measured across the 16 labeled test cases (`DEV-01`..`DEV-10`, `CHAL-11`..`CHAL-16`) on identical frozen `BGE-M3` top-3 retrieved context with `llama-server` build `b12110` (`max_tokens=280`, `temp=0.0`):

| Model Candidate | Environment & Backend | Mean Prompt Tokens | Mean Completion Tokens | Mean Prompt Prefill Speed (t/s) | Mean Generation Speed (t/s) | E2E Latency p50 (s) | E2E Latency p95 (s) | E2E Latency Max (s) | Calls >30s SLA |
|---|---|---:|---:|---:|---:|---:|---:|---:|---|
| `Qwen3-4B-Instruct-2507-Q4_K_M` | Dell Laptop (i5-10210U CPU) | 1,012.8 | 146.4 | 18.49 | 3.05 | 81.93 | 128.58 | 130.19 | 16/16 (100% fail) |
| `Qwen3-4B-Instruct-2507-Q4_K_M` | **RTX 3090 PC (Vulkan `-ngl 99`)** | **1,012.9** | **147.4** | **2,137.86** | **70.58** | **2.21** | **7.93** | **15.25** | **0/16 (0% fail)** |
| `gemma-4-E4B-it-Q4_0` | Dell Laptop (i5-10210U CPU) | 945.8 | 100.8 | 22.86 | 2.71 | 60.53 | 105.74 | 117.71 | 16/16 (100% fail) |
| `gemma-4-E4B-it-Q4_0` | **RTX 3090 PC (Vulkan `-ngl 99`)** | **951.8** | **112.5** | **1,900.17** | **36.67** | **2.35** | **15.50** | **40.14** | **1/16 (6.25% fail)** |
| `Qwen3-8B-Q4_K_M` | Dell Laptop (i5-10210U CPU) | 880.5* | 101.0* | 9.79 | 1.63 | 157.79 | 240.01 | 240.02 | 16/16 (100% fail) |
| `Qwen3-8B-Q4_K_M` | **RTX 3090 PC (Vulkan `-ngl 99`)** | **1,012.9** | **150.2** | **1,072.82** | **38.64** | **3.91** | **7.21** | **7.31** | **0/16 (0% fail)** |
| `medgemma-4b-it` | Dell Laptop (i5-10210U CPU) | 945.8 | 187.6 | 25.58 | 4.03 | 88.83 | 122.01 | 129.79 | 16/16 (100% fail) |
| `medgemma-4b-it` | **RTX 3090 PC (Vulkan `-ngl 99`)** | **945.8** | **178.4** | **4,505.54** | **143.00** | **1.62** | **2.22** | **2.34** | **0/16 (0% fail)** |

*\*Note on Laptop CPU run: `Qwen3-8B-Q4_K_M` timed out at 240s on 2 of 16 cases (`DEV-02`, `DEV-04`). On the RTX 3090 PC with GPU offload, all 16 cases completed with 0 timeouts and max latency of 7.31s.*

---

## 2. Measurement Methodology & Precision Limits

- **Measurement Source**: Exact hardware execution counters reported directly by `llama-server.exe` through the OpenAI-compatible `/v1/chat/completions` API response (`usage.prompt_tokens`, `usage.completion_tokens`, `timings.prompt_per_second`, `timings.predicted_per_second`), and end-to-end wall-clock time measured via Python `time.perf_counter()`.
- **Production Analytics Suitability**: These are **exact runtime-level counters**, not tokenizer approximations or rough character-count heuristics. In production (Phase 5/6), logging these exact response fields from `llama-server` provides auditable per-request token volume and latency data.
- **Throughput Leader**: `medgemma-4b-it` achieved the highest generation speed (**143.0 t/s**) and prefill speed (**4,505.54 t/s**) on the RTX 3090, leading to a maximum latency of just **2.34s**.
- **Largest Observed Calls**:
  - **Prompt Tokens**: Case `DEV-03` with 1,117 prompt tokens (3 retrieved section chunks + system prompt).
  - **Completion Tokens**: Cases `DEV-02`, `CHAL-13`, `CHAL-14` hitting the 280-token cap (`max_tokens=280`) when outputting comprehensive trade-name or antibiotic lists under JSON schema constraints.
  - **Latency Outlier on PC**: `gemma-4-E4B-it-Q4_0` on `DEV-01` took **40.14s** due to longer initial KV slot allocation and 280-token generation at 36.7 t/s. On `Qwen3-8B`, the maximum latency was **7.31s** and on `medgemma-4b-it` the maximum latency was **2.34s**.

---

## 3. Performance & Latency Optimization Roadmap for Phase 2 & 3

1. **Sub-Section Chunking**: Reducing chunk lengths from ~900 characters to ~350 characters will lower mean prompt tokens from ~950–1,010 to ~350–450 tokens. This will directly decrease prefill time on both GPU and CPU.
2. **Prompt Caching (`--cache-reuse`)**: The clinical drug-information system prompt (~170 tokens) is static across all requests. Enabling KV-cache reuse will eliminate prefill overhead for the system prompt.
3. **Deterministic Fast Path for Red Flags**: Emergency queries (`CHAL-15`, `CHAL-16`) and clear non-medical queries (`DEV-07`, `DEV-08`) will be triaged by deterministic keyword/pattern guards before invoking the LLM, reducing latency for emergency escalation to under 50 ms and eliminating MedGemma's single safety violation.
