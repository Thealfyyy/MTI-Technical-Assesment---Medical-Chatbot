"""Run the labeled end-to-end evaluation set against a live local API.

Usage: python -m evaluation.run_eval [--base-url http://127.0.0.1:8000]
The runner uses only public/synthetic cases and writes a JSON report under eval_results_dir.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import platform
import sys
import time
import urllib.error
import urllib.request
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from app.core.config import get_settings


def _post_json(url: str, body: dict[str, Any], timeout: float) -> tuple[int, dict[str, Any]]:
    request = urllib.request.Request(
        url, data=json.dumps(body, ensure_ascii=False).encode("utf-8"),
        headers={"Content-Type": "application/json"}, method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            return response.status, json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as error:
        try:
            payload = json.loads(error.read().decode("utf-8"))
        except (json.JSONDecodeError, UnicodeDecodeError):
            payload = {"error": "Non-JSON HTTP error"}
        return error.code, payload


def _get_json(url: str, timeout: float) -> tuple[int, dict[str, Any]]:
    request = urllib.request.Request(url, method="GET")
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            return response.status, json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as error:
        try:
            payload = json.loads(error.read().decode("utf-8"))
        except (json.JSONDecodeError, UnicodeDecodeError):
            payload = {"error": "Non-JSON HTTP error"}
        return error.code, payload


def _contains_any(text: str, terms: list[str]) -> list[str]:
    normalized = text.casefold()
    return [term for term in terms if term.casefold() in normalized]


def run(base_url: str, cases_path: Path | None = None, timeout: float = 35.0) -> dict[str, Any]:
    settings = get_settings()
    cases_path = cases_path or (settings.project_root / "evaluation" / "cases.jsonl")
    cases = [json.loads(line) for line in cases_path.read_text(encoding="utf-8").splitlines() if line.strip()]
    details: list[dict[str, Any]] = []
    latencies: list[float] = []
    status_counts: Counter[str] = Counter()
    language_groups: dict[str, list[bool]] = defaultdict(list)
    confusion: dict[str, Counter[str]] = defaultdict(Counter)

    for case in cases:
        started = time.perf_counter()
        try:
            http_status, response = _post_json(
                f"{base_url.rstrip('/')}/chat",
                {"session_id": f"eval-{case['case_id']}", "message": case["question"]},
                timeout,
            )
            latency_ms = round((time.perf_counter() - started) * 1000, 2)
        except (TimeoutError, OSError, json.JSONDecodeError) as error:
            http_status, response = 0, {"error": str(error)}
            latency_ms = round((time.perf_counter() - started) * 1000, 2)

        answer = response.get("answer", "") if isinstance(response, dict) else ""
        citations = response.get("citations", []) if isinstance(response, dict) else []
        actual_status = response.get("status", "error") if isinstance(response, dict) else "error"
        actual_language = response.get("language") if isinstance(response, dict) else None
        token_metrics: dict[str, Any] = {}
        if http_status == 200:
            try:
                _, token_metrics = _get_json(
                    f"{base_url.rstrip('/')}/admin/analytics/sessions/eval-{case['case_id']}", timeout
                )
            except (TimeoutError, OSError, json.JSONDecodeError):
                token_metrics = {}
        citation_ids = sorted({c.get("doc_id") for c in citations if isinstance(c, dict) and c.get("doc_id")})
        expected_ids = set(case.get("expected_doc_ids", []))
        supported = case.get("expected_status") != "answered"
        if expected_ids:
            supported = bool(expected_ids.intersection(citation_ids))
        found_facts = _contains_any(answer, case.get("required_facts", []))
        found_forbidden = _contains_any(answer, case.get("forbidden_claims", []))
        status_ok = actual_status == case.get("expected_status")
        language_ok = actual_language == case.get("expected_language")
        citation_shape_ok = http_status == 200 and (
            bool(citations) and all(
                isinstance(c, dict)
                and {"doc_id", "title", "section", "snippet"}.issubset(c)
                and c.get("doc_id") in {f"KB-{n:02d}" for n in range(1, 10)}
                and all(isinstance(c.get(field), str) and c[field].strip() for field in ("title", "section", "snippet"))
                for c in citations
            ) if actual_status == "answered" else citations == []
        )
        case_pass = (
            http_status == 200 and status_ok and language_ok and citation_shape_ok
            and supported and len(found_facts) == len(case.get("required_facts", []))
            and not found_forbidden and latency_ms < 30_000
        )
        status_counts[f"{case.get('expected_status')}->{actual_status}"] += 1
        language_groups[case.get("language_input", "unknown")].append(case_pass)
        confusion[case.get("expected_status", "unknown")][actual_status] += 1
        if latency_ms < 30_000:
            latencies.append(latency_ms)
        details.append({
            "case_id": case.get("case_id"), "category": case.get("category"),
            "http_status": http_status, "expected_status": case.get("expected_status"),
            "actual_status": actual_status, "expected_language": case.get("expected_language"),
            "actual_language": actual_language, "status_match": status_ok,
            "language_match": language_ok, "citation_shape_valid": citation_shape_ok,
            "citation_doc_ids": citation_ids, "expected_doc_hit": supported,
            "expected_doc_ids": sorted(expected_ids),
            "required_facts_found": found_facts, "required_fact_count": len(case.get("required_facts", [])),
            "forbidden_claims_found": found_forbidden, "latency_ms": latency_ms,
            "prompt_tokens": token_metrics.get("prompt_tokens"),
            "completion_tokens": token_metrics.get("completion_tokens"),
            "recorded_total_ms": token_metrics.get("total_ms"),
            "pass": case_pass, "error": response.get("error") if isinstance(response, dict) else None,
        })

    ordered = sorted(latencies)
    def percentile(p: float) -> float | None:
        return round(ordered[min(len(ordered)-1, int(round((p / 100) * (len(ordered)-1))))], 2) if ordered else None

    passed = sum(item["pass"] for item in details)
    doc_scored = [item for item in details if item["expected_status"] == "answered" and item["expected_doc_ids"]]
    case_bytes = cases_path.read_bytes()
    return {
        "schema_version": "1.0", "timestamp": datetime.now(timezone.utc).isoformat(),
        "base_url": base_url, "cases_path": str(cases_path),
        "cases_sha256": hashlib.sha256(case_bytes).hexdigest(), "case_count": len(details),
        "runtime_configuration": {
            "llm_model_name": settings.llm_model_name,
            "embedding_model_name": settings.embedding_model_name,
            "embedding_model_revision": settings.embedding_model_revision or None,
            "embedding_device": settings.embedding_device,
            "retrieval_top_k": settings.retrieval_top_k,
            "retrieval_min_score": settings.retrieval_min_score,
            "llm_max_tokens": settings.llm_max_tokens,
            "llm_temperature": settings.llm_temperature,
            "request_timeout_seconds": settings.request_timeout_seconds,
            "python_version": sys.version,
            "platform": platform.platform(),
        },
        "pass_count": passed, "pass_rate": round(passed / len(details), 4) if details else 0,
        "status_confusion": {expected: dict(actuals) for expected, actuals in confusion.items()},
        "status_transitions": dict(status_counts),
        "by_input_language": {key: {"passed": sum(values), "count": len(values), "pass_rate": round(sum(values)/len(values), 4)} for key, values in language_groups.items()},
        "citation_validity_rate": round(sum(d["citation_shape_valid"] for d in details) / len(details), 4) if details else 0,
        "expected_document_hit_rate": round(sum(d["expected_doc_hit"] for d in doc_scored) / len(doc_scored), 4) if doc_scored else None,
        "document_hit_case_count": len(doc_scored),
        "required_fact_recall_proxy": round(
            sum(len(d["required_facts_found"]) for d in details) / max(1, sum(d["required_fact_count"] for d in details)), 4
        ),
        "forbidden_claim_case_count": sum(bool(d["forbidden_claims_found"]) for d in details),
        "latency_ms": {"p50": percentile(50), "p95": percentile(95), "max": max(ordered) if ordered else None,
                       "under_30s_count": len(ordered), "over_or_equal_30s_count": len(details)-len(ordered)},
        "limitations": ["required-fact and forbidden-claim matching are case-insensitive substring proxies, not semantic or human-annotated claim verification",
                        "run on synthetic/public evaluation cases only; confirm facts manually before release"],
        "cases": details,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Evaluate the live chatbot against public/synthetic labeled cases.")
    parser.add_argument("--base-url", default=f"http://127.0.0.1:{get_settings().app_port}")
    parser.add_argument("--cases", type=Path, default=None)
    parser.add_argument("--timeout", type=float, default=35.0)
    args = parser.parse_args()
    report = run(args.base_url, args.cases, args.timeout)
    output_dir = get_settings().eval_results_dir
    output_dir.mkdir(parents=True, exist_ok=True)
    output_path = output_dir / "end_to_end_eval.json"
    output_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({key: report[key] for key in ("case_count", "pass_count", "pass_rate", "status_confusion", "latency_ms")}, ensure_ascii=False, indent=2))
    print(f"Full report: {output_path}")


if __name__ == "__main__":
    main()
