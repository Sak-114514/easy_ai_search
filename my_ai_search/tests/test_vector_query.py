#!/usr/bin/env python3

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from vector.vector import init_vector_db, store_documents, clear_collection
from vector.vector_query import search, hybrid_search, search_by_ids


def test_semantic_search():
    """测试语义检索"""
    print("测试1：语义检索")

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
        {
            "text": "Neural networks are inspired by biology.",
            "chunk_id": 1,
            "url": "https://example3.com",
        },
    ]
    store_documents(chunks)

    results = search("artificial intelligence", top_k=2)
    print(f"Found {len(results)} results")

    for result in results:
        print(f"{result['similarity']:.2f}: {result['text'][:50]}...")

    assert len(results) <= 2
    assert all("similarity" in r for r in results)
    print("✅ 测试1通过\n")


def test_hybrid_search():
    """测试混合检索"""
    print("测试2：混合检索")

    results = hybrid_search("Python programming", top_k=2, alpha=0.7)
    print(f"Hybrid search results: {len(results)}")

    for result in results:
        print(
            f"Score: {result['score']:.2f} (Vector: {result['vector_score']:.2f}, Keyword: {result['keyword_score']:.2f})"
        )
        print(f"Text: {result['text'][:50]}...")

    assert len(results) <= 2
    assert all("score" in r for r in results)
    print("✅ 测试2通过\n")


def test_metadata_filter():
    """测试元数据过滤"""
    print("测试3：元数据过滤")

    results = search("AI", filter_metadata={"source_url": "https://example1.com"})
    print(f"Filtered results: {len(results)}")

    for result in results:
        assert result["metadata"]["source_url"] == "https://example1.com"
        print(f"Match: {result['text'][:50]}...")

    print("✅ 测试3通过\n")


def test_empty_query():
    """测试空查询处理"""
    print("测试4：空查询处理")

    results = search("")
    assert results == []
    print("Empty query returns empty list: ✅\n")

    results = search("   ")
    assert results == []
    print("Whitespace query returns empty list: ✅\n")

    print("✅ 测试4通过\n")


def test_search_by_ids():
    """测试根据ID检索"""
    print("测试5：根据ID检索")

    test_ids = [
        "https://example1.com#chunk_0",
        "https://example1.com#chunk_1",
        "https://example2.com#chunk_2",
    ]

    results = search_by_ids(test_ids)
    print(f"Found {len(results)} documents by IDs")

    for result in results:
        print(f"ID: {result['id']}")
        print(f"Text: {result['text'][:50]}...")

    assert len(results) == 3
    assert all("id" in r and "text" in r for r in results)
    print("✅ 测试5通过\n")


def test_top_k_parameter():
    """测试top_k参数"""
    print("测试6：top_k参数")

    results3 = search("learning", top_k=3)
    print(f"Top 3: {len(results3)} results")

    results5 = search("learning", top_k=5)
    print(f"Top 5: {len(results5)} results")

    assert len(results3) <= 3
    assert len(results5) <= 5
    print("✅ 测试6通过\n")


def test_alpha_parameter():
    """测试alpha参数"""
    print("测试7：alpha参数")

    results_vector_weighted = hybrid_search("Python", top_k=3, alpha=0.9)
    results_balanced = hybrid_search("Python", top_k=3, alpha=0.5)
    results_keyword_weighted = hybrid_search("Python", top_k=3, alpha=0.1)

    print(f"Vector weighted (alpha=0.9): {len(results_vector_weighted)} results")
    print(f"Balanced (alpha=0.5): {len(results_balanced)} results")
    print(f"Keyword weighted (alpha=0.1): {len(results_keyword_weighted)} results")

    assert all("score" in r for r in results_vector_weighted)
    assert all("score" in r for r in results_balanced)
    assert all("score" in r for r in results_keyword_weighted)
    print("✅ 测试7通过\n")


def test_result_structure():
    """测试结果结构"""
    print("测试8：结果结构")

    results = search("AI", top_k=1)

    if results:
        result = results[0]
        required_keys = ["id", "text", "metadata", "similarity", "distance"]

        for key in required_keys:
            assert key in result, f"Missing key: {key}"
            print(f"✓ {key}: {type(result[key]).__name__}")

    print("✅ 测试8通过\n")


if __name__ == "__main__":
    print("=" * 50)
    print("Vector Query 模块测试")
    print("=" * 50 + "\n")

    try:
        init_vector_db()
        test_semantic_search()
        test_hybrid_search()
        test_metadata_filter()
        test_empty_query()
        test_search_by_ids()
        test_top_k_parameter()
        test_alpha_parameter()
        test_result_structure()

        print("=" * 50)
        print("所有测试通过！")
        print("=" * 50)
    except Exception as e:
        print(f"❌ 测试失败: {e}")
        import traceback

        traceback.print_exc()
        sys.exit(1)
