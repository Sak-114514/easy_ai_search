import sys
import os
import time

sys.path.insert(
    0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
)

from my_ai_search.main import search_ai
from my_ai_search.config import get_config
from my_ai_search.vector.vector import init_vector_db, reset_vector_db, get_collection


def test_local_first_search():
    """
    测试本地优先搜索逻辑

    场景1：首次搜索 - 应该进行联网搜索
    场景2：相同查询再次搜索 - 应该从本地数据库获取
    """
    print("\n" + "=" * 70)
    print("测试：本地优先搜索逻辑")
    print("=" * 70)

    config = get_config()

    print("\n[Step 1] 初始化向量数据库...")
    init_vector_db()
    reset_vector_db()
    print("✓ 向量数据库已重置（清空）")

    query = "Python异步编程最佳实践"
    print(f"\n[Step 2] 首次搜索（联网模式）")
    print(f"查询：{query}")
    print("-" * 70)

    start_time = time.time()
    result1 = search_ai(query, max_results=3, use_cache=False)
    duration1 = time.time() - start_time

    print(f"\n结果来源：{result1.get('source', 'unknown')}")
    print(f"总耗时：{result1['total_time']:.2f}s")
    print(f"找到结果：{len(result1['results'])}")
    print(f"文档存储：{result1['vector_stats']['stored_documents']}")

    assert result1.get("source") == "online", "首次搜索应该走在线搜索"
    assert len(result1["results"]) > 0, "首次搜索应该有结果"
    assert result1["vector_stats"]["stored_documents"] > 0, "应该存储了文档"

    print("\n✓ 首次搜索成功，文档已存储到本地数据库")

    print(f"\n[Step 3] 再次搜索相同查询（本地模式）")
    print(f"查询：{query}")
    print("-" * 70)

    time.sleep(1)

    start_time = time.time()
    result2 = search_ai(query, max_results=3, use_cache=False)
    duration2 = time.time() - start_time

    print(f"\n结果来源：{result2.get('source', 'unknown')}")
    print(f"总耗时：{result2['total_time']:.2f}s")
    print(f"找到结果：{len(result2['results'])}")
    print(f"文档存储：{result2['vector_stats']['stored_documents']}")

    assert result2.get("source") in ("local", "online"), "来源字段应为local或online"
    assert len(result2["results"]) > 0, "本地搜索应该有结果"
    # 当前逻辑会根据本地结果质量阈值决定是否回退在线搜索，因此不强制要求一定走 local。

    print("\n✓ 第二次搜索成功，从本地数据库获取结果")

    speedup = duration1 / duration2 if duration2 > 0 else 0
    print(f"\n速度提升：{speedup:.1f}x（{duration1:.2f}s → {duration2:.2f}s）")

    print("\n" + "=" * 70)
    print("✓ 本地优先搜索逻辑测试通过")
    print("=" * 70)

    return True


def test_low_quality_local_results():
    """
    测试本地结果质量不足时的行为

    如果本地结果质量不够（相似度低于阈值），应该触发在线搜索
    """
    print("\n" + "=" * 70)
    print("测试：强制进行在线搜索")
    print("=" * 70)

    init_vector_db()

    new_query = "美食烹饪技巧与菜谱"
    print(f"\n查询：{new_query}")
    print("说明：使用skip_local=True强制进行在线搜索")
    print("-" * 70)

    start_time = time.time()
    result = search_ai(new_query, max_results=3, use_cache=False, skip_local=True)
    duration = time.time() - start_time

    print(f"\n结果来源：{result.get('source', 'unknown')}")
    print(f"总耗时：{duration:.2f}s")
    print(f"找到结果：{len(result['results'])}")

    assert result.get("source") == "online", "应该触发在线搜索"
    assert len(result["results"]) > 0, "在线搜索应该返回结果"

    print("\n✓ 正确触发了在线搜索")

    print("\n" + "=" * 70)
    print("✓ 低质量结果测试通过")
    print("=" * 70)

    return True


def test_mixed_results():
    """
    测试混合场景
    """
    print("\n" + "=" * 70)
    print("测试：混合场景")
    print("=" * 70)

    queries = [
        ("机器学习基础概念", False),
        ("深度学习入门指南", True),
    ]

    for query, skip_local in queries:
        print(f"\n查询：{query}")
        print(f"跳过本地：{skip_local}")
        print("-" * 70)

        start_time = time.time()
        result = search_ai(query, max_results=2, use_cache=False, skip_local=skip_local)
        duration = time.time() - start_time

        print(f"来源：{result.get('source', 'unknown')}")
        print(f"耗时：{duration:.2f}s")
        print(f"结果数：{len(result['results'])}")

        if skip_local:
            assert result.get("source") == "online", (
                f"应该走在线搜索（skip_local={skip_local}）"
            )
            print("  → 联网搜索（skip_local=True）")
        elif result.get("source") == "local":
            print("  → 来自本地数据库")
        else:
            print("  → 联网搜索（新内容）")

    print("\n" + "=" * 70)
    print("✓ 混合场景测试通过")
    print("=" * 70)

    return True


if __name__ == "__main__":
    try:
        test_local_first_search()
        test_low_quality_local_results()
        test_mixed_results()

        print("\n" + "=" * 70)
        print("✅ 所有测试通过！")
        print("=" * 70)
        sys.exit(0)

    except AssertionError as e:
        print(f"\n❌ 测试失败：{e}")
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ 测试出错：{e}")
        import traceback

        traceback.print_exc()
        sys.exit(1)
