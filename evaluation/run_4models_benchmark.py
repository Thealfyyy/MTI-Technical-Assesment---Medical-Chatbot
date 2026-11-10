"""Orchestrates end-to-end 200-question evaluation across all 4 candidate LLMs on RTX 3090 Vulkan.

Candidates:
1. Qwen3-8B-Q4_K_M
2. Qwen3-4B-Instruct-2507-Q4_K_M
3. gemma-4-E4B-it-Q4_0
4. medgemma-4b-it-Q4_K_M

For each model:
- Boots llama-server with Vulkan offload
- Awaits healthy readiness
- Runs the 200 questions through http://127.0.0.1:8000/chat
- Records per-case metrics, accuracy, latency
- Restores Qwen3-8B at the end
- Outputs consolidated Markdown/JSON comparison report
"""

import json
import os
import subprocess
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

# Force UTF-8 stdout
sys.stdout.reconfigure(encoding="utf-8")

PROJECT_ROOT = Path(__file__).resolve().parents[1]
LLAMA_SERVER_EXE = PROJECT_ROOT / ".cache" / "tools" / "llama-b12110-vulkan" / "llama-server.exe"
MODELS_DIR = PROJECT_ROOT / ".cache" / "models"
RESULTS_DIR = PROJECT_ROOT / "evaluation" / "results"
RESULTS_DIR.mkdir(parents=True, exist_ok=True)

MODELS = [
    {
        "name": "Qwen3-8B-Q4_K_M",
        "tag": "eval_200_qwen3_8b",
        "file": MODELS_DIR / "Qwen3-8B-Q4_K_M.gguf",
        "params": "-c 4096 -t 16 -tb 24 -ngl 99 --temp 0.0 --reasoning-budget 0",
    },
    {
        "name": "Qwen3-4B-Instruct-2507-Q4_K_M",
        "tag": "eval_200_qwen3_4b",
        "file": MODELS_DIR / "Qwen3-4B-Instruct-2507-Q4_K_M.gguf",
        "params": "-c 4096 -t 16 -tb 24 -ngl 99 --temp 0.0 --reasoning-budget 0",
    },
    {
        "name": "gemma-4-E4B-it-Q4_0",
        "tag": "eval_200_gemma4_e4b",
        "file": MODELS_DIR / "gemma-4-E4B-it-Q4_0.gguf",
        "params": "-c 4096 -t 16 -tb 24 -ngl 99 --temp 0.0 --reasoning-budget 0",
    },
    {
        "name": "medgemma-4b-it-Q4_K_M",
        "tag": "eval_200_medgemma_4b",
        "file": MODELS_DIR / "medgemma-4b-it-Q4_K_M.gguf",
        "params": "-c 4096 -t 16 -tb 24 -ngl 99 --temp 0.0 --reasoning-budget 0",
    },
]


def kill_process_on_port(port: int = 8080) -> None:
    """Kill any process currently holding port 8080."""
    try:
        cmd = f"Get-NetTCPConnection -LocalPort {port} -ErrorAction SilentlyContinue | Select-Object -ExpandProperty OwningProcess -Unique"
        res = subprocess.run(["powershell", "-NoProfile", "-Command", cmd], capture_output=True, text=True)
        pids = [line.strip() for line in res.stdout.strip().splitlines() if line.strip().isdigit() and line.strip() != "0"]
        for pid in pids:
            print(f"[Model Orchestrator] Killing process {pid} on port {port}...")
            subprocess.run(["powershell", "-NoProfile", "-Command", f"Stop-Process -Id {pid} -Force -ErrorAction SilentlyContinue"])
        time.sleep(1.5)
    except Exception as e:
        print(f"[Model Orchestrator] Port cleanup warning: {e}")


def wait_for_health(url: str, timeout_sec: int = 60) -> bool:
    """Poll URL until HTTP 200 or timeout."""
    t0 = time.perf_counter()
    while time.perf_counter() - t0 < timeout_sec:
        try:
            req = urllib.request.Request(url)
            with urllib.request.urlopen(req, timeout=2.0) as resp:
                if resp.status == 200:
                    return True
        except Exception:
            pass
        time.sleep(1.0)
    return False


def get_current_model_name() -> str:
    """Check what model is currently reported by llama-server."""
    try:
        req = urllib.request.Request("http://127.0.0.1:8080/v1/models")
        with urllib.request.urlopen(req, timeout=2.0) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            if "data" in data and len(data["data"]) > 0:
                return data["data"][0].get("id", "")
    except Exception:
        pass
    return ""


