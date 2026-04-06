"""测试导入兼容层：统一将旧模块名映射到 my_ai_search 包路径。"""

import importlib
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def _alias_module(old_name: str, new_name: str) -> None:
    sys.modules[old_name] = importlib.import_module(new_name)


_alias_module("cache", "my_ai_search.cache")
_alias_module("config", "my_ai_search.config")
_alias_module("deep_process", "my_ai_search.deep_process")
_alias_module("fetch", "my_ai_search.fetch")
_alias_module("process", "my_ai_search.process")
_alias_module("search", "my_ai_search.search")
_alias_module("utils", "my_ai_search.utils")
_alias_module("vector", "my_ai_search.vector")
_alias_module("cache.cache", "my_ai_search.cache.cache")
_alias_module("deep_process.deep_process", "my_ai_search.deep_process.deep_process")
_alias_module("fetch.fetch", "my_ai_search.fetch.fetch")
_alias_module("process.process", "my_ai_search.process.process")
_alias_module("search.search", "my_ai_search.search.search")
_alias_module("utils.exceptions", "my_ai_search.utils.exceptions")
_alias_module("vector.vector", "my_ai_search.vector.vector")
_alias_module("vector.vector_query", "my_ai_search.vector.vector_query")


class _FakeCollection:
    def __init__(self):
        self._data = {}

    def count(self):
        return len(self._data)

    def get(self, ids=None, limit=None, offset=None):
        if ids is not None:
            existing = [i for i in ids if i in self._data]
            return {
                "ids": existing,
                "documents": [self._data[i]["document"] for i in existing],
                "metadatas": [self._data[i]["metadata"] for i in existing],
            }
        keys = list(self._data.keys())
        if offset is None:
            offset = 0
        if limit is None:
            limit = len(keys)
        selected = keys[offset : offset + limit]
        return {
            "ids": selected,
            "documents": [self._data[i]["document"] for i in selected],
            "metadatas": [self._data[i]["metadata"] for i in selected],
        }

    def add(self, ids, documents, metadatas):
        for i, d, m in zip(ids, documents, metadatas, strict=False):
            self._data[i] = {"document": d, "metadata": m}

    def update(self, ids, documents, metadatas):
        for i, d, m in zip(ids, documents, metadatas, strict=False):
            if i in self._data:
                self._data[i] = {"document": d, "metadata": m}

    def delete(self, ids=None, where=None):
        if ids is not None:
            for i in ids:
                self._data.pop(i, None)
            return
        if where and where.get("is_cache") is True:
            self._data.clear()


@pytest.fixture(autouse=True)
def _mock_external_dependencies(monkeypatch, request):
    path = str(request.node.fspath)

    if "my_ai_search/tests/test_cache.py" in path:
        cache_mod = importlib.import_module("my_ai_search.cache.cache")
        fake_collection = _FakeCollection()
        monkeypatch.setattr(cache_mod, "_get_cache_collection", lambda: fake_collection)
        monkeypatch.setattr(cache_mod, "_cache_hits", 0)
        monkeypatch.setattr(cache_mod, "_cache_misses", 0)

    if "my_ai_search/tests/test_search.py" in path or "my_ai_search/tests/test_local_first" in path:
        search_mod = importlib.import_module("my_ai_search.search.search")

        def _fake_call_searxng_api(query, params):
            q = params.get("q", query)
            return {
                "results": [
                    {
                        "title": f"{q} - mock result 1",
                        "url": "https://example.com/mock-1",
                        "content": "mock content 1",
                        "score": 0.9,
                    },
                    {
                        "title": f"{q} - mock result 2",
                        "url": "https://example.com/mock-2",
                        "content": "mock content 2",
                        "score": 0.8,
                    },
                ]
            }

        monkeypatch.setattr(search_mod, "_call_searxng_api", _fake_call_searxng_api)

    if "my_ai_search/tests/test_local_first" in path:
        main_mod = importlib.import_module("my_ai_search.main")

        async def _fake_fetch_page(url, timeout=None):
            return {
                "url": url,
                "html": (
                    "<html><body><article>"
                    + ("Python async programming best practices and patterns. " * 20)
                    + "</article></body></html>"
                ),
                "title": "Mock Page",
                "success": True,
                "error": None,
                "duration": 0.01,
            }

        monkeypatch.setattr(main_mod, "fetch_page", _fake_fetch_page)

    if "my_ai_search/tests/test_fetch.py" in path:
        for module_name in ("my_ai_search.fetch.fetch", "fetch.fetch"):
            fetch_mod = importlib.import_module(module_name)

            def _fake_fetch_with_requests(url, timeout):
                if "this-site-does-not-exist-12345.com" in url:
                    return {
                        "url": url,
                        "html": "",
                        "title": "",
                        "success": False,
                        "error": "DNS failure",
                        "duration": 0.01,
                    }
                return {
                    "url": url,
                    "html": "<html><head><title>Python</title></head><body>Python.org</body></html>",
                    "title": "Python",
                    "success": True,
                    "error": None,
                    "duration": 0.01,
                }

            monkeypatch.setattr(fetch_mod, "_fetch_with_requests", _fake_fetch_with_requests)
            monkeypatch.setattr(fetch_mod, "_use_requests", True)
