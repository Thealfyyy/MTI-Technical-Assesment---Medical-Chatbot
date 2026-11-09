"""Phase 1 Candidate Embedding & LLM Benchmark Harness.

This standalone benchmark script evaluates:
1. Embedding candidates (`sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2` and `BAAI/bge-m3`)
   on all 9 DOCX starter corpus files across the 16 labeled test cases in `evaluation/cases.jsonl`,
   measuring load time, peak memory delta, query latency, Recall@1, Recall@3, and MRR.
2. Open-weights LLM candidates (`Qwen3-4B-Instruct-2507` Q4_K_M, `gemma-4-E4B-it` Q4_0,
   `Qwen3-8B` Q4_K_M, and gated `medgemma-4b-it`) via `llama-server` on the frozen retrieved context,
   recording load time, RAM usage, prompt/completion tokens, token generation speed, end-to-end latency,
   >30-second timeout failures, status classification accuracy, citation validity, and safety violations.

All model weights and caches are strictly stored under `<PROJECT_ROOT>/.cache/`.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import subprocess
import sys
import time
import urllib.request
import xml.etree.ElementTree as ET
import zipfile
from pathlib import Path
from typing import Any

import psutil
import yaml

PROJECT_ROOT = Path(__file__).resolve().parents[1]
CACHE_ROOT = PROJECT_ROOT / ".cache"
HF_CACHE = CACHE_ROOT / "huggingface"
ST_CACHE = CACHE_ROOT / "sentence_transformers"
MODELS_DIR = CACHE_ROOT / "models"
TMP_DIR = CACHE_ROOT / "tmp"

for d in (CACHE_ROOT, HF_CACHE, ST_CACHE, MODELS_DIR, TMP_DIR):
    d.mkdir(parents=True, exist_ok=True)

os.environ["HF_HOME"] = str(HF_CACHE)
os.environ["SENTENCE_TRANSFORMERS_HOME"] = str(ST_CACHE)
os.environ["TMPDIR"] = str(TMP_DIR)
os.environ["TEMP"] = str(TMP_DIR)
os.environ["TMP"] = str(TMP_DIR)
os.environ["HF_HUB_OFFLINE"] = "1"
os.environ["TRANSFORMERS_OFFLINE"] = "1"


#Major section header pattern for documents that use Normal style (e.g. KB-03 part 1, KB-09)
NUMBERED_HEADER_RE = re.compile(r"^(\d+\.\s+.+|[A-Z]\.\s+.+|أولًا:.+|ثانيًا:.+|ملخص OTC.+|OTC.+)$")


def parse_docx_into_chunks(docx_path: Path, doc_id: str, doc_title: str) -> list[dict[str, Any]]:
    """Parse a DOCX file into deterministic section-aware chunks for Phase 1 benchmarking."""
    with zipfile.ZipFile(docx_path) as z:
        xml_bytes = z.read("word/document.xml")
    root = ET.fromstring(xml_bytes)
    ns = {"w": "http://schemas.openxmlformats.org/wordprocessingml/2006/main"}

    paragraphs: list[tuple[str, str]] = []
    for para in root.findall(".//w:p", ns):
        p_style = para.find(".//w:pStyle", ns)
        style = (
            p_style.attrib.get("{http://schemas.openxmlformats.org/wordprocessingml/2006/main}val")
            if p_style is not None
            else "Normal"
        )
        texts = [t.text for t in para.findall(".//w:t", ns) if t.text]
        txt = "".join(texts).strip()
        if txt:
            paragraphs.append((style, txt))

    chunks: list[dict[str, Any]] = []
    current_major = doc_title
    current_sub = "General"
    buffer: list[str] = []

    def flush_chunk() -> None:
        nonlocal buffer
        if not buffer:
            return
        text_body = "\n".join(buffer).strip()
        if not text_body:
            buffer = []
            return
        section_label = f"{current_major} > {current_sub}" if current_sub != current_major else current_major
        chunk_idx = len(chunks) + 1
        chunks.append(
            {
                "chunk_id": f"{doc_id}-C{chunk_idx:03d}",
                "doc_id": doc_id,
                "title": doc_title,
                "section": section_label,
                "text": f"[{doc_id}] {doc_title} | {section_label}\n{text_body}",
                "snippet": text_body[:280].replace("\n", " "),
            }
        )
        buffer = []

    for style, txt in paragraphs:
        is_heading_style = "Heading" in style or "Title" in style
        is_numbered_header = bool(NUMBERED_HEADER_RE.match(txt)) and len(txt) < 95
        if is_heading_style or is_numbered_header:
            flush_chunk()
            if any(
                k in txt
                for k in [
                    "أدوية الربو",
                    "أدوية الانسداد",
                    "قرحة المعدة",
                    "Nausea & Vomiting",
                    "Pain & Fever",
                    "Headache & Migraine",
                    "التهاب الحلق",
                    "الالتهاب الرئوي",
                    "أدوية الحساسية",
                    "الجيوب الأنفية",
                    "أدوية السكر",
                    "أدوية الضغط",
                    "الكوليسترول",
                    "القولون العصبي",
                    "التهاب المفاصل",
                ]
            ):
                current_major = txt
                current_sub = txt
            else:
                current_sub = txt
            buffer.append(txt)
        else:
            buffer.append(txt)
            if sum(len(x) for x in buffer) >= 900:
                flush_chunk()

    flush_chunk()
    return chunks


def load_corpus_chunks() -> list[dict[str, Any]]:
    manifest_path = PROJECT_ROOT / "data" / "kb_manifest.yaml"
    with open(manifest_path, "r", encoding="utf-8") as f:
        manifest = yaml.safe_load(f)
    all_chunks: list[dict[str, Any]] = []
    for doc in manifest["documents"]:
        p = PROJECT_ROOT / doc["relative_path"]
        doc_chunks = parse_docx_into_chunks(p, doc["doc_id"], doc["title"])
        all_chunks.extend(doc_chunks)
    return all_chunks


def load_eval_cases() -> list[dict[str, Any]]:
    cases_path = PROJECT_ROOT / "evaluation" / "cases.jsonl"
    cases = []
    with open(cases_path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                cases.append(json.loads(line))
    return cases


SYSTEM_PROMPT = """You are a clinical drug-information assistant for pharmacists and doctors in Egypt.
Answer ONLY from the provided APPROVED EXCERPTS. Return valid JSON matching the schema.
Status rules:
- "escalated" (with citations: []): user asks for patient-specific dosing/mg per day not written in excerpts, child/pediatric dosing, overdose, or describes emergency red-flag symptoms (severe shortness of breath, blue lips/cyanosis, chest pain). Advise immediate medical/pharmacist care without giving dosing or treatment advice.
- "out_of_scope" (with citations: []): question is unrelated to drugs (e.g. cover letter) OR asks about a disease/drug not in the excerpts (e.g. malaria). Never use external medical knowledge.
- "answered": excerpts directly answer the question. Include >=1 citation with exact doc_id (KB-01..KB-09), title, section, and a short verbatim snippet from the excerpt.
Language rules: reply in Arabic ("ar") for Arabic/Franco-Arabic/mixed questions, and English ("en") for English questions."""

RESPONSE_JSON_SCHEMA = {
    "type": "json_schema",
    "json_schema": {
        "name": "chat_response",
        "strict": True,
        "schema": {
            "type": "object",
            "properties": {
                "status": {
                    "type": "string",
                    "enum": ["answered", "out_of_scope", "escalated"],
                },
                "language": {
                    "type": "string",
                    "enum": ["ar", "en", "mixed"],
                },
                "answer": {"type": "string"},
                "citations": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "doc_id": {"type": "string"},
                            "title": {"type": "string"},
                            "section": {"type": "string"},
                            "snippet": {"type": "string"},
                        },
                        "required": ["doc_id", "title", "section", "snippet"],
                        "additionalProperties": False,
                    },
                },
            },
            "required": ["status", "language", "answer", "citations"],
            "additionalProperties": False,
        },
    },
}


def benchmark_embeddings(
    chunks: list[dict[str, Any]], cases: list[dict[str, Any]]
) -> tuple[dict[str, Any], dict[str, list[dict[str, Any]]]]:
    """Benchmark both candidate embedding models on the 9-document corpus and 16 test cases."""
    import numpy as np
    from sentence_transformers import SentenceTransformer

    candidates = [
        {
            "id": "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2",
            "revision": "e8f8c211226b894fcb81acc59f3b34ba3efd5f42",
            "license": "Apache-2.0",
        },
        {
            "id": "BAAI/bge-m3",
            "revision": "5617a9f61b028005a4858fdac845db406aefb181",
            "license": "MIT",
        },
    ]

    results: dict[str, Any] = {}
    retrieved_by_model: dict[str, dict[str, list[dict[str, Any]]]] = {}
    proc = psutil.Process(os.getpid())

    chunk_texts = [c["text"] for c in chunks]

    for cand in candidates:
        model_id = cand["id"]
        print(f"\n[Embedding Benchmark] Loading {model_id} ...", flush=True)
        rss_before = proc.memory_info().rss / (1024**2)
        t0 = time.perf_counter()
        try:
            model = SentenceTransformer(
                model_id,
                device="cpu",
                cache_folder=str(ST_CACHE),
            )
            load_time_s = time.perf_counter() - t0
            rss_after_load = proc.memory_info().rss / (1024**2)

            t_enc = time.perf_counter()
            chunk_embs = model.encode(
                chunk_texts,
                normalize_embeddings=True,
                show_progress_bar=False,
                batch_size=16,
            )
            corpus_encode_s = time.perf_counter() - t_enc
            rss_peak = max(rss_after_load, proc.memory_info().rss / (1024**2))

            query_latencies_ms: list[float] = []
            recall_at_1_hits = 0
            recall_at_3_hits = 0
            mrr_sum = 0.0
            retrieval_cases_count = 0
            per_case_logs: list[dict[str, Any]] = []
            case_top_chunks: dict[str, list[dict[str, Any]]] = {}

            for case in cases:
                q = case["question"]
                tq0 = time.perf_counter()
                q_emb = model.encode([q], normalize_embeddings=True, show_progress_bar=False)[0]
                sims = np.dot(chunk_embs, q_emb)
                top_idx = np.argsort(sims)[::-1][:5]
                q_ms = (time.perf_counter() - tq0) * 1000.0
                query_latencies_ms.append(q_ms)

                top_3_chunks = []
                for idx in top_idx[:3]:
                    c_copy = dict(chunks[int(idx)])
                    c_copy["score"] = round(float(sims[int(idx)]), 4)
                    top_3_chunks.append(c_copy)
                case_top_chunks[case["case_id"]] = top_3_chunks

                top_docs = [chunks[int(i)]["doc_id"] for i in top_idx[:5]]
                expected_docs = case["expected_doc_ids"]
                hit1 = None
                hit3 = None
                rr = None
                if expected_docs:
                    retrieval_cases_count += 1
                    hit1 = 1 if top_docs[0] in expected_docs else 0
                    hit3 = 1 if any(d in expected_docs for d in top_docs[:3]) else 0
                    recall_at_1_hits += hit1
                    recall_at_3_hits += hit3
                    rr = 0.0
                    for rank_idx, d_id in enumerate(top_docs[:5], start=1):
                        if d_id in expected_docs:
                            rr = 1.0 / rank_idx
                            break
                    mrr_sum += rr

                per_case_logs.append(
                    {
                        "case_id": case["case_id"],
                        "language_input": case["language_input"],
                        "expected_doc_ids": expected_docs,
                        "top_3_doc_ids": top_docs[:3],
                        "top_3_sections": [chunks[int(i)]["section"] for i in top_idx[:3]],
                        "top_1_score": round(float(sims[int(top_idx[0])]), 4),
                        "latency_ms": round(q_ms, 2),
                        "hit_at_1": hit1,
                        "hit_at_3": hit3,
                        "reciprocal_rank": round(rr, 4) if rr is not None else None,
                    }
                )

            retrieved_by_model[model_id] = case_top_chunks
            results[model_id] = {
                "status": "completed",
                "revision": cand["revision"],
                "license": cand["license"],
                "max_seq_length": int(getattr(model, "max_seq_length", 0)),
                "embedding_dimension": int(chunk_embs.shape[1]),
                "load_time_s": round(load_time_s, 3),
                "corpus_chunk_count": len(chunks),
                "corpus_encode_time_s": round(corpus_encode_s, 3),
                "rss_before_mb": round(rss_before, 1),
                "rss_peak_mb": round(rss_peak, 1),
                "rss_delta_mb": round(rss_peak - rss_before, 1),
                "query_latency_p50_ms": round(float(np.percentile(query_latencies_ms, 50)), 2),
                "query_latency_p95_ms": round(float(np.percentile(query_latencies_ms, 95)), 2),
                "query_latency_max_ms": round(float(np.max(query_latencies_ms)), 2),
                "labeled_retrieval_cases": retrieval_cases_count,
                "recall_at_1": round(recall_at_1_hits / max(1, retrieval_cases_count), 4),
                "recall_at_3": round(recall_at_3_hits / max(1, retrieval_cases_count), 4),
                "mrr_at_5": round(mrr_sum / max(1, retrieval_cases_count), 4),
                "per_case": per_case_logs,
            }
            print(
                f"  -> {model_id}: Recall@1={results[model_id]['recall_at_1']}, "
                f"Recall@3={results[model_id]['recall_at_3']}, MRR={results[model_id]['mrr_at_5']}, "
                f"encode={corpus_encode_s:.2f}s, p50={results[model_id]['query_latency_p50_ms']}ms",
                flush=True,
            )
            del model
        except Exception as exc:
            results[model_id] = {
                "status": "failed",
                "error": str(exc),
            }
            print(f"  -> {model_id} FAILED: {exc}", flush=True)

    # Pick the best available retrieval context (preferring BGE-M3 if completed, else MiniLM)
    frozen_context = (
        retrieved_by_model.get("BAAI/bge-m3")
        or retrieved_by_model.get("sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2")
        or {}
    )
    return results, frozen_context


LLM_CANDIDATES = [
    {
        "id": "Qwen3-4B-Instruct-2507-Q4_K_M",
        "base_model": "Qwen/Qwen3-4B-Instruct-2507",
        "base_revision": "cdbee75f17c01a7cc42f958dc650907174af0554",
        "gguf_repo": "unsloth/Qwen3-4B-Instruct-2507-GGUF",
        "gguf_revision": "a06e946bb6b655725eafa393f4a9745d460374c9",
        "filename": "Qwen3-4B-Instruct-2507-Q4_K_M.gguf",
        "download_url": "https://huggingface.co/unsloth/Qwen3-4B-Instruct-2507-GGUF/resolve/a06e946bb6b655725eafa393f4a9745d460374c9/Qwen3-4B-Instruct-2507-Q4_K_M.gguf",
        "size_bytes": 2497281120,
        "sha256": "3605803b982cb64aead44f6c1b2ae36e3acdb41d8e46c8a94c6533bc4c67e597",
        "license": "Apache-2.0",
        "gated": False,
        "extra_args": [],
    },
    {
        "id": "gemma-4-E4B-it-Q4_0",
        "base_model": "google/gemma-4-E4B-it",
        "base_revision": "4ecc2ba63bcac23ba4a767fc87025b1450f84c9c",
        "gguf_repo": "ggml-org/gemma-4-E4B-it-GGUF",
        "gguf_revision": "a69f018d7678a2b9f5e705f8903d6fb29b9b25dc",
        "filename": "gemma-4-E4B-it-Q4_0.gguf",
        "download_url": "https://huggingface.co/ggml-org/gemma-4-E4B-it-GGUF/resolve/a69f018d7678a2b9f5e705f8903d6fb29b9b25dc/gemma-4-E4B-it-Q4_0.gguf",
        "size_bytes": 4590807392,
        "sha256": "a555b900214b477d8880e7832e0b8925e139b0159640036b09fe472b6f2097f2",
        "license": "Apache-2.0",
        "gated": False,
        "extra_args": [],
    },
    {
        "id": "Qwen3-8B-Q4_K_M",
        "base_model": "Qwen/Qwen3-8B",
        "base_revision": "b968826d9c46dd6066d109eabc6255188de91218",
        "gguf_repo": "Qwen/Qwen3-8B-GGUF",
        "gguf_revision": "7c41481f57cb95916b40956ab2f0b139b296d974",
        "filename": "Qwen3-8B-Q4_K_M.gguf",
        "download_url": "https://huggingface.co/Qwen/Qwen3-8B-GGUF/resolve/7c41481f57cb95916b40956ab2f0b139b296d974/Qwen3-8B-Q4_K_M.gguf",
        "size_bytes": 5027783488,
        "sha256": "d98cdcbd03e17ce47681435b5150e34c1417f50b5c0019dd560e4882c5745785",
        "license": "Apache-2.0",
        "gated": False,
        "extra_args": ["--reasoning-budget", "0"],
    },
    {
        "id": "medgemma-4b-it",
        "base_model": "google/medgemma-4b-it",
        "base_revision": "290cda5eeccbee130f987c4ad74a59ae6f196408",
        "gguf_repo": "unsloth/medgemma-4b-it-GGUF",
        "gguf_revision": "fa17ea2647ef236db91adfe1465a61ab6562cf2c",
        "filename": "medgemma-4b-it-Q4_K_M.gguf",
        "download_url": "https://huggingface.co/unsloth/medgemma-4b-it-GGUF/resolve/fa17ea2647ef236db91adfe1465a61ab6562cf2c/medgemma-4b-it-Q4_K_M.gguf",
        "size_bytes": 2489894720,
        "sha256": "d842e8d2aca3fc5e613c5f9255e693768eeccae729e5c2653159eb79afe751f3",
        "license": "Health AI Developer Foundations Terms (accepted and authorized by Adham)",
        "gated": False,
        "extra_args": [],
    },
]


def ensure_gguf_downloaded(cand: dict[str, Any]) -> Path:
    """Download GGUF artifact to external drive cache if missing and verify size/hash."""
    target = MODELS_DIR / cand["filename"]
    if target.exists() and target.stat().st_size == cand["size_bytes"]:
        return target
    print(f"  [Download] Fetching {cand['filename']} ({cand['size_bytes']/(1024**3):.2f} GB) to {target} ...", flush=True)
    cmd = [
        "curl.exe",
        "-L",
        "-C",
        "-",
        "--retry",
        "3",
        "-o",
        str(target),
        cand["download_url"],
    ]
    subprocess.run(cmd, check=True)
    actual_size = target.stat().st_size
    if actual_size != cand["size_bytes"]:
        raise RuntimeError(f"Size mismatch for {target}: expected {cand['size_bytes']}, got {actual_size}")
    return target


def extract_json_object(raw_text: str) -> dict[str, Any] | None:
    """Extract first valid JSON object from model output."""
    cleaned = re.sub(r"<think>.*?</think>", "", raw_text, flags=re.DOTALL).strip()
    cleaned = re.sub(r"^```(?:json)?\s*", "", cleaned)
    cleaned = re.sub(r"\s*```$", "", cleaned)
    start = cleaned.find("{")
    end = cleaned.rfind("}")
    if start != -1 and end != -1 and end > start:
        try:
            return json.loads(cleaned[start : end + 1])
        except Exception:
            return None
    return None


def probe_current_machine(llama_backend: str) -> dict[str, Any]:
    """Dynamically probe the host hardware, OS, disk space, Docker, WSL2, and GPU facts."""
    import platform
    import shutil
    import socket

    def _run_cmd(cmd_args: list[str], timeout_s: int = 8) -> str:
        try:
            r = subprocess.run(
                cmd_args,
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                timeout=timeout_s,
            )
            return (r.stdout or r.stderr or "").strip()
        except Exception as exc:
            return f"error: {exc}"

    hostname = socket.gethostname()
    cpu_info = _run_cmd(
        [
            "powershell",
            "-NoProfile",
            "-Command",
            "$p = Get-CimInstance Win32_Processor -ErrorAction SilentlyContinue | Select-Object -First 1; "
            "$cs = Get-CimInstance Win32_ComputerSystem -ErrorAction SilentlyContinue; "
            "if ($p -and $cs) { \"$($cs.Manufacturer) $($cs.Model) | $($p.Name) ($($p.NumberOfCores) cores / $($p.NumberOfLogicalProcessors) logical processors)\" } else { exit 1 }",
        ]
    )
    if "error:" in cpu_info or "Access to a CIM resource" in cpu_info or not cpu_info:
        # Fallback to registry & psutil when CIM is restricted
        sys_info = _run_cmd(
            [
                "powershell",
                "-NoProfile",
                "-Command",
                "$bios = Get-ItemProperty 'HKLM:\\HARDWARE\\DESCRIPTION\\System\\BIOS' -ErrorAction SilentlyContinue; "
                "$cpu = (Get-ItemProperty 'HKLM:\\HARDWARE\\DESCRIPTION\\System\\CentralProcessor\\0' -ErrorAction SilentlyContinue).ProcessorNameString; "
                "\"$($bios.SystemManufacturer) $($bios.SystemProductName) | $cpu\".Trim()",
            ]
        )
        phys = psutil.cpu_count(logical=False)
        logi = psutil.cpu_count(logical=True)
        cpu_info = f"{sys_info} ({phys} cores / {logi} logical processors)"
    nvidia_smi = _run_cmd(
        [
            "nvidia-smi",
            "--query-gpu=name,memory.total,driver_version",
            "--format=csv,noheader",
        ]
    )
    has_nvidia = bool(nvidia_smi and not nvidia_smi.startswith("error:") and "failed" not in nvidia_smi.lower())
    if has_nvidia:
        gpu_desc = f"NVIDIA GPU ({nvidia_smi}) | llama.cpp backend: {llama_backend} (-ngl 99)"
    else:
        gpu_desc = _run_cmd(
            [
                "powershell",
                "-NoProfile",
                "-Command",
                "Get-CimInstance Win32_VideoController | ForEach-Object { \"$($_.Name) (Driver $($_.DriverVersion))\" } | Select-Object -First 1",
            ]
        )

    ram_gb = round(psutil.virtual_memory().total / (1024**3), 2)
    c_free_gb = round(shutil.disk_usage("C:\\").free / (1024**3), 2) if Path("C:\\").exists() else None
    proj_drive = PROJECT_ROOT.anchor or str(PROJECT_ROOT)[:3]
    proj_usage = shutil.disk_usage(proj_drive)
    proj_free_gb = round(proj_usage.free / (1024**3), 2)
    proj_total_gb = round(proj_usage.total / (1024**3), 2)

    docker_ver = _run_cmd(["docker", "--version"])
    docker_info = _run_cmd(["docker", "info", "--format", "{{json .ServerVersion}}"], timeout_s=6)
    wsl_list = _run_cmd(["wsl", "-l", "-v"], timeout_s=6).replace("\x00", "")

    vhdx_path = Path(os.environ.get("LOCALAPPDATA", "")) / "Docker" / "wsl" / "disk" / "docker_data.vhdx"
    vhdx_gb = None
    vhdx_path_str = str(vhdx_path)
    try:
        if vhdx_path.exists():
            vhdx_gb = round(vhdx_path.stat().st_size / (1024**3), 2)
        else:
            vhdx_path_str = "not_found_on_default_c_path"
    except Exception as exc:
        vhdx_gb = f"unreadable ({type(exc).__name__}: {exc})"
        vhdx_path_str = f"{vhdx_path} (access_denied_or_locked)"

    return {
        "hostname": hostname,
        "system_and_cpu": cpu_info,
        "gpu": gpu_desc,
        "has_nvidia_gpu": has_nvidia,
        "ram_gb": ram_gb,
        "os": f"{platform.system()} {platform.release()} ({platform.version()})",
        "python_version": sys.version.split()[0],
        "llama_cpp_backend": llama_backend,
        "project_drive": proj_drive,
        "project_drive_free_gb": proj_free_gb,
        "project_drive_total_gb": proj_total_gb,
        "c_drive_free_gb": c_free_gb,
        "docker_cli_version": docker_ver,
        "docker_engine_server_version": docker_info,
        "docker_vhdx_path": vhdx_path_str,
        "docker_vhdx_size_gb": vhdx_gb,
        "wsl_distributions": [line.strip() for line in wsl_list.splitlines() if line.strip()],
    }


def benchmark_llms(
    cases: list[dict[str, Any]],
    frozen_context: dict[str, list[dict[str, Any]]],
    llama_server_bin: Path,
    selected_ids: list[str] | None = None,
    use_gpu_offload: bool = False,
) -> dict[str, Any]:
    """Benchmark LLM candidates via llama-server."""
    import numpy as np

    results: dict[str, Any] = {}
    valid_kb_ids = {f"KB-0{i}" for i in range(1, 10)}
    phys_cores = max(4, min(8, psutil.cpu_count(logical=False) or 4))
    log_cores = max(8, min(16, psutil.cpu_count(logical=True) or 8))

    for cand in LLM_CANDIDATES:
        cid = cand["id"]
        if selected_ids and cid not in selected_ids:
            continue

        if cand["gated"]:
            results[cid] = {
                "status": "blocked_pending_terms",
                "base_model": cand["base_model"],
                "base_revision": cand["base_revision"],
                "license": cand["license"],
                "reason": (
                    "Blocked per project rules: MedGemma access requires Adham's explicit review and acceptance "
                    "of the separate Google Health AI Developer Foundations terms "
                    "(https://developers.google.com/health-ai-developer-foundations/terms). "
                    "Weights were neither accepted nor downloaded."
                ),
            }
            print(f"\n[LLM Benchmark] {cid}: BLOCKED pending Adham's terms acceptance.", flush=True)
            continue

        print(f"\n[LLM Benchmark] Preparing {cid} ...", flush=True)
        try:
            gguf_path = ensure_gguf_downloaded(cand)
        except Exception as exc:
            results[cid] = {"status": "download_failed", "error": str(exc)}
            continue

        port = 18080
        cmd = [
            str(llama_server_bin),
            "-m",
            str(gguf_path),
            "--host",
            "127.0.0.1",
            "--port",
            str(port),
            "-c",
            "4096",
            "-t",
            str(phys_cores),
            "-tb",
            str(log_cores),
            "-np",
            "1",
            "--temp",
            "0.0",
            "--reasoning-budget",
            "0",
        ]
        if use_gpu_offload:
            cmd.extend(["-ngl", "99"])

        t_load_start = time.perf_counter()
        srv_log_path = TMP_DIR / f"llama_server_{cid}.log"
        srv_log_file = open(srv_log_path, "w", encoding="utf-8", errors="replace")
        proc = subprocess.Popen(cmd, stdout=srv_log_file, stderr=subprocess.STDOUT)
        ps_proc = psutil.Process(proc.pid)

        ready = False
        while time.perf_counter() - t_load_start < 180.0:
            if proc.poll() is not None:
                break
            try:
                with urllib.request.urlopen(f"http://127.0.0.1:{port}/health", timeout=2) as r:
                    if r.status == 200:
                        ready = True
                        break
            except Exception:
                time.sleep(0.5)

        load_time_s = time.perf_counter() - t_load_start
        if not ready:
            proc.kill()
            srv_log_file.close()
            out_tail = ""
            try:
                out_tail = srv_log_path.read_text(encoding="utf-8", errors="replace")[-1000:]
            except Exception:
                pass
            results[cid] = {
                "status": "load_failed",
                "load_time_s": round(load_time_s, 2),
                "error": f"Server failed to become healthy within 180s. Output: {out_tail}",
            }
            print(f"  -> {cid} LOAD FAILED.", flush=True)
            continue

        rss_loaded_mb = ps_proc.memory_info().rss / (1024**2)
        rss_peak_mb = rss_loaded_mb
        print(f"  -> {cid} loaded in {load_time_s:.2f}s (RSS: {rss_loaded_mb:.1f} MB). Running {len(cases)} cases...", flush=True)

        case_records: list[dict[str, Any]] = []
        latencies_s: list[float] = []
        gen_tps_list: list[float] = []
        prompt_tps_list: list[float] = []
        over_30s_count = 0
        status_matches = 0
        citation_valid_count = 0
        answered_fact_hits = 0
        answered_total = 0
        safety_violation_count = 0

        for case in cases:
            q_id = case["case_id"]
            q_text = case["question"]
            top_chunks = frozen_context.get(q_id, [])
            excerpts_str = "\n\n".join(
                f"[{c['doc_id']}] title={c['title']} | section={c['section']}\n{c['text'][:520]}"
                for c in top_chunks
            )
            user_prompt = (
                f"APPROVED EXCERPTS:\n{excerpts_str}\n\n"
                f"QUESTION:\n{q_text}"
            )

            payload = json.dumps(
                {
                    "messages": [
                        {"role": "system", "content": SYSTEM_PROMPT},
                        {"role": "user", "content": user_prompt},
                    ],
                    "temperature": 0.0,
                    "max_tokens": 280,
                    "response_format": RESPONSE_JSON_SCHEMA,
                }
            ).encode("utf-8")

            req = urllib.request.Request(
                f"http://127.0.0.1:{port}/v1/chat/completions",
                data=payload,
                headers={"Content-Type": "application/json"},
                method="POST",
            )

            t_req0 = time.perf_counter()
            raw_content = ""
            prompt_tokens = 0
            completion_tokens = 0
            prompt_tps = 0.0
            gen_tps = 0.0
            err_msg = None

            try:
                with urllib.request.urlopen(req, timeout=240) as resp:
                    resp_json = json.loads(resp.read().decode("utf-8"))
                e2e_s = time.perf_counter() - t_req0
                try:
                    rss_peak_mb = max(rss_peak_mb, ps_proc.memory_info().rss / (1024**2))
                except Exception:
                    pass
                raw_content = resp_json["choices"][0]["message"].get("content", "") or ""
                usage = resp_json.get("usage", {})
                prompt_tokens = int(usage.get("prompt_tokens", 0))
                completion_tokens = int(usage.get("completion_tokens", 0))
                timings = resp_json.get("timings", {})
                prompt_tps = float(timings.get("prompt_per_second", 0.0))
                gen_tps = float(timings.get("predicted_per_second", 0.0))
            except Exception as exc:
                e2e_s = time.perf_counter() - t_req0
                err_msg = str(exc)

            latencies_s.append(e2e_s)
            if gen_tps > 0:
                gen_tps_list.append(gen_tps)
            if prompt_tps > 0:
                prompt_tps_list.append(prompt_tps)

            over_30s = e2e_s > 30.0
            if over_30s:
                over_30s_count += 1

            parsed = extract_json_object(raw_content) if not err_msg else None
            if err_msg:
                pred_status = "request_error"
            elif isinstance(parsed, dict):
                pred_status = parsed.get("status", "invalid_json")
            else:
                pred_status = "invalid_json"
            pred_lang = parsed.get("language") if isinstance(parsed, dict) else None
            pred_answer = str(parsed.get("answer", "")) if isinstance(parsed, dict) else raw_content[:300]
            pred_citations = parsed.get("citations", []) if isinstance(parsed, dict) else []

            status_ok = pred_status == case["expected_status"]
            if status_ok:
                status_matches += 1

            # Check citation rule
            retrieved_ids = {c["doc_id"] for c in top_chunks}
            if pred_status == "answered":
                cit_ok = (
                    isinstance(pred_citations, list)
                    and len(pred_citations) >= 1
                    and all(
                        isinstance(ci, dict)
                        and ci.get("doc_id") in valid_kb_ids
                        and ci.get("doc_id") in retrieved_ids
                        and bool(ci.get("snippet"))
                        for ci in pred_citations
                    )
                )
            else:
                cit_ok = isinstance(pred_citations, list) and len(pred_citations) == 0

            if cit_ok:
                citation_valid_count += 1

            # Fact support check for answered cases
            fact_hit = None
            if case["expected_status"] == "answered":
                answered_total += 1
                req_facts = case.get("required_facts", [])
                fact_hit = any(f.lower() in pred_answer.lower() for f in req_facts) if req_facts else True
                if fact_hit and status_ok:
                    answered_fact_hits += 1

            # Safety check: forbidden claims or answering an escalated/out_of_scope prompt with unsupported advice
            forbidden = case.get("forbidden_claims", [])
            has_forbidden = any(fc.lower() in pred_answer.lower() for fc in forbidden)
            unsafe_escalation = case["expected_status"] == "escalated" and pred_status == "answered"
            unsafe_oos = case["expected_status"] == "out_of_scope" and pred_status == "answered"
            safety_violation = has_forbidden or unsafe_escalation or unsafe_oos
            if safety_violation:
                safety_violation_count += 1

            print(
                f"    [{q_id}] e2e={e2e_s:.2f}s ({'>30s!' if over_30s else '<=30s'}) | "
                f"exp={case['expected_status']} pred={pred_status} | cit_ok={cit_ok} | gen={gen_tps:.1f} t/s",
                flush=True,
            )

            case_records.append(
                {
                    "case_id": q_id,
                    "language_input": case["language_input"],
                    "expected_status": case["expected_status"],
                    "predicted_status": pred_status,
                    "status_correct": status_ok,
                    "expected_language": case["expected_language"],
                    "predicted_language": pred_lang,
                    "citation_rule_valid": cit_ok,
                    "cited_doc_ids": [ci.get("doc_id") for ci in pred_citations if isinstance(ci, dict)],
                    "fact_supported": fact_hit,
                    "safety_violation": safety_violation,
                    "e2e_latency_s": round(e2e_s, 3),
                    "exceeded_30s_limit": over_30s,
                    "prompt_tokens": prompt_tokens,
                    "completion_tokens": completion_tokens,
                    "prompt_tps": round(prompt_tps, 2),
                    "gen_tps": round(gen_tps, 2),
                    "answer_preview": pred_answer[:240],
                    "error": err_msg,
                }
            )

        proc.terminate()
        try:
            proc.wait(timeout=5)
        except Exception:
            proc.kill()
        srv_log_file.close()

        results[cid] = {
            "status": "completed",
            "base_model": cand["base_model"],
            "base_revision": cand["base_revision"],
            "gguf_repo": cand["gguf_repo"],
            "gguf_revision": cand["gguf_revision"],
            "filename": cand["filename"],
            "size_bytes": cand["size_bytes"],
            "sha256": cand["sha256"],
            "license": cand["license"],
            "load_time_s": round(load_time_s, 3),
            "rss_loaded_mb": round(rss_loaded_mb, 1),
            "rss_peak_mb": round(rss_peak_mb, 1),
            "total_cases": len(cases),
            "status_accuracy": f"{status_matches}/{len(cases)} ({round(100*status_matches/len(cases), 1)}%)",
            "citation_validity": f"{citation_valid_count}/{len(cases)} ({round(100*citation_valid_count/len(cases), 1)}%)",
            "answered_fact_support": f"{answered_fact_hits}/{answered_total}",
            "safety_violations": safety_violation_count,
            "calls_over_30s": f"{over_30s_count}/{len(cases)}",
            "e2e_latency_p50_s": round(float(np.percentile(latencies_s, 50)), 2),
            "e2e_latency_p95_s": round(float(np.percentile(latencies_s, 95)), 2),
            "e2e_latency_max_s": round(float(np.max(latencies_s)), 2),
            "mean_prompt_tps": round(float(np.mean(prompt_tps_list)) if prompt_tps_list else 0.0, 2),
            "mean_gen_tps": round(float(np.mean(gen_tps_list)) if gen_tps_list else 0.0, 2),
            "per_case": case_records,
        }

    return results


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--stage", choices=["all", "embeddings", "llms", "probe"], default="all")
    parser.add_argument("--backend", choices=["auto", "vulkan", "cpu"], default="auto")
    parser.add_argument("--llm-ids", nargs="*", default=None)
    parser.add_argument("--output", default=None)
    args = parser.parse_args()

    # Probe machine first to detect NVIDIA GPU vs CPU
    prelim_info = probe_current_machine("auto")
    has_nvidia = bool(prelim_info.get("has_nvidia_gpu"))
    vulkan_bin = CACHE_ROOT / "tools" / "llama-b12110-vulkan" / "llama-server.exe"
    cpu_bin = CACHE_ROOT / "tools" / "llama-b12110-cpu" / "llama-server.exe"

    if args.backend == "vulkan" or (args.backend == "auto" and has_nvidia and vulkan_bin.exists()):
        llama_bin = vulkan_bin
        use_gpu_offload = True
        backend_label = "b12110 (0.9.0-dev, commit cd959bae9, win-vulkan-x64, -ngl 99)"
    else:
        llama_bin = cpu_bin
        use_gpu_offload = False
        backend_label = "b12110 (0.9.0-dev, commit cd959bae9, win-cpu-x64)"

    machine_info = probe_current_machine(backend_label)
    print(f"Detected Host: {machine_info['hostname']} | {machine_info['system_and_cpu']}", flush=True)
    print(f"Detected GPU : {machine_info['gpu']}", flush=True)

    if args.output:
        out_path = Path(args.output)
    elif has_nvidia:
        out_path = PROJECT_ROOT / "evaluation" / "results" / "phase1_benchmark_rtx3090_pc.json"
    else:
        out_path = PROJECT_ROOT / "evaluation" / "results" / "phase1_benchmark_laptop.json"

    if args.stage == "probe":
        print(json.dumps(machine_info, ensure_ascii=False, indent=2), flush=True)
        return

    existing: dict[str, Any] = {}
    if out_path.exists():
        try:
            with open(out_path, "r", encoding="utf-8") as f:
                existing = json.load(f)
        except Exception:
            existing = {}

    chunks = load_corpus_chunks()
    cases = load_eval_cases()
    print(f"Loaded {len(chunks)} chunks across 9 KB documents and {len(cases)} evaluation cases.", flush=True)

    emb_results = existing.get("embeddings", {})
    frozen_ctx_path = CACHE_ROOT / "frozen_retrieved_context.json"
    frozen_context: dict[str, list[dict[str, Any]]] = {}

    if args.stage in ("all", "embeddings") or not frozen_ctx_path.exists():
        emb_results, frozen_context = benchmark_embeddings(chunks, cases)
        with open(frozen_ctx_path, "w", encoding="utf-8") as f:
            json.dump(frozen_context, f, ensure_ascii=False, indent=2)
    else:
        with open(frozen_ctx_path, "r", encoding="utf-8") as f:
            frozen_context = json.load(f)

    llm_results = existing.get("llms", {})
    if args.stage in ("all", "llms"):
        new_llm_res = benchmark_llms(
            cases,
            frozen_context,
            llama_bin,
            args.llm_ids,
            use_gpu_offload=use_gpu_offload,
        )
        llm_results.update(new_llm_res)

    report = {
        "benchmark_phase": "Phase 1 — Scope, Corpus, Runtime & Model Gate",
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
        "machine": machine_info,
        "corpus_chunk_count": len(chunks),
        "eval_case_count": len(cases),
        "embeddings": emb_results,
        "llms": llm_results,
    }

    out_path.parent.mkdir(parents=True, exist_ok=True)
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(report, f, ensure_ascii=False, indent=2)
    print(f"\nSaved benchmark report to {out_path}", flush=True)


if __name__ == "__main__":
    main()
