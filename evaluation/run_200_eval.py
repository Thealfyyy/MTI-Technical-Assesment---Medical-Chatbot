"""Runner to test the entire 200-question benchmark set against the live API.
Logs progress, measures latency, checks status matching, citations, and language.
Saves full per-question results to evaluation/results/eval_200_results.json.
DO NOT STOP OR INTERRUPT UNTIL ALL 200 QUESTIONS ARE TESTED.
"""

import json
import sys
import time
import urllib.request
import urllib.error
from pathlib import Path

# Fix terminal encoding for Arabic console logs
sys.stdout.reconfigure(encoding="utf-8")

cases_file = Path("evaluation/test_200_cases.json")
if not cases_file.is_file():
    print("Error: evaluation/test_200_cases.json not found!")
    sys.exit(1)

cases = json.loads(cases_file.read_text(encoding="utf-8"))
print(f"Loaded {len(cases)} test cases from {cases_file}.")

url = "http://127.0.0.1:8000/chat"
results = []
correct_status_count = 0
correct_by_category = {"answered": 0, "out_of_scope": 0, "escalated": 0}
total_by_category = {"answered": 0, "out_of_scope": 0, "escalated": 0}

print("Starting execution of 200 test questions against http://127.0.0.1:8000/chat ...\n")
started_all = time.perf_counter()

for idx, case in enumerate(cases, 1):
    cid = case["id"]
    q = case["q"]
    exp = case["exp"]
    total_by_category[exp] += 1

    payload = json.dumps({"session_id": f"eval-200-{cid}", "message": q}).encode("utf-8")
    req = urllib.request.Request(url, data=payload, headers={"Content-Type": "application/json"})

    t0 = time.perf_counter()
    try:
        with urllib.request.urlopen(req, timeout=35.0) as resp:
            elapsed_ms = round((time.perf_counter() - t0) * 1000, 1)
            data = json.loads(resp.read().decode("utf-8"))
            got_status = data.get("status", "unknown")
            answer = data.get("answer", "")
            citations = data.get("citations", [])
            lang = data.get("language", "unknown")
            error = None
    except Exception as e:
        elapsed_ms = round((time.perf_counter() - t0) * 1000, 1)
        got_status = "error"
        answer = ""
        citations = []
        lang = "unknown"
        error = str(e)

    status_match = (got_status == exp)
    if status_match:
        correct_status_count += 1
        correct_by_category[exp] += 1

    doc_ids = [c.get("doc_id") for c in citations if isinstance(c, dict) and "doc_id" in c]

    record = {
        "id": cid,
        "question": q,
        "expected_status": exp,
        "got_status": got_status,
        "status_match": status_match,
        "latency_ms": elapsed_ms,
        "language": lang,
        "citations": citations,
        "doc_ids": doc_ids,
        "answer": answer,
        "error": error,
    }
    results.append(record)

    # Progress log
    mark = "OK " if status_match else "MIS"
    q_preview = q if len(q) <= 45 else q[:42] + "..."
    print(f"[{idx:03d}/200] {cid} {mark} exp={exp:<12} got={got_status:<12} {elapsed_ms:>6.1f}ms docs={','.join(doc_ids[:2])} | {q_preview}")

total_elapsed = round(time.perf_counter() - started_all, 1)
print("\n" + "="*70)
print(f"COMPLETED 200/200 QUESTIONS in {total_elapsed}s.")
print(f"Overall Status Accuracy: {correct_status_count}/200 ({correct_status_count/200*100:.1f}%)")
for cat, count in total_by_category.items():
    corr = correct_by_category[cat]
    pct = (corr / count * 100) if count else 0
    print(f"  - {cat:<14}: {corr}/{count} ({pct:.1f}%)")
print("="*70)

# Output filename from command-line argument if provided
model_tag = sys.argv[1] if len(sys.argv) > 1 else "eval_200_results"
out_res_path = Path(f"evaluation/results/{model_tag}.json")
out_res_path.parent.mkdir(parents=True, exist_ok=True)
summary_data = {
    "model_tag": model_tag,
    "total_questions": len(cases),
    "correct_status_count": correct_status_count,
    "accuracy": correct_status_count / len(cases),
    "total_elapsed_seconds": total_elapsed,
    "average_latency_ms": round(total_elapsed * 1000 / len(cases), 1),
    "by_category": {
        cat: {
            "total": total_by_category[cat],
            "correct": correct_by_category[cat],
            "accuracy": correct_by_category[cat] / total_by_category[cat],
        }
        for cat in total_by_category
    },
    "cases": results,
}
out_res_path.write_text(json.dumps(summary_data, ensure_ascii=False, indent=2), encoding="utf-8")
print(f"Full results saved to {out_res_path}")
