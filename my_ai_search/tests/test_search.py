import sys
import os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from search.search import (
    search,
    _parse_results,
    _build_refined_query,
    _build_recall_boost_query,
    _needs_recall_boost,
    _needs_source_profile_boost,
    _should_trigger_second_pass,
    _merge_search_results,
    _extract_query_terms,
)
from my_ai_search.utils.exceptions import SearchException
from unittest.mock import patch


def test_normal_search():
    """测试1：正常搜索"""
    print("\n=== Test 1: Normal Search ===")
    try:
        results = search("python programming")
        print(f"Found {len(results)} results")

        for i, result in enumerate(results[:3]):
            print(f"{i + 1}. {result['title']}")
            print(f"   URL: {result['url']}")
            print(f"   Content: {result['content'][:100]}...")
            print()

        assert len(results) > 0, "Should return at least one result"
        assert "title" in results[0], "Result should have 'title'"
        assert "url" in results[0], "Result should have 'url'"
        assert "content" in results[0], "Result should have 'content'"
        assert "score" in results[0], "Result should have 'score'"

        print("✓ Test 1 passed: Normal search works")
        return True
    except Exception as e:
        print(f"✗ Test 1 failed: {e}")
        return False


def test_custom_max_results():
    """测试2：自定义结果数"""
    print("\n=== Test 2: Custom Max Results ===")
    try:
        results = search("AI", max_results=10)
        print(f"Got {len(results)} results")

        assert len(results) <= 10, (
            f"Should return at most 10 results, got {len(results)}"
        )

        print("✓ Test 2 passed: Custom max_results works")
        return True
    except Exception as e:
        print(f"✗ Test 2 failed: {e}")
        return False


def test_empty_query():
    """测试3：空查询处理"""
    print("\n=== Test 3: Empty Query ===")
    try:
        search("")
        print("✗ Test 3 failed: Should raise SearchException for empty query")
        return False
    except SearchException as e:
        if "empty" in str(e).lower():
            print(f"✓ Test 3 passed: Correctly caught error: {e}")
            return True
        else:
            print(f"✗ Test 3 failed: Wrong error message: {e}")
            return False
    except Exception as e:
        print(f"✗ Test 3 failed: Wrong exception type: {type(e).__name__}: {e}")
        return False


def test_whitespace_query():
    """测试4：空白查询处理"""
    print("\n=== Test 4: Whitespace Query ===")
    try:
        search("   ")
        print("✗ Test 4 failed: Should raise SearchException for whitespace query")
        return False
    except SearchException as e:
        if "empty" in str(e).lower():
            print(f"✓ Test 4 passed: Correctly caught error: {e}")
            return True
        else:
            print(f"✗ Test 4 failed: Wrong error message: {e}")
            return False
    except Exception as e:
        print(f"✗ Test 4 failed: Wrong exception type: {type(e).__name__}: {e}")
        return False


def test_result_fields():
    """测试5：结果字段验证"""
    print("\n=== Test 5: Result Fields Validation ===")
    try:
        results = search("test query")

        for result in results:
            assert isinstance(result["title"], str), "Title should be string"
            assert isinstance(result["url"], str), "URL should be string"
            assert isinstance(result["content"], str), "Content should be string"
            assert isinstance(result["score"], (int, float)), "Score should be numeric"
            assert result["url"].startswith("http"), (
                f"URL should start with http: {result['url']}"
            )

        print(f"✓ Test 5 passed: All {len(results)} results have valid fields")
        return True
    except Exception as e:
        print(f"✗ Test 5 failed: {e}")
        return False


def test_parse_results_prefers_relevant_domains():
    response = {
        "results": [
            {
                "title": "下载某某App",
                "url": "https://apps.microsoft.com/detail/foo",
                "content": "免费下载 官方入口",
                "score": 0.9,
            },
            {
                "title": "Python asyncio 最佳实践",
                "url": "https://www.cnblogs.com/asyncio-best",
                "content": "介绍 asyncio 任务调度与并发控制",
                "score": 0.8,
            },
            {
                "title": "红烧肉家常做法",
                "url": "https://home.meishichina.com/recipe-70081.html",
                "content": "详细讲解焯水、炒糖色、收汁",
                "score": 0.7,
            },
        ]
    }

    results = _parse_results(response, max_results=5)
    urls = [item["url"] for item in results]

    assert "https://apps.microsoft.com/detail/foo" not in urls
    assert urls[0] == "https://www.cnblogs.com/asyncio-best"


