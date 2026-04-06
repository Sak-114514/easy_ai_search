import importlib
from pathlib import Path
from types import SimpleNamespace

import pytest

import my_ai_search.fetch.fetch as fetch_module
import my_ai_search.search.search as search_module


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
