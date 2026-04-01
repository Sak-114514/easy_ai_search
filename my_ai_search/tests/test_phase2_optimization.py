import pytest
import asyncio
from concurrent.futures import ThreadPoolExecutor
from unittest.mock import patch, MagicMock, AsyncMock

from deep_process import deep_process_page, dedup_chunks
from vector.vector_query import hybrid_search, search, _keyword_search


class TestDeepProcessPage:
    def test_basic_processing(self):
        chunks = [
            {
                "text": "Python是一门高级编程语言，具有简洁清晰的语法。它支持多种编程范式，被广泛应用于Web开发、数据科学和人工智能等领域。",
                "chunk_id": 0,
                "url": "https://python.org",
                "metadata": {},
            },
        ]

        result = deep_process_page(
            chunks,
            enable_summary=True,
            enable_quality_check=True,
            min_quality_score=0.5,
        )

        assert len(result) == 1
        assert "quality_score" in result[0]
        assert "is_duplicate" in result[0]
        assert result[0]["is_duplicate"] == False

    def test_empty_chunks(self):
        result = deep_process_page([])
        assert result == []

    def test_all_features_disabled(self):
        chunks = [
            {
                "text": "Some text content here",
                "chunk_id": 0,
                "url": "https://test.com",
            },
        ]
        result = deep_process_page(
            chunks, enable_summary=False, enable_quality_check=False
        )
        assert len(result) == 1
        assert "summary" not in result[0]
        assert "quality_score" not in result[0]

    def test_quality_filtering(self):
        chunks = [
            {
                "text": "Python是一门高级编程语言。它支持多种编程范式，被广泛应用于Web开发、数据科学和人工智能等领域。",
                "chunk_id": 0,
                "url": "https://python.org",
                "metadata": {},
            },
            {
                "text": "啊啊啊啊啊啊啊啊啊啊啊啊",
                "chunk_id": 1,
                "url": "https://python.org",
                "metadata": {},
            },
        ]

        result = deep_process_page(
            chunks,
            enable_summary=False,
            enable_quality_check=True,
            min_quality_score=0.5,
        )

        assert len(result) == 1
        assert result[0]["chunk_id"] == 0

    def test_failed_page_result(self):
        result = {"success": False, "url": "https://test.com", "html": ""}
        from deep_process import deep_process_page

        chunks = deep_process_page([], enable_summary=True)
        assert chunks == []


class TestDedupChunks:
    def test_exact_duplicates(self):
        chunks = [
            {"text": "Python是一门编程语言", "chunk_id": 0, "url": "https://test.com"},
            {"text": "Python是一门编程语言", "chunk_id": 1, "url": "https://test.com"},
            {"text": "Java也是一门编程语言", "chunk_id": 2, "url": "https://test.com"},
        ]

        result = dedup_chunks(chunks, similarity_threshold=1.0)

        assert len(result) == 2

    def test_empty_chunks(self):
        result = dedup_chunks([])
        assert result == []

    def test_no_duplicates(self):
        chunks = [
            {"text": "Python is great", "chunk_id": 0, "url": "https://test.com"},
            {"text": "Java is also good", "chunk_id": 1, "url": "https://test.com"},
        ]

        result = dedup_chunks(chunks, similarity_threshold=0.9)

        assert len(result) == 2

    def test_near_duplicates(self):
        chunks = [
            {"text": "Python是一门编程语言", "chunk_id": 0, "url": "https://test.com"},
            {
                "text": "Python是一门非常流行的编程语言",
                "chunk_id": 1,
                "url": "https://test.com",
            },
            {"text": "Java也是一门编程语言", "chunk_id": 2, "url": "https://test.com"},
        ]

        result = dedup_chunks(chunks, similarity_threshold=0.7)

        assert len(result) < 3


class TestKeywordSearchOptimization:
    def test_keyword_search_with_candidate_ids(self):
        from vector.vector import init_vector_db, store_documents, clear_collection

        clear_collection()

        chunks = [
            {
                "text": "Machine learning is a subset of AI.",
                "chunk_id": 0,
                "url": "https://example1.com",
            },
            {
                "text": "Deep learning uses neural networks.",
                "chunk_id": 1,
                "url": "https://example1.com",
            },
            {
                "text": "Python is a programming language.",
                "chunk_id": 2,
                "url": "https://example2.com",
            },
            {
                "text": "AI can learn from data patterns.",
                "chunk_id": 0,
                "url": "https://example3.com",
            },
        ]
        store_documents(chunks)

        vector_results = search("AI", top_k=2)
        candidate_ids = [r["id"] for r in vector_results]

        results_with_candidates = _keyword_search(
            "AI", top_k=4, candidate_ids=candidate_ids
        )
        results_without_candidates = _keyword_search("AI", top_k=4)

        assert all(r["id"] in candidate_ids for r in results_with_candidates)

        if len(candidate_ids) < 4:
            assert len(results_with_candidates) <= len(candidate_ids)
            assert len(results_without_candidates) >= len(results_with_candidates)

    def test_keyword_search_empty_candidates(self):
        results = _keyword_search("test", top_k=5, candidate_ids=[])
        assert results == []


