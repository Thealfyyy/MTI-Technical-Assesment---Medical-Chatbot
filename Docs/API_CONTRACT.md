# API Contract Specification

This document mirrors the exact API contract defined in the MTI AI Solutions Technical Assessment Brief (§04) and `project-continuity-skill/BRIEF.md` (§5), including all core and stretch endpoints.

---

## 1. Core Endpoints

### 1.1 `POST /chat`

Processes clinical medication questions against the 9 approved formulary documents.

#### Request Payload (`application/json`)

```json
{
  "session_id": "abc123",
  "message": "ايه المادة الفعالة في Controloc؟"
}
```

* `session_id` (*optional string*): Unique session tracking identifier. Auto-generated if omitted.
* `message` (*required string*): User's clinical query in English, Modern Standard Arabic, Egyptian Colloquial Arabic, Franco-Arabic, or mixed script.

#### Response Payload (`HTTP 200 OK`)

```json
{
  "answer": "الدواء Controloc يحتوي على Pantoprazole، ويُستخدم لعلاج قرحة المعدة والحموضة (GERD) وعلاج H. pylori.",
  "citations": [
    {
      "doc_id": "KB-02",
      "title": "1. أدوية قرحة المعدة والحموضة – Peptic Ulcer & GERD / 2. Nausea & Vomiting – الغثيان والقيء",
      "section": "1. Proton Pump Inhibitors (PPIs) > Trade Names & Formulations",
      "snippet": "الاسم التجاري في مصر: Controloc | Active ingredient: Pantoprazole"
    }
  ],
  "status": "answered",
  "language": "ar"
}
```

#### Contractual Invariants
* `status` (*string*): Exactly one of `"answered"`, `"out_of_scope"`, or `"escalated"`.
* `citations` (*array of objects*):
  * When `status == "answered"`: Non-empty array containing at least one valid citation from `KB-01` through `KB-09`.
  * When `status == "out_of_scope"` or `"escalated"`: Exactly empty array `[]`.
* `language` (*string*): `"ar"`, `"en"`, or `"mixed"`.
* **Execution SLA:** Must complete and respond within **30.0 seconds**.
* **Failure Mode:** On internal exception or timeout, returns `HTTP 500` with `{"error": "Request timed out"}` or `{"error": "Internal server error"}`.

---

### 1.2 `GET /health`

Verifies backend service and model readiness.

#### Response Payload (`HTTP 200 OK`)

```json
{
  "status": "ok",
  "llm": "Qwen3-8B-Q4_K_M",
  "embedding": "BAAI/bge-m3"
}
```

* Returns `HTTP 503 Service Unavailable` if the local LLM server or embedding engine is offline.

---

## 2. Stretch Administrative & Management Endpoints

All `/admin/*` endpoints require administrative authentication via header `X-Admin-Token: <token>` or HTTP Basic Auth (`admin:<password>`).

### 2.1 `GET /admin/documents`
Lists all knowledge base documents, active chunk counts, and operational status.

```json
[
  {
    "doc_id": "KB-01",
    "title": "1. أدوية الربو – Asthma / 2. أدوية الانسداد الرئوي المزمن – COPD",
    "category": "Respiratory",
    "chunks_count": 57,
    "status": "active"
  }
]
```

### 2.2 `POST /admin/documents` (`multipart/form-data`)
Uploads a brand new document or replaces an existing document with real-time BGE-M3 re-embedding and BM25 index refresh.

* Form Fields:
  * `doc_id` (*required string*): Target identifier (e.g., `KB-06`, or new ID like `KB-10`).
  * `title` (*optional string*): Document title (for new documents).
  * `category` (*optional string*): Therapeutic category (for new documents).
  * `file` (*required .docx file*): Word document up to 15 MiB.

### 2.3 `DELETE /admin/documents/{doc_id}`
Removes a document from the active Chroma vector store and BM25 index without requiring code changes.

### 2.4 `GET /admin/analytics`
Exposes live operational metrics aggregated from SQLite:
* `conversation_volume`: Total sessions recorded.
* `unanswered_count`: Number of `out_of_scope` and `escalated` queries.
* `total_prompt_tokens`: Cumulative prompt tokens.
* `total_completion_tokens`: Cumulative generated tokens.
* `latency_p50_ms`, `latency_p95_ms`, `latency_max_ms`: Percentile latency figures.
* `top_questions`: Most frequent clinical inquiries.

### 2.5 Escalation Handoff Queue
* `POST /handoff`: Patient submits contact info (`name`, `contact`, `summary`) following an escalation.
* `GET /admin/handoffs`: Returns all captured escalation handoffs with status (`pending` / `handled`).
* `PATCH /admin/handoffs/{id}`: Toggles handoff status between `handled` and `pending`.
* `DELETE /admin/handoffs/{id}`: Deletes a resolved handoff record.
