import asyncio
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from types import SimpleNamespace

import pytest

import my_ai_search.main as main_module
import my_ai_search.vector.vector as vector_module


@pytest.mark.asyncio
async def test_pipeline_fetch_and_process_cancellation_shuts_down_executor(monkeypatch):
    shutdown_called = asyncio.Event()
    started = asyncio.Event()
    cancelled_urls = []

    class TrackingExecutor(ThreadPoolExecutor):
        def shutdown(self, wait=True, cancel_futures=False):
            shutdown_called.set()
            return super().shutdown(wait=wait, cancel_futures=cancel_futures)

    async def slow_fetch(url, timeout=None):
        started.set()
        try:
            await asyncio.sleep(5)
        except asyncio.CancelledError:
            cancelled_urls.append(url)
            raise
        return {
            "url": url,
            "html": "<html></html>",
            "title": url,
            "success": True,
            "error": None,
            "duration": 0.01,
        }

    config = SimpleNamespace(
        lightpanda=SimpleNamespace(max_concurrent=4),
        deep_process=SimpleNamespace(enable_dedup=False, dedup_threshold=0.8),
    )

    monkeypatch.setattr(main_module, "ThreadPoolExecutor", TrackingExecutor)
    monkeypatch.setattr(main_module, "fetch_page", slow_fetch)

    task = asyncio.create_task(
        main_module._pipeline_fetch_and_process(
            urls=["https://a.example.com", "https://b.example.com"],
            use_cache=False,
            config=config,
        )
    )

    await started.wait()
    task.cancel()

    with pytest.raises(asyncio.CancelledError):
        await task

    await asyncio.sleep(0)
    assert shutdown_called.is_set(), "executor should be shut down on cancellation"
    assert cancelled_urls, "pending fetch tasks should receive cancellation"


def test_main_py_stays_under_900_lines():
    main_path = Path(main_module.__file__)
    assert len(main_path.read_text(encoding="utf-8").splitlines()) < 900


def test_cleanup_expired_documents_deletes_only_expired_ephemeral_docs(monkeypatch):
    cleanup = getattr(vector_module, "cleanup_expired_documents", None)
    assert callable(cleanup), "vector module should expose cleanup_expired_documents()"

    class FakeCollection:
        def __init__(self):
            self.deleted_ids = []
            self.payload = {
                "ids": [
                    "https://expired.example#chunk_0",
                    "https://fresh.example#chunk_0",
                    "https://durable.example#chunk_0",
                ],
                "metadatas": [
                    {"ephemeral": True, "expires_at": 50.0},
                    {"ephemeral": True, "expires_at": 150.0},
                    {"ephemeral": False, "expires_at": 10.0},
                ],
            }

        def get(self):
            return self.payload

        def delete(self, ids):
            self.deleted_ids.extend(ids)

    collection = FakeCollection()
    monkeypatch.setattr(vector_module, "get_collection", lambda: collection)

    cleanup(now=100.0)

    assert collection.deleted_ids == ["https://expired.example#chunk_0"]