def test_parse_results_blocks_shell_pages():
    response = {
        "results": [
            {
                "title": "Just a moment...",
                "url": "https://example.com/challenge",
                "content": "请稍候",
                "score": 0.9,
            },
            {
                "title": "HarmonyOS 架构详解",
                "url": "https://www.harmonyos.com/guide",
                "content": "介绍鸿蒙系统架构和分布式能力",
                "score": 0.8,
            },
        ]
    }

    results = _parse_results(response, max_results=5)

    assert len(results) == 1
    assert results[0]["url"] == "https://www.harmonyos.com/guide"


def test_extract_query_terms_for_chinese_queries():
    terms = _extract_query_terms("量子纠缠为什么不能超光速通信")

    assert "量子纠缠" in terms
    assert "超光速通信" in terms


def test_parse_results_penalizes_explanation_without_query_overlap():
    response = {
        "results": [
            {
                "title": "哔哩哔哩 - 维基百科，自由的百科全书",
                "url": "https://zh.wikipedia.org/zh-cn/%E5%93%94%E5%93%A9%E5%93%94%E5%93%A9",
                "content": "哔哩哔哩相关介绍",
                "score": 0.96,
            },
            {
                "title": "量子纠缠为什么不能超光速通信",
                "url": "https://www.163.com/dy/article/SCIENCE123.html",
                "content": "解释量子纠缠与超光速通信限制的科普文章",
                "score": 0.75,
            },
        ]
    }

    results = _parse_results(
        response,
        max_results=5,
        query="量子纠缠为什么不能超光速通信",
        intent_plan={"intent": "explanation"},
    )

    assert results[0]["url"] == "https://www.163.com/dy/article/SCIENCE123.html"


def test_build_refined_query_adds_social_terms_for_social_profile():
    refined = _build_refined_query(
        "OpenAI GPT-5.4 mini 用户反馈 首发 讨论",
        {"intent": "news"},
        {"source_profile": "social_realtime", "preferred_domains": ["x.com", "weibo.com"]},
    )

    assert "site:x.com" in refined.lower()
    assert "site:weibo.com" in refined.lower()


def test_build_recall_boost_query_adds_community_terms_for_tech_profile():
    refined = _build_recall_boost_query(
        "Python asyncio gather 和 TaskGroup 区别",
        {"intent": "technical"},
        {"source_profile": "tech_community", "preferred_domains": ["docs.python.org", "stackoverflow.com"]},
    )

    assert "site:docs.python.org" in refined.lower()
    assert "stackoverflow" in refined.lower()
    assert "github" in refined.lower()


def test_parse_results_uses_query_relevance():
    response = {
        "results": [
            {
                "title": "Reddit discussion about OpenAI billing",
                "url": "https://www.reddit.com/r/OpenAI/comments/abc",
                "content": "community post",
                "score": 0.95,
            },
            {
                "title": "Introducing OpenAI GPT-5.4 mini and nano",
                "url": "https://openai.com/index/introducing-gpt-5-4-mini-and-nano/",
                "content": "OpenAI 发布 GPT-5.4 mini 与 nano",
                "score": 0.8,
            },
        ]
    }

    results = _parse_results(response, max_results=5, query="OpenAI GPT-5.4 mini 发布信息")

    assert results[0]["url"] == "https://openai.com/index/introducing-gpt-5-4-mini-and-nano/"


def test_parse_results_prefers_official_news_profile():
    response = {
        "results": [
            {
                "title": "网友在微博讨论 OpenAI GPT-5.4 mini 发布",
                "url": "https://weibo.com/1234567890/abcdef",
                "content": "社交媒体讨论串",
                "score": 0.97,
            },
            {
                "title": "OpenAI 发布 GPT-5.4 mini 与 nano",
                "url": "https://finance.sina.com.cn/stock/t/2026-03-18/doc-inhrkfva3464410.shtml",
                "content": "新闻报道 OpenAI 发布 GPT-5.4 mini 与 nano",
                "score": 0.80,
            },
        ]
    }

    results = _parse_results(
        response,
        max_results=5,
        query="OpenAI GPT-5.4 mini 发布信息",
        tool_context={"source_profile": "official_news"},
    )

    assert "finance.sina.com.cn" in results[0]["url"]


