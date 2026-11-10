# Clinical Safety, Negative Evidence Boundaries & Data Privacy

> **Assessment Requirement:** Documentation of safety policies, negative evidence constraints, emergency triaging, citation grounding, and data protection rules.

---

## 1. Clinical Evidence Boundary: Approved Formulary Only

The core requirement of the assessment is strict boundary enforcement: **the chatbot must answer only from the 9 approved clinical knowledge base documents (`KB-01` through `KB-09`)**. It is strictly forbidden from diagnosing, suggesting unsupported treatments, or hallucinating drug facts from parametric pre-training weights.

### Response Status Definitions

Every response from `POST /chat` adheres strictly to one of three statuses:

1. **`answered`**:
   * Returned **only** when explicit, verifiable facts exist in the retrieved approved document chunks.
   * **Mandatory Citation Rule:** Must contain at least one valid citation from `KB-01`..`KB-09` with exact `doc_id`, `title`, `section`, and a verbatim evidence `snippet`.
2. **`out_of_scope`**:
   * Returned when the question asks about medications absent from the formulary (e.g. Lipitor, Viagra, Ozempic, Aspirin), asks for medical disease diagnosis based on symptoms, or general medical knowledge not documented in the formulary.
   * **Mandatory Citation Rule:** Must return `citations: []` (empty list). Never fabricates citations.
   * Standard safe abstention message:
     * English: *"I could not find enough supporting information in the approved sources to answer this question."*
     * Arabic: *"لا أجد في المصادر المعتمدة معلومات كافية للإجابة عن هذا السؤال."*
3. **`escalated`**:
   * Returned for any acute medical emergencies, red-flag symptoms, toxic ingestion, overdose, severe pediatric fever, or personalized patient dosing requests.
   * **Mandatory Citation Rule:** Must return `citations: []` (empty list).
   * Standard safe escalation directive:
     * English: *"This may require urgent professional assessment. Please contact local emergency services or a qualified clinician now."*
     * Arabic: *"قد تتطلب الحالة تقييماً عاجلاً من مختص. يُرجى التواصل مع خدمات الطوارئ المحلية أو مختص صحي فوراً."*

---

## 2. Two-Tier Safety Architecture

```
User Message
    │
    ▼
[ Tier 1: Deterministic Regex Fast-Path ]
    ├── Acute Emergency Detected? ───────────────► ESCALATE (< 1 ms, 0 tokens)
    ├── Personal Dose Calculation? ──────────────► ESCALATE (< 1 ms, 0 tokens)
    └── Diagnostic Symptoms / Off-Corpus Drug? ──► OUT OF SCOPE (< 1 ms, 0 tokens)
    │
    ▼ (Passes Safety Pre-Checks)
[ Hybrid Retrieval: Dense BGE-M3 + BM25 ]
    └── No relevant chunks retrieved? ───────────► OUT OF SCOPE (~50 ms, 0 tokens)
    │
    ▼ (Top-3 Chunks Retrieved)
[ Qwen3-8B Grounded Generation (JSON Schema) ]
    │
    ▼
[ Tier 2: Post-Generation Verbatim Validator ]
    ├── Verbatim Substring Matching Failed? ─────► FALLBACK TO VERBATIM EVIDENCE
    ├── Unsupported Drug Names / Dosages? ───────► OUT OF SCOPE (Zero Hallucination)
    └── Fully Grounded & Entailed ───────────────► ANSWERED (With Verified Citations)
```

### 2.1 Tier 1: Deterministic Pre-Retrieval Guards
Implemented in `app/safety/guards.py`. Before invoking the vector store or neural model, deterministic regex patterns scan the query for high-risk clinical triggers:
* **Acute Emergencies (`is_emergency`):** Chest pain radiating to arm/jaw, acute dyspnea / cyanosis, anaphylaxis / angioedema, suspected stroke / FAST symptoms, severe infant fever (>40°C in <3 months), testicular torsion, extensive blistering rash (Stevens-Johnson syndrome), active GI hemorrhage (hematemesis/melena), intentional self-harm or overdose.
* **Personalized Dosing (`is_personal_dose`):** Inquiries asking *"How many pills should my 5-year-old take?"* or *"What dose should I give my grandmother with kidney failure?"* require professional assessment and cannot be calculated autonomously.
* **Performance:** Executes in **0.1–0.3 ms** without loading embedding models or invoking the LLM.

### 2.2 Tier 2: Verbatim Substring Grounding & Anti-Hallucination
Implemented in `app/generation/grounding.py`. Unlike traditional RAG systems that trust the LLM's summary:
* The LLM is instructed via grammar-constrained JSON schema to provide both its answer and an `evidence` array containing exact verbatim quotes from the chunks.
* **Substring Check:** Every quote is verified using exact case-insensitive substring matching against the source text of the cited `chunk_id`.
* **Entity & Number Audit:** A deterministic post-processor extracts all drug names, numbers, percentages, and units from the generated text and verifies that each appears in the cited chunk text. If an entity is not grounded in the source chunk, the generated answer is discarded and replaced with the verbatim evidence sentences.

---

## 3. Human-in-the-Loop & Escalation Handoff

When an acute query is escalated, the application provides an optional **Escalation Handoff** capture modal in the UI (`app/static/index.html`):
* **Non-Advisory Handoff:** Collects patient name, contact phone/email, and query summary.
* **Clear Disclaimer:** The UI prominently notifies the user: *"This assessment demo is not an emergency service. For immediate emergencies, call local emergency services immediately."*
* **Triage Review Lifecycle in Admin Dashboard (`/admin`):**
  * Submissions are stored in SQLite `handoffs` table with initial state `pending`.
  * Pharmacy operators can inspect the clinical summary, review the contact, and transition the status to `handled` or delete the record after resolution.

---

## 4. Data Privacy, Sovereignty & HIPAA Alignment

* **Zero Real Patient Data:** The application was developed, evaluated, and benchmarked exclusively using synthetic, simulated medical inquiries. No protected health information (PHI) or real patient records exist in the repository or database.
* **100% Local Inference & Loopback Isolation:** By hosting `llama-server.exe` and `bge-m3` locally on loopback (`127.0.0.1`), zero prompts, medical questions, or session data are ever transmitted to third-party cloud APIs (such as OpenAI, Anthropic, or external telemetry).
* **Sanitized Operational Telemetry:** SQLite logging (`conversations` table) records anonymized question text, status, token counts, and latency for quality monitoring. No IP addresses or browser fingerprints are tracked.
* **Secure Admin Access:** The `/admin` portal and document endpoints are secured with mandatory token-based authentication (`X-Admin-Token` / HTTP Basic Auth).
