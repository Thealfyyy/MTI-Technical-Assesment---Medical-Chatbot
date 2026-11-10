import json

with open("evaluation/results/eval_200_results.json", encoding="utf-8") as f:
    data = json.load(f)

cases = data["cases"]
mismatches = [c for c in cases if not c["status_match"]]

print(f"Total Mismatches: {len(mismatches)} / 200\n")

by_cat = {}
for m in mismatches:
    exp = m["expected_status"]
    by_cat.setdefault(exp, []).append(m)

for cat in ["answered", "out_of_scope", "escalated"]:
    items = by_cat.get(cat, [])
    print(f"==================================================")
    print(f"CATEGORY: {cat.upper()} ({len(items)} mismatches)")
    print(f"==================================================")
    for it in items:
        got = it["got_status"]
        q = it["question"]
        doc = ",".join(it["doc_ids"]) if it["doc_ids"] else "none"
        ans_preview = it["answer"][:60].replace("\n", " ") if it["answer"] else ""
        print(f"[{it['id']}] GOT={got:<12} docs={doc:<10} | Q: {q}")
        if it["got_status"] == "answered":
            print(f"   -> Ans: {ans_preview}")
    print()
