import sys
import os

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from vector.vector import (
    init_vector_db,
    store_documents,
    get_collection,
    clear_collection,
    get_collection_stats,
    reset_vector_db,
)
from utils.exceptions import VectorException
import time


def test_init_vector_db():
    """测试1：初始化向量数据库"""
    print("\n=== 测试1：初始化向量数据库 ===")

    try:
        collection = init_vector_db()
        print(f"✓ Collection name: {collection.name}")

        stats = get_collection_stats()
        print(f"✓ Initial document count: {stats['count']}")

        assert collection is not None, "Collection should not be None"
        print("✓ Collection is not None")

        print("✓ 测试1通过：初始化向量数据库成功")
        return True

    except Exception as e:
        print(f"✗ 测试1失败：{e}")
        return False


def test_store_documents():
    """测试2：存储文档"""
    print("\n=== 测试2：存储文档 ===")

    try:
        chunks = [
            {
                "text": "Python is a programming language.",
                "chunk_id": 0,
                "url": "https://example.com",
            },
            {
                "text": "JavaScript is used for web development.",
                "chunk_id": 1,
                "url": "https://example.com",
            },
        ]

        ids = store_documents(chunks)
        print(f"✓ Stored document IDs: {ids}")

        stats = get_collection_stats()
        print(f"✓ Total documents: {stats['count']}")

        assert len(ids) == 2, f"Expected 2 IDs, got {len(ids)}"
        assert stats["count"] == 2, f"Expected 2 documents, got {stats['count']}"
        print("✓ 测试2通过：存储文档成功")
        return True

    except Exception as e:
        print(f"✗ 测试2失败：{e}")
        return False


def test_metadata_storage():
    """测试3：元数据存储"""
    print("\n=== 测试3：元数据存储 ===")

    try:
        chunks = [
            {
                "text": "Machine learning is a subset of AI.",
                "chunk_id": 2,
                "url": "https://example.com",
                "metadata": {"category": "AI", "author": "test"},
            }
        ]

        ids = store_documents(chunks)
        print(f"✓ Stored document with metadata: {ids}")

        collection = get_collection()
        result = collection.get(ids=["https://example.com#chunk_2"])
        print(f"✓ Retrieved metadata: {result['metadatas'][0]}")

        assert result["metadatas"][0]["category"] == "AI", "Category should be 'AI'"
        assert result["metadatas"][0]["author"] == "test", "Author should be 'test'"
        print("✓ 测试3通过：元数据存储成功")
        return True

    except Exception as e:
        print(f"✗ 测试3失败：{e}")
        return False


def test_clear_collection():
    """测试4：清空集合"""
    print("\n=== 测试4：清空集合 ===")

    try:
        stats_before = get_collection_stats()
        print(f"✓ Before clear: {stats_before['count']} docs")

        clear_collection()

        stats_after = get_collection_stats()
        print(f"✓ After clear: {stats_after['count']} docs")

        assert stats_after["count"] == 0, (
            f"Expected 0 documents after clear, got {stats_after['count']}"
        )
        print("✓ 测试4通过：清空集合成功")
        return True

    except Exception as e:
        print(f"✗ 测试4失败：{e}")
        return False


def test_get_collection_stats():
    """测试5：获取集合统计信息"""
    print("\n=== 测试5：获取集合统计信息 ===")

    try:
        stats = get_collection_stats()
        print(f"✓ Collection stats: {stats}")

        assert "count" in stats, "Stats should contain 'count'"
        assert "name" in stats, "Stats should contain 'name'"
        assert "metadata" in stats, "Stats should contain 'metadata'"

        print("✓ 测试5通过：获取集合统计信息成功")
        return True

    except Exception as e:
        print(f"✗ 测试5失败：{e}")
        return False


def test_reset_vector_db():
    """测试6：重置向量数据库"""
    print("\n=== 测试6：重置向量数据库 ===")

    try:
        chunks = [
            {
                "text": "Test document for reset.",
                "chunk_id": 0,
                "url": "https://test.com",
            }
        ]

        store_documents(chunks)
        stats_before = get_collection_stats()
        print(f"✓ Before reset: {stats_before['count']} docs")

        reset_vector_db()

        stats_after = get_collection_stats()
        print(f"✓ After reset: {stats_after['count']} docs")

        assert stats_after["count"] == 0, (
            f"Expected 0 documents after reset, got {stats_after['count']}"
        )
        print("✓ 测试6通过：重置向量数据库成功")
        return True

    except Exception as e:
        print(f"✗ 测试6失败：{e}")
        return False


def test_empty_chunks():
    """测试7：处理空文档列表"""
    print("\n=== 测试7：处理空文档列表 ===")

    try:
        ids = store_documents([])
        print(f"✓ Stored empty chunks: {ids}")

        assert ids == [], f"Expected empty list, got {ids}"
        print("✓ 测试7通过：正确处理空文档列表")
        return True

    except Exception as e:
        print(f"✗ 测试7失败：{e}")
        return False


def test_large_batch():
    """测试8：批量存储多个文档"""
    print("\n=== 测试8：批量存储多个文档 ===")

    try:
        chunks = [
            {
                "text": f"This is document {i}.",
                "chunk_id": i,
                "url": f"https://example.com/doc{i}",
            }
            for i in range(10)
        ]

        ids = store_documents(chunks)
        print(f"✓ Stored {len(ids)} documents")

        stats = get_collection_stats()
        print(f"✓ Total documents: {stats['count']}")

        assert len(ids) == 10, f"Expected 10 IDs, got {len(ids)}"
        assert stats["count"] == 10, f"Expected 10 documents, got {stats['count']}"
        print("✓ 测试8通过：批量存储多个文档成功")
        return True

    except Exception as e:
        print(f"✗ 测试8失败：{e}")
        return False


def main():
    """运行所有测试"""
    print("\n" + "=" * 50)
    print("开始运行向量存储模块测试")
    print("=" * 50)

    tests = [
        test_init_vector_db,
        test_store_documents,
        test_metadata_storage,
        test_get_collection_stats,
        test_clear_collection,
        test_empty_chunks,
        test_large_batch,
        test_reset_vector_db,
    ]

    passed = 0
    failed = 0

    for test in tests:
        try:
            if test():
                passed += 1
            else:
                failed += 1
        except Exception as e:
            print(f"✗ 测试异常：{test.__name__} - {e}")
            failed += 1

    print("\n" + "=" * 50)
    print(f"测试完成：通过 {passed}/{len(tests)}，失败 {failed}/{len(tests)}")
    print("=" * 50)

    return failed == 0


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