def start_llama_server(model_path: Path, params: str) -> subprocess.Popen:
    """Launch llama-server in background."""
    kill_process_on_port(8080)
    cmd = f'"{LLAMA_SERVER_EXE}" -m "{model_path}" --host 127.0.0.1 --port 8080 {params}'
    print(f"[Model Orchestrator] Starting: {cmd}")
    proc = subprocess.Popen(
        cmd,
        shell=True,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        creationflags=subprocess.CREATE_NEW_PROCESS_GROUP if os.name == "nt" else 0,
    )
    ready = wait_for_health("http://127.0.0.1:8080/health", timeout_sec=90)
    if not ready:
        raise RuntimeError(f"llama-server failed to become ready for {model_path.name}")
    print(f"[Model Orchestrator] Model {model_path.name} is ready on 8080!")
    return proc


def main():
    print("=" * 80)
    print("STARTING 4-MODEL 200-QUESTION COMPARATIVE BENCHMARK")
    print("=" * 80)

    comparison_results = []

    for idx, model_cfg in enumerate(MODELS, 1):
        m_name = model_cfg["name"]
        m_tag = model_cfg["tag"]
        m_file = model_cfg["file"]
        m_params = model_cfg["params"]

        print(f"\n\n{'#'*80}")
        print(f"[{idx}/4] PREPARING MODEL: {m_name}")
        print(f"File: {m_file.name} ({m_file.stat().st_size / (1024**3):.2f} GiB)")
        print(f"{'#'*80}\n")

        # Check if already running
        current_loaded = get_current_model_name()
        if m_file.stem in current_loaded or current_loaded.endswith(m_file.name):
            print(f"[Model Orchestrator] Model {m_name} is already loaded on 8080.")
        else:
            start_llama_server(m_file, m_params)

        # Warmup FastAPI
        wait_for_health("http://127.0.0.1:8000/health", timeout_sec=30)
        time.sleep(2)

        # Run 200-question suite
        print(f"[Model Orchestrator] Running 200-question suite for {m_name}...")
        python_exe = sys.executable
        runner_script = PROJECT_ROOT / "evaluation" / "run_200_eval.py"
        run_res = subprocess.run([python_exe, str(runner_script), m_tag], cwd=str(PROJECT_ROOT))
        if run_res.returncode != 0:
            print(f"[Model Orchestrator] WARNING: evaluation runner exited with code {run_res.returncode}")

        # Read output JSON
        res_file = RESULTS_DIR / f"{m_tag}.json"
        if res_file.is_file():
            data = json.loads(res_file.read_text(encoding="utf-8"))
            comparison_results.append({
                "model_name": m_name,
                "model_file": m_file.name,
                "total_questions": data.get("total_questions", 200),
                "correct_status_count": data.get("correct_status_count", 0),
                "accuracy": round(data.get("accuracy", 0.0) * 100, 2),
                "total_elapsed_seconds": data.get("total_elapsed_seconds", 0.0),
                "average_latency_ms": data.get("average_latency_ms", 0.0),
                "by_category": data.get("by_category", {}),
            })
        else:
            print(f"[Model Orchestrator] ERROR: Result file not found at {res_file}")

    # Restore default Qwen3-8B
    print("\n\n" + "=" * 80)
    print("RESTORING PRODUCTION DEFAULT MODEL: Qwen3-8B-Q4_K_M")
    print("=" * 80)
    start_llama_server(MODELS[0]["file"], MODELS[0]["params"])

    # Write consolidation comparison file
    summary_path = RESULTS_DIR / "comparison_4_models_200q.json"
    summary_path.write_text(json.dumps(comparison_results, ensure_ascii=False, indent=2), encoding="utf-8")

    # Print summary table
    print("\n\n" + "=" * 80)
    print("FINAL 4-MODEL 200-QUESTION BENCHMARK COMPARISON TABLE")
    print("=" * 80)
    header = f"{'Model Name':<28} | {'Accuracy':<10} | {'Answered (100)':<15} | {'Out of Scope (50)':<18} | {'Escalated (50)':<15} | {'Avg Latency':<12} | {'Total Time':<10}"
    print(header)
    print("-" * len(header))
    for r in comparison_results:
        cats = r.get("by_category", {})
        ans = cats.get("answered", {})
        oos = cats.get("out_of_scope", {})
        esc = cats.get("escalated", {})

        ans_str = f"{ans.get('correct', 0)}/100 ({ans.get('accuracy', 0)*100:.1f}%)"
        oos_str = f"{oos.get('correct', 0)}/50 ({oos.get('accuracy', 0)*100:.1f}%)"
        esc_str = f"{esc.get('correct', 0)}/50 ({esc.get('accuracy', 0)*100:.1f}%)"
        print(f"{r['model_name']:<28} | {r['accuracy']:>6.1f}%    | {ans_str:<15} | {oos_str:<18} | {esc_str:<15} | {r['average_latency_ms']:>8.1f} ms | {r['total_elapsed_seconds']:>8.1f} s")
    print("=" * len(header))
    print(f"\nSaved consolidated comparison report to {summary_path}")


if __name__ == "__main__":
    main()
