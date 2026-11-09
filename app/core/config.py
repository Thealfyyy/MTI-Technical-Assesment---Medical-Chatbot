"""Configuration and storage path validation for the MTI Medical Knowledge Chatbot.

Phase 1 setup: defines environment-configurable paths rooted on the shared external drive
and provides a deterministic writability check so startup fails fast if the external drive
is missing, unmounted, or read-only.
"""

from __future__ import annotations

import os
import tempfile
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv


@dataclass(frozen=True)
class Settings:
    """Environment-backed configuration settings."""

    project_root: Path
    require_writable_storage: bool
    corpus_dir: Path
    kb_manifest_path: Path
    chroma_persist_dir: Path
    sqlite_db_path: Path
    uploads_dir: Path
    eval_results_dir: Path
    model_cache_dir: Path
    hf_home: Path
    sentence_transformers_home: Path
    app_host: str
    app_port: int
    request_timeout_seconds: float
    llm_server_url: str
    llm_model_name: str
    llm_max_tokens: int
    llm_temperature: float
    retrieval_top_k: int
    retrieval_min_score: float
    embedding_model_name: str
    embedding_model_revision: str = ""
    embedding_device: str = "cpu"

    @classmethod
    def from_env(cls) -> "Settings":
        default_root = Path(__file__).resolve().parents[2]
        # Load the local config without overriding explicit shell/CI settings.
        load_dotenv(default_root / ".env", override=False)
        root = Path(os.getenv("PROJECT_ROOT", str(default_root))).resolve()

        def _resolve(env_key: str, default_rel: str) -> Path:
            val = Path(os.getenv(env_key, default_rel))
            return val if val.is_absolute() else (root / val).resolve()

        return cls(
            project_root=root,
            require_writable_storage=os.getenv("REQUIRE_WRITABLE_STORAGE", "true").lower() in ("1", "true", "yes"),
            corpus_dir=_resolve("CORPUS_DIR", "Docs/Data"),
            kb_manifest_path=_resolve("KB_MANIFEST_PATH", "data/kb_manifest.yaml"),
            chroma_persist_dir=_resolve("CHROMA_PERSIST_DIR", "data/chroma"),
            sqlite_db_path=_resolve("SQLITE_DB_PATH", "data/sqlite/app.db"),
            uploads_dir=_resolve("UPLOADS_DIR", "data/uploads"),
            eval_results_dir=_resolve("EVAL_RESULTS_DIR", "evaluation/results"),
            model_cache_dir=_resolve("MODEL_CACHE_DIR", ".cache/models"),
            hf_home=_resolve("HF_HOME", ".cache/huggingface"),
            sentence_transformers_home=_resolve("SENTENCE_TRANSFORMERS_HOME", ".cache/sentence_transformers"),
            app_host=os.getenv("APP_HOST", "127.0.0.1"),
            app_port=int(os.getenv("APP_PORT", "8000")),
            request_timeout_seconds=float(os.getenv("REQUEST_TIMEOUT_SECONDS", "28")),
            llm_server_url=os.getenv("LLM_SERVER_URL", "http://127.0.0.1:8080").rstrip("/"),
            llm_model_name=os.getenv("LLM_MODEL_NAME", "Qwen3-8B-Q4_K_M"),
            llm_max_tokens=int(os.getenv("LLM_MAX_TOKENS", "512")),
            llm_temperature=float(os.getenv("LLM_TEMPERATURE", "0.0")),
            retrieval_top_k=int(os.getenv("RETRIEVAL_TOP_K", "3")),
            retrieval_min_score=float(os.getenv("RETRIEVAL_MIN_SCORE", "0.50")),
            embedding_model_name=os.getenv("EMBEDDING_MODEL_NAME", "BAAI/bge-m3"),
            embedding_model_revision=os.getenv("EMBEDDING_MODEL_REVISION", ""),
            embedding_device=os.getenv("EMBEDDING_DEVICE", "cpu"),
        )


from functools import lru_cache


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Return cached Settings instance loaded from environment variables."""
    return Settings.from_env()


def validate_storage_paths(settings: Settings | None = None) -> dict[str, str]:
    """Validate that the configured project root and persistence directories exist and are writable."""
    cfg = settings or Settings.from_env()
    if not cfg.project_root.exists():
        raise RuntimeError(f"Configured PROJECT_ROOT does not exist: {cfg.project_root}")

    if cfg.require_writable_storage:
        cfg.model_cache_dir.mkdir(parents=True, exist_ok=True)
        with tempfile.NamedTemporaryFile(dir=cfg.project_root, prefix=".write_probe_", delete=True) as tmp:
            tmp.write(b"ok")
            tmp.flush()

    return {
        "project_root": str(cfg.project_root),
        "corpus_dir": str(cfg.corpus_dir),
        "kb_manifest_path": str(cfg.kb_manifest_path),
        "model_cache_dir": str(cfg.model_cache_dir),
    }
