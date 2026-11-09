# Phase 2 — Ingestion and Multilingual Retrieval Foundation Report

**Document Version:** 1.4.0  
**Date:** 2026-11-08  
**Status:** Complete — local review and process-restart recovery tests passed  
**Target Environment:** Alienware Aurora R13 (Intel Core i9-12900KF, 32GB RAM, NVIDIA RTX 3090 24GB, Windows 11 26H2) / Dell Latitude 3410 Laptop Fallback  
**Persistent Storage:** `data/chroma`  
**Embedding Model:** `BAAI/bge-m3` (1024-dimensional, normalized cosine space)  

---

## 1. Executive Summary & Gate Status

Phase 2 establishes the assessment prototype's multilingual ingestion, recoverable index rebuild, and retrieval foundation. The test results below cover simulated process interruptions and this small evaluation set; they do not establish production or clinical readiness.

1. **Heading-, Sub-section-, and Table-Aware DOCX Parser (`app/ingestion/docx_parser.py`):**
   * Preserves exact Arabic Unicode (NFC), hierarchical document structure, and clinical categories.
   * Parses **153 embedded Word tables** across all 9 documents using python-docx `iter_block_items()`, extracting full brand-to-generic mappings (e.g., *Cataflam &rarr; Diclofenac potassium*, *Brufen &rarr; Ibuprofen*) and OTC classifications.
   * Completely eliminates the 85 stub/empty category headings observed in naive chunkers, producing **414 rich, atomic clinical chunks**.
   * Preserves critical clinical facts (such as ARBs pregnancy contraindications in `KB-08`, Metformin renal eGFR thresholds in `KB-07`, and Metronidazole 48-hour alcohol interaction in `KB-02`) without clipping.

2. **WAL-Coordinated Rebuild Recovery & Verification (`app/retrieval/vector_store.py`):**
   * **Full Rebuild Recovery:** `ChromaStore.atomic_rebuild()` uses a WAL written by atomic file replacement and file flush before collection renames. Startup recovery checks actual live/staging/backup collection state and can roll forward when staging exists or restore the backup if staging is unavailable.
   * **Targeted Document Replacement:** `atomic_replace_document()` computes first, then upserts and verifies new chunks before pruning obsolete IDs. If interrupted after upsert, old and new IDs can coexist until the targeted ingestion is retried; this preserves data but is not an instantaneous atomic view.
   * **Recovery Tests (`tests/ingestion_retrieval/test_vector_store_atomicity.py`):** 10 tests passed locally, including process-restart simulations immediately before and after each collection rename, targeted replacement verification failure, and threshold behavior. These simulate application interruption; they do not emulate physical power loss or storage-device failure.

3. **Hybrid Multilingual Search & Egyptian Franco Normalizer (`app/retrieval/franco_normalizer.py`, `app/retrieval/hybrid_search.py`):**
   * Solves zero-recall failure on Egyptian Franco-Arabic queries (`CHAL-11`, `CHAL-12`) via deterministic Arabizi transliteration and medical vocabulary mapping (`7omo2a` &rarr; `حموضة`, `katably` &rarr; `كتبلي`, `soda3` &rarr; `صداع`, etc.). (Rule modifications reserved for Adham).
   * Fast in-memory BM25 lexical search with conversational stop-word filtering (`what`, `are`, `the`, `is`, `common`, `ما`, `هي`, `هل`, etc.) and cross-lingual clinical synonym expansion (`metformin` &harr; `ميتفورمين` &harr; `biguanides`, `alcohol` &harr; `كحول`, `salbutamol` &harr; `saba` &harr; `ventolin`).
   * Merges dense semantic similarity ($w=0.65$) and lexical matching ($w=0.35$) via Reciprocal Rank Fusion (RRF, $k=60$). Chunks are indexed directly from ChromaDB in milliseconds.