class TestPipelineIntegration:
    def test_pipeline_import(self):
        from my_ai_search.main import _pipeline_fetch_and_process

        assert asyncio.iscoroutinefunction(_pipeline_fetch_and_process)

    def test_pipeline_returns_correct_structure(self):
        from my_ai_search.main import _pipeline_fetch_and_process
        import time

        mock_result = {
            "fetch_results": [],
            "all_processed_chunks": [],
            "cache_hits": 0,
            "pipeline_time": 0.1,
            "total_raw_chunks": 0,
            "total_chunks_before_dedup": 0,
        }

        assert "fetch_results" in mock_result
        assert "all_processed_chunks" in mock_result
        assert "cache_hits" in mock_result
        assert "pipeline_time" in mock_result
        assert "total_raw_chunks" in mock_result
        assert "total_chunks_before_dedup" in mock_result

    def test_prefilter_search_results_dedupes_domain_and_skips_non_article(self):
        from my_ai_search.main import _prefilter_search_results

        search_results = [
            {
                "title": "Python asyncio 官方文档",
                "url": "https://docs.python.org/3/library/asyncio.html",
                "content": "docs",
                "score": 0.9,
            },
            {
                "title": "Python asyncio 官方文档法语版",
                "url": "https://docs.python.org/fr/3/library/asyncio.html",
                "content": "docs fr",
                "score": 0.8,
            },
            {
                "title": "Python asyncio 官方文档 3.10",
                "url": "https://docs.python.org/3.10/library/asyncio.html",
                "content": "docs 3.10",
                "score": 0.7,
            },
            {
                "title": "Pull requests · python/asyncio · GitHub",
                "url": "https://github.com/python/asyncio/pulls",
                "content": "repo list",
                "score": 0.95,
            },
            {
                "title": "Python asyncio 最佳实践",
                "url": "https://www.cnblogs.com/async-guide",
                "content": "guide",
                "score": 0.75,
            },
        ]

        filtered = _prefilter_search_results(
            search_results=search_results,
            query="Python asyncio 最佳实践",
            max_results=3,
        )

        urls = [item["url"] for item in filtered]
        assert "https://github.com/python/asyncio/pulls" not in urls
        assert "https://www.cnblogs.com/async-guide" in urls
        assert len([u for u in urls if "docs.python.org" in u]) <= 2

    def test_enrich_candidate_chunks_only_processes_top_candidates(self):
        from my_ai_search.main import _enrich_candidate_chunks

        config = MagicMock()
        config.deep_process.enable_summary = True
        config.deep_process.enable_quality_check = True
        config.deep_process.min_quality_score = 0.5

        chunk_lookup = {
            "https://a.com#chunk_0": {
                "text": "Python asyncio 最佳实践与任务调度",
                "snippet": "Python asyncio 最佳实践",
                "chunk_id": 0,
                "url": "https://a.com",
                "metadata": {"title": "Python asyncio 最佳实践"},
            },
            "https://b.com#chunk_0": {
                "text": "家常红烧肉的做法",
                "snippet": "红烧肉教程",
                "chunk_id": 0,
                "url": "https://b.com",
                "metadata": {"title": "红烧肉教程"},
            },
        }
        vector_results = [
            {
                "id": "https://a.com#chunk_0",
                "text": chunk_lookup["https://a.com#chunk_0"]["text"],
                "metadata": {"source_url": "https://a.com", "chunk_id": 0},
                "similarity": 0.91,
                "score": 0.91,
            },
            {
                "id": "https://b.com#chunk_0",
                "text": chunk_lookup["https://b.com#chunk_0"]["text"],
                "metadata": {"source_url": "https://b.com", "chunk_id": 0},
                "similarity": 0.75,
                "score": 0.75,
            },
        ]

        with patch("my_ai_search.main.deep_process_page") as mock_deep_process_page:
            mock_deep_process_page.side_effect = lambda page_chunks, **kwargs: [
                {**chunk, "summary": "summary", "metadata": {**chunk.get("metadata", {}), "summary": "summary"}}
                for chunk in page_chunks
            ]
            result = _enrich_candidate_chunks(
                query="Python asyncio 最佳实践",
                vector_results=vector_results,
                chunk_lookup=chunk_lookup,
                config=config,
                max_results=1,
                disable_deep_process=False,
            )

        assert result["candidate_ids"] == {"https://a.com#chunk_0", "https://b.com#chunk_0"}
        assert "https://a.com#chunk_0" in result["processed_map"]
        assert "https://b.com#chunk_0" in result["processed_map"]

    def test_search_ai_prefilters_urls_before_pipeline(self):
        from my_ai_search.main import search_ai

        config = MagicMock()
        config.searxng.max_results = 3
        config.deep_process.enable_summary = False
        config.deep_process.enable_quality_check = False
        config.deep_process.min_quality_score = 0.5

        search_results = [
            {
                "title": "Python asyncio 官方文档",
                "url": "https://docs.python.org/3/library/asyncio.html",
                "content": "docs",
                "score": 0.9,
            },
            {
                "title": "Python asyncio 官方文档法语版",
                "url": "https://docs.python.org/fr/3/library/asyncio.html",
                "content": "docs fr",
                "score": 0.8,
            },
            {
                "title": "Pull requests · python/asyncio · GitHub",
                "url": "https://github.com/python/asyncio/pulls",
                "content": "repo list",
                "score": 0.95,
            },
            {
                "title": "Python asyncio 最佳实践",
                "url": "https://www.cnblogs.com/async-guide",
                "content": "guide",
                "score": 0.75,
            },
        ]

        pipeline_result = {
            "fetch_results": [],
            "all_processed_chunks": [],
            "cache_hits": 0,
            "pipeline_time": 0.1,
            "total_raw_chunks": 0,
            "total_chunks_before_dedup": 0,
        }

        with patch("my_ai_search.main.get_config", return_value=config), \
             patch("my_ai_search.main.validate_config", return_value=True), \
             patch("my_ai_search.main.init_vector_db"), \
             patch("my_ai_search.main.hybrid_search", return_value=[]), \
             patch("my_ai_search.main.search", return_value=search_results), \
             patch("my_ai_search.main.asyncio.run", return_value=pipeline_result) as mock_asyncio_run, \
             patch("my_ai_search.main.get_cache_stats", return_value={}):
            result = search_ai("Python asyncio 最佳实践", max_results=3, use_cache=False, skip_local=True)

        filtered_urls = mock_asyncio_run.call_args.args[0].cr_frame.f_locals["urls"]
        assert "https://github.com/python/asyncio/pulls" not in filtered_urls
        assert len([u for u in filtered_urls if "docs.python.org" in u]) <= 2
        assert result["results"] == []

    def test_search_ai_fast_mode_skips_vector_storage(self):
        from my_ai_search.main import search_ai

        fake_config = MagicMock()
        fake_config.searxng.max_results = 3
        fake_config.deep_process.enable_dedup = False
        fake_config.deep_process.dedup_threshold = 0.85
        fake_config.deep_process.enable_summary = False
        fake_config.deep_process.enable_quality_check = False
        fake_config.deep_process.min_quality_score = 0.5

        pipeline_result = {
            "fetch_results": [{"url": "https://a.com", "success": True}],
            "all_processed_chunks": [
                {
                    "text": "Redis 持久化机制对比 RDB AOF 的核心差异与优缺点",
                    "snippet": "Redis 持久化机制对比",
                    "chunk_id": 0,
                    "url": "https://a.com",
                    "metadata": {"source_url": "https://a.com", "title": "Redis 持久化机制对比"},
                }
            ],
            "cache_hits": 0,
            "pipeline_time": 0.1,
            "total_raw_chunks": 1,
            "total_chunks_before_dedup": 1,
        }

        with patch("my_ai_search.main.get_config", return_value=fake_config), \
             patch("my_ai_search.main.validate_config", return_value=True), \
             patch("my_ai_search.main.init_vector_db"), \
             patch("my_ai_search.main.search", return_value=[{"title": "A", "url": "https://a.com"}]), \
             patch("my_ai_search.main.asyncio.run", return_value=pipeline_result), \
             patch("my_ai_search.main.store_documents") as mock_store, \
             patch("my_ai_search.main.hybrid_search", return_value=[]), \
             patch("my_ai_search.main.get_cache_stats", return_value={}):
            result = search_ai(
                "Redis 持久化机制对比",
                max_results=3,
                use_cache=False,
                skip_local=True,
                mode="fast",
            )

        mock_store.assert_not_called()
        assert result["vector_stats"]["stored_documents"] == 0
        assert result["vector_stats"]["mode"] == "fast"
        assert result["results"]

    def test_prefilter_search_results_respects_fetch_target(self):
        from my_ai_search.main import _prefilter_search_results

        search_results = [
            {"title": f"Result {i}", "url": f"https://example{i}.com/article"} for i in range(6)
        ]
        filtered = _prefilter_search_results(
            search_results=search_results,
            query="测试查询",
            max_results=3,
            fetch_target=3,
        )
        assert len(filtered) == 3

    def test_enrich_candidate_chunks_tracks_filtered_low_quality(self):
        from my_ai_search.main import _enrich_candidate_chunks

        config = MagicMock()
        config.deep_process.enable_summary = True
        config.deep_process.enable_quality_check = True
        config.deep_process.min_quality_score = 0.5

        chunk_lookup = {
            "https://a.com#chunk_0": {
                "text": "Python asyncio 最佳实践与任务调度",
                "snippet": "Python asyncio 最佳实践",
                "chunk_id": 0,
                "url": "https://a.com",
                "metadata": {"title": "Python asyncio 最佳实践"},
            }
        }
        vector_results = [
            {
                "id": "https://a.com#chunk_0",
                "text": chunk_lookup["https://a.com#chunk_0"]["text"],
                "metadata": {"source_url": "https://a.com", "chunk_id": 0},
                "similarity": 0.91,
                "score": 0.91,
            }
        ]

        with patch("my_ai_search.main.deep_process_page", return_value=[]):
            result = _enrich_candidate_chunks(
                query="Python asyncio 最佳实践",
                vector_results=vector_results,
                chunk_lookup=chunk_lookup,
                config=config,
                max_results=1,
                disable_deep_process=False,
            )

        assert result["candidate_ids"] == {"https://a.com#chunk_0"}
        assert result["processed_map"] == {}
        assert result["filtered_low_quality"] == 1

    def test_online_search_uses_request_scoped_vector_filter(self):
        from my_ai_search.main import search_ai

        fake_config = MagicMock()
        fake_config.searxng.max_results = 3
        fake_config.deep_process.enable_dedup = False
        fake_config.deep_process.dedup_threshold = 0.85
        fake_config.deep_process.enable_summary = False
        fake_config.deep_process.enable_quality_check = False
        fake_config.deep_process.min_quality_score = 0.5

        pipeline_result = {
            "fetch_results": [{"url": "https://a.com", "success": True}],
            "all_processed_chunks": [
                {
                    "text": "Python asyncio 最佳实践",
                    "snippet": "Python asyncio 最佳实践",
                    "chunk_id": 0,
                    "url": "https://a.com",
                    "metadata": {"source_url": "https://a.com"},
                }
            ],
            "cache_hits": 0,
            "pipeline_time": 0.1,
            "total_raw_chunks": 1,
            "total_chunks_before_dedup": 1,
        }

        with patch("my_ai_search.main.get_config", return_value=fake_config), \
             patch("my_ai_search.main.validate_config", return_value=True), \
             patch("my_ai_search.main.init_vector_db"), \
             patch("my_ai_search.main.search", return_value=[{"title": "A", "url": "https://a.com"}]), \
             patch("my_ai_search.main.asyncio.run", return_value=pipeline_result), \
             patch("my_ai_search.main.store_documents", return_value=["https://a.com#chunk_0"]) as mock_store, \
             patch("my_ai_search.main.hybrid_search", return_value=[
                 {
                     "id": "https://a.com#chunk_0",
                     "text": "Python asyncio 最佳实践",
                     "metadata": {"source_url": "https://a.com", "chunk_id": 0},
                     "similarity": 0.9,
                     "score": 0.9,
                 }
             ]) as mock_hybrid, \
             patch("my_ai_search.main._enrich_candidate_chunks", return_value={
                 "processed_map": {},
                 "candidate_ids": set(),
                 "filtered_low_quality": 0,
             }), \
             patch("my_ai_search.main.get_cache_stats", return_value={}):
            result = search_ai(
                "Python asyncio 最佳实践",
                max_results=3,
                use_cache=False,
                skip_local=True,
            )

        assert result["source"] == "online"
        store_metadata = mock_store.call_args.kwargs["metadata"]
        assert store_metadata["content_scope"] == "online_temp"
        assert isinstance(store_metadata["search_request_id"], str)
        assert mock_hybrid.call_args.kwargs["filter_metadata"] == {
            "search_request_id": store_metadata["search_request_id"]
        }


class TestBackwardCompatibility:
    def test_deep_process_content_unchanged(self):
        from deep_process import deep_process_content

        chunks = [
            {
                "text": "Python是一门高级编程语言，具有简洁清晰的语法。它支持多种编程范式，被广泛应用于Web开发、数据科学和人工智能等领域。",
                "chunk_id": 0,
                "url": "https://python.org",
                "metadata": {},
            },
            {
                "text": "Python是一门高级编程语言，具有简洁清晰的语法。它支持多种编程范式，被广泛应用于Web开发、数据科学和人工智能等领域。",
                "chunk_id": 1,
                "url": "https://python.org",
                "metadata": {},
            },
        ]

        processed = deep_process_content(
            chunks,
            url="https://python.org",
            enable_summary=True,
            enable_dedup=True,
            enable_quality_check=True,
        )

        assert len(processed) == 1
        assert "summary" in processed[0]
        assert "quality_score" in processed[0]


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
