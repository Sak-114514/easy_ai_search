import asyncio
import inspect
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from types import SimpleNamespace

import pytest

import my_ai_search.deep_process.deep_process as deep_process_module
import my_ai_search.process.process as process_module


@pytest.fixture
def deep_process_config(monkeypatch):
    config = SimpleNamespace(
        deep_process=SimpleNamespace(
            summary_length=120,
            summary_backend="extractive",
            summary_api_url=None,
            summary_model=None,
            summary_timeout=1,
            summary_api_key=None,
            min_quality_score=0.0,
            min_content_length=20,
            max_content_length=5000,
            dedup_threshold=0.75,
            max_concurrent_summaries=2,
        )
    )
    monkeypatch.setattr(deep_process_module, "get_config", lambda: config)
    return config


def test_process_module_does_not_define_global_readability_lock():
    source = Path(process_module.__file__).read_text(encoding="utf-8")
    assert "_READABILITY_LOCK =" not in source


def test_clean_html_allows_parallel_readability_calls(monkeypatch):
    state = {"active": 0, "max_active": 0}
    gate = threading.Lock()

    def fake_readability(html):
        with gate:
            state["active"] += 1
            state["max_active"] = max(state["max_active"], state["active"])
        time.sleep(0.05)
        with gate:
            state["active"] -= 1
        return "正文内容" * 40

    monkeypatch.setattr(process_module, "_should_skip_readability", lambda html: False)
    monkeypatch.setattr(process_module, "_extract_with_readability", fake_readability)

    html = "<html><body><article>正文</article></body></html>"
    with ThreadPoolExecutor(max_workers=4) as executor:
        results = list(executor.map(lambda _: process_module.clean_html(html), range(4)))

    assert all(result for result in results)
    assert state["max_active"] > 1, "readability extraction should no longer be serialized by a global lock"


def test_assess_quality_keeps_counter_import_at_module_top():
    assert "from collections import Counter" not in inspect.getsource(deep_process_module.assess_quality)


def test_detect_duplicates_avoids_pairwise_thefuzz_scan(deep_process_config, monkeypatch):
    def fail_if_called(*args, **kwargs):
        raise AssertionError("pairwise thefuzz scan should not be used for near-duplicate detection")

    monkeypatch.setattr(deep_process_module.fuzz, "ratio", fail_if_called)

    chunks = [
        {
            "text": "Python asyncio tasks can be cancelled gracefully with semaphores and gather orchestration.",
            "chunk_id": 0,
            "url": "https://example.com/article",
        },
        {
            "text": (
                "Python asyncio task cancellation works gracefully with gather orchestration "
                "plus semaphore control."
            ),
            "chunk_id": 1,
            "url": "https://example.com/article",
        },
        {
            "text": "Sourdough bread depends on hydration, fermentation, and oven spring.",
            "chunk_id": 2,
            "url": "https://example.com/article",
        },
    ]

    result = deep_process_module.detect_duplicates(chunks, similarity_threshold=0.7)

    assert result["duplicate_ids"], "near-duplicate content should still be detected without pairwise fuzzy matching"


def test_deep_process_content_limits_summary_parallelism(deep_process_config, monkeypatch):
    state = {"active": 0, "max_active": 0}
    gate = threading.Lock()

    def fake_summary(text, max_length=None):
        with gate:
            state["active"] += 1
            state["max_active"] = max(state["max_active"], state["active"])
        time.sleep(0.05)
        with gate:
            state["active"] -= 1
        return f"summary:{text[:12]}"

    monkeypatch.setattr(deep_process_module, "generate_summary", fake_summary)

    chunks = [
        {"text": f"chunk-{i} 内容足够长。" * 10, "chunk_id": i, "url": "https://example.com", "metadata": {}}
        for i in range(4)
    ]

    processed = deep_process_module.deep_process_content(
        chunks,
        enable_summary=True,
        enable_dedup=False,
        enable_quality_check=False,
    )

    assert len(processed) == 4
    assert state["max_active"] == 2, "summary generation should respect max_concurrent_summaries"


@pytest.mark.asyncio
async def test_deep_process_content_is_safe_inside_running_event_loop(deep_process_config, monkeypatch):
    monkeypatch.setattr(deep_process_module, "generate_summary", lambda text, max_length=None: "summary")

    chunks = [{"text": "正文内容。" * 20, "chunk_id": 0, "url": "https://example.com", "metadata": {}}]

    result = await asyncio.to_thread(
        deep_process_module.deep_process_content,
        chunks,
        "https://example.com",
        True,
        False,
        False,
    )

    assert result[0]["summary"] == "summary"