4. **Transparent Dual-Gate Retrieval Benchmark (`evaluation/results/phase2_retrieval_results.json`):**
   * Evaluated across **23 labeled test queries** (18 in-scope clinical queries + 5 explicit out-of-scope/unsupported queries).
   * **Document-Level Recall:**
     * **Doc Recall@1**: **`100.0%`** (Hybrid) vs 88.9% (Dense-Only)
     * **Doc Recall@3**: **`100.0%`** (Hybrid) vs 94.4% (Dense-Only)
     * **Doc MRR@5**: **`1.000`** (Hybrid) vs 0.917 (Dense-Only)
   * **Dual-Gate Chunk/Fact Evidence Recall:**
     * Evaluated using transparent proxy criteria requiring BOTH (a) chunk belonging to `expected_doc_ids` AND (b) `target_drug` substring presence AND (c) at least one clinical evidence keyword.
     * **Fact Recall@1**: **`72.2%`** (Hybrid & Dense)
     * **Fact Recall@3**: **`83.3%`** (Hybrid & Dense)
     * **Fact MRR@5**: **`0.778`** (Hybrid) vs 0.768 (Dense)
   * **Retrieval Threshold Evaluation:** The same `min_score=0.50` dense similarity cutoff is applied to all 18 in-scope and five out-of-scope queries. In-scope retention is **100% (18/18)** in this set; out-of-scope rejection is **80% (4/5)**.
     * `RET-OOS-04` mentions "rebo" (Asthma in Franco), matching Asthma in KB-01 with 0.562 score; ungrounded drug rejection for fictitious drug "makin" is appropriately deferred to Phase 3 generation.

---

## 2. Ingestion Breakdown & Corpus Coverage

All 9 starter corpus documents defined in `data/kb_manifest.yaml` were ingested into persistent Chroma storage at `data/chroma`.

| Document ID | Document Title & Scope | Tables Extracted | Total Chunks | Avg Chars / Chunk | Key Clinical Coverage Preserved |
| :--- | :--- | :---: | :---: | :---: | :--- |
| **KB-01** | `Asthma & COPD` | 19 | 57 | 305.2 | SABA/LABA/ICS, Ventolin, Seretide, dosage warnings (Hypokalemia), tremors |
| **KB-02** | `Peptic Ulcer, GERD, Nausea & Vomiting` | 19 | 51 | 237.8 | H. pylori eradication, PPIs, Metronidazole alcohol (48h), Domperidone QT |
| **KB-03** | `Pain, Fever, Headache & Migraine` | 15 | 47 | 282.6 | Paracetamol liver contraindications, NSAIDs, Cataflam, Brufen alternatives, Aspirin |
| **KB-04** | `Pharyngitis & Tonsillitis` | 9 | 24 | 266.6 | Sore throat antipyretics, Paracetamol/Ibuprofen trade names, swallow analgesics |
| **KB-05** | `Pneumonia` | 8 | 26 | 351.2 | CAP/HAP antibiotics, Oseltamivir viral contraindications, CURB-65 guidelines |
| **KB-06** | `Allergic Diseases & Sinusitis` | 16 | 50 | 368.7 | Antihistamines (1st/2nd gen), saline nasal irrigation, facial pressure analgesics |
| **KB-07** | `Antidiabetic Drugs` | 22 | 40 | 339.7 | Biguanides (Metformin eGFR/lactic acidosis), Sulfonylureas, SGLT2i, DPP-4i |
| **KB-08** | `Antihypertensive & Dyslipidemia` | 30 | 64 | 348.8 | ARBs (pregnancy contraindication, renal artery stenosis), ACEi, Statins, Ezetimibe |
| **KB-09** | `Irritable Bowel Syndrome & Arthritis` | 15 | 55 | 300.0 | Antispasmodics (Duspatalin/Mebeverine), DMARDs (Mycophenolate pregnancy harm) |
| **TOTAL** | **Full 9-Document Starter Corpus** | **153** | **414** | **299.8** | **All nine manifest documents parsed and indexed; no semantic coverage audit claimed** |

*Artifact: `evaluation/results/phase2_ingestion_report.json`*

---

## 3. Failure-Safe Transactional Architecture