def test_parse_results_prefers_social_realtime_profile():
    response = {
        "results": [
            {
                "title": "OpenAI 发布 GPT-5.4 mini 与 nano",
                "url": "https://finance.sina.com.cn/stock/t/2026-03-18/doc-inhrkfva3464410.shtml",
                "content": "新闻报道 OpenAI 发布 GPT-5.4 mini 与 nano",
                "score": 0.95,
            },
            {
                "title": "OpenAI 发布 GPT-5.4 mini 的首批讨论",
                "url": "https://x.com/openai/status/1234567890",
                "content": "来自社交媒体的一手动态",
                "score": 0.80,
            },
        ]
    }

    results = _parse_results(
        response,
        max_results=5,
        query="OpenAI GPT-5.4 mini 发布信息",
        tool_context={"source_profile": "social_realtime"},
    )

    assert results[0]["url"].startswith("https://x.com/")


def test_parse_results_social_profile_penalizes_irrelevant_reference_page():
    response = {
        "results": [
            {
                "title": "The Big Bang Theory - Wikipedia",
                "url": "https://en.wikipedia.org/wiki/The_Big_Bang_Theory",
                "content": "American television sitcom",
                "score": 0.99,
            },
            {
                "title": "OpenAI 上新 GPT-5.4 mini 与 nano",
                "url": "https://www.ithome.com/0/930/063.htm",
                "content": "OpenAI 发布 GPT-5.4 mini 与 nano，并带来用户首发讨论。",
                "score": 0.80,
            },
        ]
    }

    results = _parse_results(
        response,
        max_results=5,
        query="OpenAI GPT-5.4 mini 用户反馈 首发 讨论",
        tool_context={"source_profile": "social_realtime"},
    )

    assert "ithome.com" in results[0]["url"]


def test_parse_results_caps_duplicate_domains_for_tech_community():
    response = {
        "results": [
            {
                "title": "TaskGroup 与 gather 对比 - CSDN A",
                "url": "https://blog.csdn.net/foo/article/details/1",
                "content": "讲解 TaskGroup 与 gather 的差异",
                "score": 0.99,
            },
            {
                "title": "TaskGroup 与 gather 对比 - CSDN B",
                "url": "https://blog.csdn.net/bar/article/details/2",
                "content": "继续讲解 TaskGroup 与 gather 的差异",
                "score": 0.98,
            },
            {
                "title": "协程与任务 — Python 3.11.15 文档",
                "url": "https://docs.python.org/zh-cn/3.11/library/asyncio-task.html",
                "content": "Python 官方文档",
                "score": 0.80,
            },
        ]
    }

    results = _parse_results(
        response,
        max_results=3,
        query="Python asyncio gather 和 TaskGroup 区别",
        tool_context={"source_profile": "tech_community"},
    )

    urls = [item["url"] for item in results]
    assert len([url for url in urls if "csdn.net" in url]) == 1
    assert any("docs.python.org" in url for url in urls)


def test_parse_results_prefers_official_docs_in_tech_community():
    response = {
        "results": [
            {
                "title": "TaskGroup 与 gather 对比 - CSDN",
                "url": "https://blog.csdn.net/foo/article/details/1",
                "content": "讲解 TaskGroup 与 gather 的差异",
                "score": 0.95,
            },
            {
                "title": "协程与任务 — Python 3.11.15 文档",
                "url": "https://docs.python.org/zh-cn/3.11/library/asyncio-task.html",
                "content": "官方文档对 TaskGroup 与 gather 的说明",
                "score": 0.85,
            },
        ]
    }

    results = _parse_results(
        response,
        max_results=2,
        query="Python asyncio gather 和 TaskGroup 区别",
        tool_context={"source_profile": "tech_community"},
        intent_plan={"intent": "technical"},
    )

    assert results[0]["url"].startswith("https://docs.python.org/")


