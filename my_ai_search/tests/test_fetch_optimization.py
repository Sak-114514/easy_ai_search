import asyncio
import importlib
from pathlib import Path
from types import SimpleNamespace

import pytest

import my_ai_search.fetch.fetch as fetch_module

search_module = importlib.import_module("my_ai_search.search.search")


@pytest.mark.asyncio
async def test_fetch_page_returns_reusable_plain_data_fields(monkeypatch):
    async def fake_aiohttp(url, timeout):
        return {
            "url": url,
            "html": "<html><head><title>Example</title></head><body><article>Useful content.</article></body></html>",
            "title": "Example",
            "success": True,
            "error": None,
            "duration": 0.01,
        }

    monkeypatch.setattr(
        fetch_module,
        "get_config",
        lambda: SimpleNamespace(lightpanda=SimpleNamespace(timeout=5, max_concurrent=2)),
    )
    monkeypatch.setattr(fetch_module, "_use_requests", False)
    monkeypatch.setattr(fetch_module, "_fetch_with_aiohttp", fake_aiohttp)
    monkeypatch.setattr(fetch_module, "_is_content_sufficient", lambda html: True)

    result = await fetch_module.fetch_page("https://example.com")

    reusable_fields = {"parsed_title", "preview_text", "main_text_candidate"}
    assert reusable_fields & set(result.keys()), "fetch results should expose reusable plain-data parsing fields"


def test_search_reuses_cached_searxng_response_for_identical_query(monkeypatch):
    search_fresh = importlib.reload(search_module)
    calls = []

    monkeypatch.setattr(
        search_fresh,
        "get_config",
        lambda: SimpleNamespace(searxng=SimpleNamespace(max_results=3, timeout=1, api_url="http://searx.test")),
    )
    monkeypatch.setattr(search_fresh, "get_search_intent", lambda query: {})

    def fake_api(query, params):
        calls.append((query, params.get("engines")))
        return {
            "results": [
                {
                    "title": f"{query} result",
                    "url": "https://example.com/result",
                    "content": "useful content",
                    "score": 1.0,
                }
            ]
        }

    monkeypatch.setattr(search_fresh, "_call_searxng_api", fake_api)

    first = search_fresh.search("python asyncio", max_results=1, engines="bing", allow_second_pass=False)
    second = search_fresh.search("python asyncio", max_results=1, engines="bing", allow_second_pass=False)

    assert first == second
    assert len(calls) == 1, "identical query+engines searches should hit the API once within the cache TTL"


def test_search_domain_rules_move_out_of_search_module():
    source = Path(search_module.__file__).read_text(encoding="utf-8")
    assert "_PREFERRED_DOMAINS =" not in source
    assert "_BLOCKED_DOMAINS =" not in source


@pytest.mark.asyncio
async def test_lightpanda_session_pool_serializes_target_lifecycle(monkeypatch):
    pool = fetch_module.LightPandaSessionPool("ws://127.0.0.1:9222", timeout=5, max_concurrent=2)
    state = {"active": 0, "max_active": 0, "create_calls": 0}

    async def fake_ensure_connection():
        return None

    async def fake_create_target(url):
        state["active"] += 1
        state["max_active"] = max(state["max_active"], state["active"])
        state["create_calls"] += 1
        await asyncio.sleep(0.05)
        return f"target-{state['create_calls']}"

    async def fake_attach_target(target_id):
        return f"session-{target_id}"

    async def fake_enable_page(session_id):
        return None

    async def fake_navigate(session_id, url, timeout):
        return None

    async def fake_evaluate_string(session_id, expression):
        if "document.title" in expression:
            return f"title-{session_id}"
        state["active"] -= 1
        return f"<html>{session_id}</html>"

    async def fake_close_target(target_id):
        return None

    monkeypatch.setattr(pool, "_ensure_connection", fake_ensure_connection)
    monkeypatch.setattr(pool, "_create_target", fake_create_target)
    monkeypatch.setattr(pool, "_attach_target", fake_attach_target)
    monkeypatch.setattr(pool, "_enable_page", fake_enable_page)
    monkeypatch.setattr(pool, "_navigate", fake_navigate)
    monkeypatch.setattr(pool, "_evaluate_string", fake_evaluate_string)
    monkeypatch.setattr(pool, "_safe_close_target", fake_close_target)

    results = await asyncio.gather(
        pool.fetch_html("https://example.com/a", timeout=5),
        pool.fetch_html("https://example.com/b", timeout=5),
    )

    assert all(result["success"] for result in results)
    assert state["create_calls"] == 2
    assert state["max_active"] == 1, "target creation should be serialized to avoid CDP TargetAlreadyLoaded races"