```
                       [ Ingestion / Rebuild Trigger ]
                                     │
                1. Parse DOCX into DocumentChunks (in-memory)
                                     │
             2. Generate BGE-M3 Dense Embeddings (in-memory)
                                     │
                     ┌───────────────┴───────────────┐
                     ▼                               ▼
             [ Full Rebuild ]              [ Single Doc Update ]
                     │                               │
        Populate Staging Collection          Upsert Chunks & Embeddings
        Verify count == len(chunks)         Prune only obsolete chunk IDs
                     │                               │
             Atomic Swap / Rename                    │
                     │                               │
                     └───────────────┬───────────────┘
                                     ▼
                    [ Live ChromaDB: 414 Chunks ]
                    (Recovery selects complete new or prior collection)
```

### Safety Guarantees & WAL Recovery:
1. **Never Clear Upfront:** The live collection is NEVER wiped or modified before new chunks and embeddings are fully computed and validated in memory.
2. **WAL-Coordinated Rebuild Recovery:** Full rebuilds log intent before each collection rename. Startup recovery examines live/staging/backup collections, handling interruption before or after each rename.
3. **Verify-Then-Prune Document Replacement:** Targeted updates upsert and verify new IDs before deleting obsolete IDs. An interruption after upsert may leave both old and new IDs until the operation is retried; prior evidence remains available.
4. **Pytest Recovery Coverage:** `tests/ingestion_retrieval/test_vector_store_atomicity.py` has 10 passing tests, including pre-operation and post-operation process-restart states. Physical power-loss behavior is not claimed.

---

## 4. Retrieval Evaluation Benchmark Results

Evaluated across **23 test queries** representing public assessment questions, challenge cases, multi-dialect clinical scenarios, and out-of-scope edge cases.

### 4.1 Comparative Summary: Dense-Only vs. Hybrid

| Retrieval Metric | Dense-Only (`BAAI/bge-m3`) | Hybrid (Dense + BM25 + Franco) | Relative Improvement |
| :--- | :---: | :---: | :---: |
| **Document Recall@1** | 88.9% | **100.0%** | **+11.1%** |
| **Document Recall@3** | 94.4% | **100.0%** | **+5.6%** |
| **Document Recall@5** | 94.4% | **100.0%** | **+5.6%** |
| **Document MRR@5** | 0.917 | **1.000** | **+9.1%** |
| **Chunk/Fact Recall@1** | 72.2% | **72.2%** | Parity |
| **Chunk/Fact Recall@3** | 83.3% | **83.3%** | Parity |
| **Chunk/Fact Recall@5** | 83.3% | **83.3%** | Parity |
| **Chunk/Fact MRR@5** | 0.768 | **0.778** | **+1.3%** |
| **In-Scope Retrieval Retention (threshold 0.50)** | **100.0%** | **100.0%** | 18/18 retained |
| **Out-of-Scope Retrieval Rejection (threshold 0.50)** | **80.0%** | **80.0%** | 4/5 empty results |

*Methodology Note:* Fact recall uses the dual-gate proxy (`target_drug` substring AND clinical evidence keyword). Full gold-label passage annotation is scheduled for Phase 6 harness.

---

### 4.2 In-Scope Fact Recall Breakdown by Query Language (Hybrid)

| Language Category | Queries ($N$) | Fact Recall@1 | Fact Recall@3 | Fact MRR@5 | Examples |
| :--- | :---: | :---: | :---: | :---: | :--- |
| **Modern Standard Arabic (`ar`)** | 4 | **100.0%** | **100.0%** | **1.000** | موانع استعمال ARBs، آثار البزموت، موانع الباراسيتامول |
| **Mixed Language (`mixed`)** | 3 | **100.0%** | **100.0%** | **1.000** | Clarithromycin side effects في جرثومة المعدة، Saline irrigation |
| **Egyptian Arabic Dialect (`ar_dialect`)** | 4 | **50.0%** | **100.0%** | **0.750** | بدائل Brufen، ميتفورمين ممنوع امتى، مغص القولون ودوسباتالين |
| **English (`en`)** | 5 | **60.0%** | **60.0%** | **0.600** | Active ingredient in Cataflam, alcohol with Metronidazole |
| **Franco-Arabic (`franco`)** | 2 | **50.0%** | **50.0%** | **0.500** | `3andi 7omo2a... omeprazole`, `soda3 w 2alam shadeed...` |
| **OVERALL (In-Scope)** | **18** | **72.2%** | **83.3%** | **0.778** | **100.0% Document Recall@3, 83.3% Fact Recall@3** |