def test_parse_results_prefers_tool_context_domains():
    response = {
        "results": [
            {
                "title": "Redis 持久化机制对比",
                "url": "https://example.com/redis-guide",
                "content": "介绍 Redis RDB 和 AOF 的差异",
                "score": 0.92,
            },
            {
                "title": "Redis 持久化机制对比",
                "url": "https://redis.io/docs/latest/operate/oss_and_stack/management/persistence/",
                "content": "官方文档解释 Redis persistence",
                "score": 0.85,
            },
        ]
    }

    results = _parse_results(
        response,
        max_results=5,
        query="Redis 持久化机制对比 RDB AOF",
        tool_context={"preferred_domains": ["redis.io"]},
    )

    assert results[0]["url"].startswith("https://redis.io/")


def test_parse_results_blocks_tool_context_domains():
    response = {
        "results": [
            {
                "title": "Redis 持久化机制对比",
                "url": "https://bad.example.com/redis-guide",
                "content": "低质量转载",
                "score": 0.95,
            },
            {
                "title": "Redis 持久化机制对比",
                "url": "https://www.cnblogs.com/shizhengwen/p/9283973.html",
                "content": "介绍 RDB 和 AOF 差异",
                "score": 0.8,
            },
        ]
    }

    results = _parse_results(
        response,
        max_results=5,
        query="Redis 持久化机制对比 RDB AOF",
        tool_context={"blocked_domains": ["bad.example.com"]},
    )

    assert all("bad.example.com" not in item["url"] for item in results)


def test_parse_results_only_mode_keeps_preferred_domains():
    response = {
        "results": [
            {
                "title": "OpenAI 发布信息",
                "url": "https://openai.com/index/introducing-o3-and-o4-mini/",
                "content": "官方发布",
                "score": 0.8,
            },
            {
                "title": "OpenAI 发布信息转载",
                "url": "https://example.com/openai-news",
                "content": "转载内容",
                "score": 0.95,
            },
        ]
    }

    results = _parse_results(
        response,
        max_results=5,
        query="OpenAI GPT-5.4 mini 发布信息",
        tool_context={
            "preferred_domains": ["openai.com"],
            "domain_preference_mode": "only",
        },
    )

    assert len(results) == 1
    assert results[0]["url"].startswith("https://openai.com/")


def test_build_refined_query_by_intent():
    assert _build_refined_query("OpenAI GPT-5.4 mini 发布信息").endswith("官方 公告 详解")
    assert _build_refined_query("Python asyncio 最佳实践").endswith("官方文档 教程 最佳实践")
    assert _build_refined_query("家常红烧肉做法和技巧").endswith("做法 步骤 图文")
    assert _build_refined_query("量子纠缠为什么不能超光速通信").endswith("原理 通俗 科普")


def test_should_trigger_second_pass_for_low_value_top_results():
    results = [
        {
            "title": "Pull requests · python/asyncio · GitHub",
            "url": "https://github.com/python/asyncio/pulls",
            "content": "repo list",
            "score": 0.9,
        },
        {
            "title": "Reddit discussion about asyncio",
            "url": "https://www.reddit.com/r/Python/comments/abc",
            "content": "community",
            "score": 0.8,
        },
        {
            "title": "Python asyncio 官方文档",
            "url": "https://docs.python.org/3/library/asyncio.html",
            "content": "asyncio docs",
            "score": 0.7,
        },
    ]

    assert _should_trigger_second_pass(results, actual_max_results=3) is True


def test_recall_boost_query_for_howto_and_explanation():
    assert _build_recall_boost_query("家常宫保鸡丁做法和技巧", {"intent": "howto"}).endswith("家常 做法 图文 菜谱")
    assert _build_recall_boost_query("量子纠缠为什么不能超光速通信", {"intent": "explanation"}).endswith("原理 科普 详解")


def test_needs_recall_boost_when_results_too_few():
    assert _needs_recall_boost([], 3, {"intent": "howto"}) is True
    assert _needs_recall_boost([{"url": "a"}], 3, {"intent": "explanation"}) is True
    assert _needs_recall_boost([{"url": "a"}, {"url": "b"}, {"url": "c"}], 3, {"intent": "technical"}) is False


def test_needs_source_profile_boost_for_social_profile_without_social_hits():
    results = [
        {"url": "https://finance.sina.com.cn/stock/t/2026-03-18/doc-inhrkfva3464410.shtml"},
        {"url": "https://openai.com/index/introducing-gpt-5-4-mini-and-nano/"},
    ]

    assert _needs_source_profile_boost(results, {"source_profile": "social_realtime"}) is True
    assert _needs_source_profile_boost(results, {"source_profile": "official_news"}) is False


