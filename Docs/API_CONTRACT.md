# API Contract Specification

This document mirrors the exact API contract defined in the MTI AI Solutions Technical Assessment Brief (§04) and `project-continuity-skill/BRIEF.md` (§5).

## 1. `POST /chat`

### Request Payload (`application/json`)

```json
{
  "session_id": "abc123",
  "message": "ايه المادة الفعالة في Controloc؟"
}
```

- `session_id` (optional `string`): Missing or null starts a new session.
- `message` (required `string`): Plain text question in Arabic, Egyptian dialect, Franco-Arabic, English, or mixed language.

### Response Payload (`HTTP 200 OK`)

```json
{
  "answer": "...",
  "citations": [
    {
      "doc_id": "KB-02",
      "title": "1. أدوية قرحة المعدة والحموضة – Peptic Ulcer & GERD",
      "section": "1. Proton Pump Inhibitors (PPIs)",
      "snippet": "Controloc – Pantoprazole"
    }
  ],
  "status": "answered",
  "language": "ar"
}
```

- `status`: Exactly one of `"answered"`, `"out_of_scope"`, or `"escalated"`.
- `citations`: Non-empty list of starter-corpus citations when `status == "answered"`; empty list `[]` when `status` is `"out_of_scope"` or `"escalated"`.
- `doc_id`: Must be one of `KB-01` through `KB-09`.
- `language`: `"ar"`, `"en"`, or `"mixed"`.
- **Answer policy**: `answer` is composed prose in the question's language (Arabic for Arabic, Egyptian-dialect, or Franco-Arabic input; English for English; Arabic with English medical terms for mixed). The model must also return one to three verbatim evidence quotes; each quote is checked against the chunk it names and discarded if it does not match, so `answered` always has at least one verified span. A deterministic post-check rejects the composed text if it mentions a number or a drug/proper name absent from the cited passages, in which case the verified quotes are returned instead. This is a provenance check, not semantic entailment; answer accuracy and Arabic/Franco wording quality still require the manual review run.
- The model may also escalate patient-specific advice that the deterministic pattern guard does not match (for example "what should I give him?"). Those responses are `escalated` with `citations: []`.
- **Timeout & Error Contract**: Must respond within 30 seconds. On unhandled error or timeout, return `HTTP 500` with `{"error": "..."}`.

## 2. `GET /health`

Returns `HTTP 200 OK`:

```json
{
  "status": "ok",
  "llm": "<loaded_llm_model_name>",
  "embedding": "<loaded_embedding_model_name>"
}
```

The current readiness implementation returns HTTP 503 while the configured local LLM server is unavailable. On success, model labels come from app configuration; the endpoint verifies server health but does not independently inspect the server's loaded model artifact.

## 3. Stretch Administrative & Escalation Endpoints

- `POST /admin/documents` — Upload or replace a knowledge base document and re-index it.
- `DELETE /admin/documents/{doc_id}` — Remove a document and its indexed chunks.
- `GET /admin/analytics` — Retrieve conversation volume, top questions, unanswered questions, token usage, and latency metrics.
- `POST /handoff` — Capture short summary and synthetic contact details following an `escalated` response.

### Demo implementation details

- Document routes accept only `.docx`, at most 15 MiB, and IDs already present in the fixed `KB-01`…`KB-09` manifest. Chroma replacement verifies new chunks before pruning old ones. The vector index and source file are separate stores, so a process crash between their commits can leave them temporarily inconsistent; rerun the upload or rebuild after reviewing the logs. Full rebuilds use committed override files. Deletion is recorded in `data/uploads/deleted_documents.json` so full rebuilds retain it; uploading that ID restores it. A crash between writing this tombstone and deleting Chroma records can temporarily leave deleted passages searchable until the delete is retried.
- Analytics are operational counters from SQLite chat records. `top_questions` groups exact question strings; token counts are those returned by the local LLM API and can be null when generation was skipped. Latency is wall-clock stage timing recorded by the application. Percentiles use nearest-rank-like discrete selection over recorded rows, not a streaming estimator.
- `GET /admin/analytics/sessions/{session_id}` returns stage latencies, status, model, and runtime token counters for one session without returning its question text; the evaluation runner uses this to associate per-case usage.
- The admin routes have no authentication in this assessment build. Keep the API bound to loopback (`APP_HOST=127.0.0.1`) and use synthetic/public evaluation prompts only. They are not safe to expose to a network.
