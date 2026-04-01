import time
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from cache import is_cached, get_cached, set_cache, get_cache_stats, clear_cache
from my_ai_search.utils.exceptions import CacheException


def test_cache_set_and_get():
    """测试缓存设置和获取"""
    print("\n=== 测试1: 缓存设置和获取 ===")

    url = "https://example.com"
    html = "<html><body>Test content</body></html>"

    set_cache(url, html, title="Test Page")

    assert is_cached(url), "URL应该被缓存"
    print("✓ is_cached 正确识别已缓存的URL")

    cached = get_cached(url)
    assert cached is not None, "应该能够获取缓存内容"
    assert cached["html"] == html, "缓存的HTML应该匹配"
    assert cached["title"] == "Test Page", "缓存的标题应该匹配"
    print("✓ get_cached 正确返回缓存内容")

    print("✓ 测试1通过\n")


def test_cache_expiry():
    """测试缓存过期"""
    print("=== 测试2: 缓存过期 ===")

    url = "https://example2.com"
    html = "<html><body>Expiring content</body></html>"

    set_cache(url, html, ttl=1)

    assert is_cached(url), "URL应该被缓存"
    print("✓ URL已缓存")

    time.sleep(2)

    assert not is_cached(url), "缓存应该过期"
    print("✓ 缓存已过期")

    cached = get_cached(url)
    assert cached is None, "过期缓存应该返回None"
    print("✓ 过期缓存返回None")

    print("✓ 测试2通过\n")


def test_cache_stats():
    """测试缓存统计"""
    print("=== 测试3: 缓存统计 ===")

    clear_cache()

    set_cache("https://test1.com", "<html>test1</html>")
    set_cache("https://test2.com", "<html>test2</html>")

    get_cached("https://test1.com")
    get_cached("https://test1.com")
    get_cached("https://test2.com")

    get_cached("https://not-cached.com")

    stats = get_cache_stats()

    print(
        f"缓存统计: 命中={stats['hits']}, 未命中={stats['misses']}, 命中率={stats['hit_rate']:.2%}, 总条目={stats['total']}"
    )

    assert stats["hits"] >= 2, "应该有至少2次缓存命中"
    assert stats["misses"] >= 1, "应该有至少1次缓存未命中"
    assert stats["total"] == 2, "应该有2个缓存条目"
    print("✓ 缓存统计正确")

    print("✓ 测试3通过\n")


def test_clear_cache():
    """测试清空缓存"""
    print("=== 测试4: 清空缓存 ===")

    set_cache("https://test.com", "<html>test</html>")
    assert is_cached("https://test.com"), "URL应该被缓存"
    print("✓ URL已缓存")

    clear_cache()

    assert not is_cached("https://test.com"), "缓存应该被清空"
    print("✓ 缓存已清空")

    stats = get_cache_stats()
    assert stats["total"] == 0, "缓存条目数应该为0"
    assert stats["hits"] == 0, "命中次数应该重置"
    assert stats["misses"] == 0, "未命中次数应该重置"
    print("✓ 统计信息已重置")

    print("✓ 测试4通过\n")


def test_empty_url():
    """测试空URL处理"""
    print("=== 测试5: 空URL处理 ===")

    result = is_cached("")
    assert result is False, "空URL应该返回False"
    print("✓ is_cached 正确处理空URL")

    result = is_cached("   ")
    assert result is False, "空白URL应该返回False"
    print("✓ is_cached 正确处理空白URL")

    cached = get_cached("")
    assert cached is None, "空URL应该返回None"
    print("✓ get_cached 正确处理空URL")

    print("✓ 测试5通过\n")


def test_empty_html():
    """测试空HTML处理"""
    print("=== 测试6: 空HTML处理 ===")

    url = "https://example3.com"

    set_cache(url, "", title="Empty HTML")
    assert not is_cached(url), "空HTML不应该被缓存"
    print("✓ set_cache 正确拒绝空HTML")

    set_cache(url, "   ", title="Whitespace HTML")
    assert not is_cached(url), "空白HTML不应该被缓存"
    print("✓ set_cache 正确拒绝空白HTML")

    print("✓ 测试6通过\n")


def test_duplicate_url():
    """测试重复URL更新"""
    print("=== 测试7: 重复URL更新 ===")

    url = "https://example4.com"

    set_cache(url, "<html>First version</html>", title="V1")
    cached = get_cached(url)
    assert cached["html"] == "<html>First version</html>", "应该获取第一版内容"
    print("✓ 第一版内容已缓存")

    set_cache(url, "<html>Second version</html>", title="V2")
    cached = get_cached(url)
    assert cached["html"] == "<html>Second version</html>", "应该获取第二版内容"
    assert cached["title"] == "V2", "应该获取第二版标题"
    print("✓ 第二版内容已更新")

    stats = get_cache_stats()
    assert stats["total"] == 1, "重复URL应该更新而非新增"
    print("✓ 重复URL正确更新")

    print("✓ 测试7通过\n")


def test_special_characters_in_url():
    """测试URL中特殊字符"""
    print("=== 测试8: URL中特殊字符 ===")

    url = "https://example.com/path?param=value&other=test#section"

    set_cache(url, "<html>Special chars</html>", title="Special URL")
    assert is_cached(url), "特殊字符URL应该被缓存"
    print("✓ 特殊字符URL已缓存")

    cached = get_cached(url)
    assert cached is not None, "应该能够获取缓存内容"
    assert cached["html"] == "<html>Special chars</html>", "缓存内容应该匹配"
    print("✓ 特殊字符URL缓存内容正确")

    print("✓ 测试8通过\n")


def test_long_content():
    """测试长内容缓存"""
    print("=== 测试9: 长内容缓存 ===")

    url = "https://example5.com"
    long_html = "<html><body>" + "Test content " * 1000 + "</body></html>"

    set_cache(url, long_html, title="Long Content")
    assert is_cached(url), "长内容应该被缓存"
    print("✓ 长内容已缓存")

    cached = get_cached(url)
    assert cached is not None, "应该能够获取长内容"
    assert len(cached["html"]) == len(long_html), "长内容应该完整缓存"
    print("✓ 长内容完整缓存")

    print("✓ 测试9通过\n")


def run_all_tests():
    """运行所有测试"""
    print("=" * 50)
    print("开始测试Cache模块")
    print("=" * 50)

    try:
        test_cache_set_and_get()
        test_cache_expiry()
        test_cache_stats()
        test_clear_cache()
        test_empty_url()
        test_empty_html()
        test_duplicate_url()
        test_special_characters_in_url()
        test_long_content()

        print("=" * 50)
        print("✅ 所有测试通过!")
        print("=" * 50)

    except AssertionError as e:
        print(f"\n❌ 测试失败: {e}")
        import traceback

        traceback.print_exc()
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ 测试出错: {e}")
        import traceback

        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    run_all_tests()