---

### 4.3 Out-of-Scope & Genuine Abstention Evaluation (Threshold = 0.50)

| Query ID | Domain / Intent | Query Text | Top Score | Retrieval Decision | Layer Responsibility |
| :--- | :--- | :--- | :---: | :---: | :--- |
| `RET-OOS-01` | Malaria Chemotherapy | *What is the recommended dosage of Artemether-Lumefantrine for acute uncomplicated Malaria?* | 0.4781 | 🚫 **Empty List** | Retrieval layer rejection |
| `RET-OOS-02` | Rabies Prophylaxis | *Can I use Rabies post-exposure prophylaxis immunoglobulin for a bat bite?* | 0.4926 | 🚫 **Empty List** | Retrieval layer rejection |
| `RET-OOS-03` | Acute Leukemia Chemotherapy | *ما هي بروتوكولات العلاج الكيماوي لسرطان الدم اللوكيميا الحادة؟* | 0.4458 | 🚫 **Empty List** | Retrieval layer rejection |
| `RET-OOS-04` | Ungrounded Franco Drug | *katably tab makin 100 mg 3ashan el-rebo, da sa7?* | 0.5626 | ⚠️ Chunks (Asthma) | Generator layer ungrounded rejection |
| `RET-OOS-05` | Non-Medical Query | *Can you draft a formal resignation letter to my pharmacy department head?* | 0.4496 | 🚫 **Empty List** | Retrieval layer rejection |

*Result:* 4 out of 5 out-of-scope queries (80.0%) are rejected cleanly at the retrieval boundary with zero chunk leakage. The single query returning chunks (`RET-OOS-04`) matches asthma passages because the user explicitly wrote "rebo" (Asthma in Franco-Arabic); refusing the ungrounded drug "makin" is delegated to the Phase 3 generation/groundedness guard.

---

## 5. Administrative Primitives Verification

Verified on disk:
1. `ChromaStore.delete_document('KB-04')` &rarr; 414 &rarr; 390 chunks.
2. `run_ingestion(target_doc_id='KB-04')` &rarr; parsed & embedded in memory, committed via atomic replacement with post-upsert verification &rarr; 390 &rarr; 414 chunks.
3. `run_ingestion(rebuild=True)` &rarr; populated staging collection, validated count, committed via WAL-tracked atomic swap &rarr; 414 chunks.
4. `pytest tests/ingestion_retrieval/test_vector_store_atomicity.py` &rarr; 10 passed locally in 60.16s.

---

## 6. Exit Gate Checklist for Phase 2

- [x] **Full Rebuild Recovery:** WAL recovery checked against pre-operation and post-operation collection states; 10 local pytest cases pass. Physical power-loss durability is not claimed.
- [x] **Targeted Re-index Safety:** New chunks are verified before obsolete chunks are pruned; a process interruption can leave duplicate generations until an idempotent retry, with old data retained.
- [x] **Full-Corpus Ingestion Report Semantics:** Verified coherent report at `evaluation/results/phase2_ingestion_report.json` (414 chunks across 9 docs).
- [x] **Chunk/Fact-Level Retrieval Evaluation:** 18 in-scope test cases verified using dual-gate criteria (`target_drug` AND clinical evidence); Fact R@1 = 72.2%, Fact R@3 = 83.3%, Doc R@1 = 100.0%, Doc R@3 = 100.0%.
- [x] **Retrieval Threshold:** Same `min_score=0.50` tested on all queries: 100% in-scope retention (18/18) and 80% OOS rejection (4/5) on this limited set.
- [x] **Administrative Re-index / Delete Support:** Fully verified on `KB-04` with atomic counts.

**Phase 2 gate is released for Phase 3.** The retrieval cutoff and recovery evidence are limited to the recorded corpus, hardware, query set, and simulated process interruption. Re-run multilingual evaluation after Adham's Franco normalizer edits.