def test_parse_results_penalizes_howto_mismatch():
    response = {
        "results": [
            {
                "title": "Microsoft campus - Wikipedia",
                "url": "https://en.wikipedia.org/wiki/Microsoft_campus",
                "content": "construction and company campus",
                "score": 0.99,
            },
            {
                "title": "宫保鸡丁的家常做法",
                "url": "https://www.xiangha.com/caipu/123.html",
                "content": "详细食材、步骤和火候技巧",
                "score": 0.8,
            },
        ]
    }

    results = _parse_results(
        response,
        max_results=5,
        query="家常宫保鸡丁做法和技巧",
        intent_plan={"intent": "howto"},
    )

    assert results[0]["url"].startswith("https://www.xiangha.com/")


def test_parse_results_blocks_adult_and_insurance_mismatch():
    response = {
        "results": [
            {
                "title": "BokepIndo - Koleksi Terbaik Bokep Indo Viral Lengkap!",
                "url": "https://bokepindo.casa/",
                "content": "konten bokep indo",
                "score": 0.99,
            },
            {
                "title": "量子纠缠为什么不能超光速通信",
                "url": "https://example.com/quantum",
                "content": "量子纠缠不会传递可控信息，因此不能超光速通信",
                "score": 0.7,
            },
        ]
    }

    results = _parse_results(
        response,
        max_results=5,
        query="量子纠缠为什么不能超光速通信",
        intent_plan={"intent": "explanation"},
    )

    assert all("bokep" not in item["url"] for item in results)


def test_merge_search_results_prefers_non_low_value():
    primary = [
        {
            "title": "Pull requests · python/asyncio · GitHub",
            "url": "https://github.com/python/asyncio/pulls",
            "content": "repo list",
            "score": 0.9,
        },
        {
            "title": "Python asyncio 官方文档",
            "url": "https://docs.python.org/3/library/asyncio.html",
            "content": "asyncio docs",
            "score": 0.8,
        },
    ]
    refined = [
        {
            "title": "Python asyncio 最佳实践",
            "url": "https://www.cnblogs.com/async-guide",
            "content": "guide",
            "score": 0.85,
        }
    ]

    merged = _merge_search_results(primary, refined, max_results=5)
    urls = [item["url"] for item in merged]

    assert urls[0] == "https://docs.python.org/3/library/asyncio.html"
    assert "https://www.cnblogs.com/async-guide" in urls


def test_search_triggers_second_pass_and_merges_results():
    primary_response = {
        "results": [
            {
                "title": "Pull requests · python/asyncio · GitHub",
                "url": "https://github.com/python/asyncio/pulls",
                "content": "repo list",
                "score": 0.9,
            },
            {
                "title": "Reddit discussion about asyncio",
                "url": "https://www.reddit.com/r/Python/comments/abc",
                "content": "community",
                "score": 0.8,
            },
        ]
    }
    refined_response = {
        "results": [
            {
                "title": "Python asyncio 官方文档",
                "url": "https://docs.python.org/3/library/asyncio.html",
                "content": "asyncio docs",
                "score": 0.7,
            },
            {
                "title": "Python asyncio 最佳实践",
                "url": "https://www.cnblogs.com/async-guide",
                "content": "guide",
                "score": 0.6,
            },
        ]
    }

    with patch("search.search._retry_search", side_effect=[primary_response, refined_response]) as mock_retry:
        results = search("Python asyncio 最佳实践", max_results=3)

    urls = [item["url"] for item in results]
    assert mock_retry.call_count == 2
    assert urls[0] == "https://docs.python.org/3/library/asyncio.html"
    assert "https://www.cnblogs.com/async-guide" in urls


if __name__ == "__main__":
    print("=" * 60)
    print("Running Search Module Tests")
    print("=" * 60)

    tests = [
        test_normal_search,
        test_custom_max_results,
        test_empty_query,
        test_whitespace_query,
        test_result_fields,
    ]

    results = []
    for test_func in tests:
        result = test_func()
        results.append(result)

    print("\n" + "=" * 60)
    print(f"Test Summary: {sum(results)}/{len(results)} tests passed")
    print("=" * 60)

    if all(results):
        print("✓ All tests passed!")
        sys.exit(0)
    else:
        print("✗ Some tests failed")
        sys.exit(1)
