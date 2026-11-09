from app.storage.database import SQLiteStore


def test_conversation_analytics_aggregate_synthetic_records(tmp_path):
    store = SQLiteStore(tmp_path / "analytics.db")
    common = dict(
        session_id="synthetic", language="en", model="test-model",
        prompt_tokens=12, completion_tokens=5, retrieval_ms=10.0,
        generation_ms=20.0,
    )
    store.record_conversation(question="Synthetic question A", status="answered", total_ms=30.0, **common)
    store.record_conversation(question="Synthetic question A", status="out_of_scope", total_ms=40.0, **common)
    store.record_conversation(question="Synthetic question B", status="escalated", total_ms=50.0, **common)

    result = store.analytics(limit=1)
    assert result["conversation_volume"] == 3
    assert result["top_questions"] == [{"question": "Synthetic question A", "count": 2}]
    assert result["unanswered_count"] == 2
    assert result["tokens"] == {"prompt": 36, "completion": 15}
    assert result["latency_ms"]["total_p50"] == 40.0
    assert result["latency_ms"]["total_max"] == 50.0
    metrics = store.conversation_metrics("synthetic")
    assert metrics is not None
    assert metrics["prompt_tokens"] == 12
    assert metrics["completion_tokens"] == 5
