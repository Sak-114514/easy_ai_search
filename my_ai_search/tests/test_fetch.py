import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from fetch.fetch import (
    fetch_page_sync,
    close_browser,
    enable_requests_mode,
    _looks_like_shell_page,
    _looks_like_video_page,
    _looks_like_listing_or_sparse_page,
    _should_skip_browser_fallback,
    _should_skip_requests_fallback,
)
from utils.exceptions import FetchException
import asyncio

# 启用 requests 模式以避免 LightPanda 连接问题
enable_requests_mode()


def test_fetch_normal_page():
    """测试1：正常页面抓取"""
    print("Test 1: Fetching normal page")

    result = fetch_page_sync("https://www.python.org")

    print(f"Success: {result['success']}")
    print(f"Title: {result['title']}")
    print(f"HTML length: {len(result['html'])}")

    assert result["success"], "Should succeed"
    assert "Python" in result["title"], "Title should contain 'Python'"
    assert len(result["html"]) > 0, "HTML should not be empty"

    print("✓ Test 1 passed\n")


def test_fetch_invalid_url():
    """测试2：无效URL处理"""
    print("Test 2: Handling invalid URL")

    result = fetch_page_sync("https://this-site-does-not-exist-12345.com")

    print(f"Success: {result['success']}")
    print(f"Error: {result['error']}")

    assert not result["success"], "Should fail"
    assert result["error"], "Should have error message"

    print("✓ Test 2 passed\n")


def test_fetch_empty_url():
    """测试3：空URL处理"""
    print("Test 3: Handling empty URL")

    try:
        fetch_page_sync("")
        assert False, "Should raise FetchException"
    except FetchException as e:
        print(f"Correctly caught error: {e}")
        assert "URL cannot be empty" in str(e)

    print("✓ Test 3 passed\n")


def test_fetch_with_timeout():
    """测试4：自定义超时"""
    print("Test 4: Fetching with custom timeout")

    result = fetch_page_sync("https://www.python.org", timeout=5)

    print(f"Success: {result['success']}")

    assert result["success"], "Should succeed with custom timeout"

    print("✓ Test 4 passed\n")


def test_shell_page_detection():
    html = """
    <html><body>
      <h1>Browser not supported</h1>
      <p>Your browser does not support the security verification required.</p>
    </body></html>
    """

    assert _looks_like_shell_page("Browser not supported", html) is True
    assert _should_skip_browser_fallback(
        "https://help.openai.com/article/test", html, "Browser not supported"
    ) is True
    assert _should_skip_requests_fallback(
        "https://help.openai.com/article/test",
        html,
        "Browser not supported",
        error="RobotsBlocked",
    ) is True


def test_video_page_detection():
    html = """
    <html><body>
      <div>视频</div>
      <div>播放</div>
      <div>弹幕</div>
    </body></html>
    """

    assert _looks_like_video_page(
        "https://www.bilibili.com/video/BV1xxxx", "", html
    ) is True
    assert _should_skip_browser_fallback(
        "https://haokan.baidu.com/v?vid=123", html, ""
    ) is True


def test_listing_page_detection():
    html = """
    <html><body>
      <div>相关推荐</div>
      <div>最新文章</div>
    </body></html>
    """

    assert _looks_like_listing_or_sparse_page(
        "https://example.com/category/ai", "AI 分类", html
    ) is True
    assert _should_skip_requests_fallback(
        "https://example.com/category/ai", html, "AI 分类"
    ) is True


def cleanup():
    """清理资源"""
    print("Cleaning up...")
    close_browser()


if __name__ == "__main__":
    try:
        test_fetch_normal_page()
        test_fetch_invalid_url()
        test_fetch_empty_url()
        test_fetch_with_timeout()

        print("=" * 50)
        print("All tests passed!")
        print("=" * 50)
    except Exception as e:
        print(f"\nTest failed with error: {e}")
        import traceback

        traceback.print_exc()
    finally:
        cleanup()
