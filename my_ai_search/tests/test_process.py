"""
测试处理层（process模块）
"""

import sys
import pytest
from process.process import (
    process_content,
    clean_html,
    chunk_text,
    limit_chunks_per_page,
    normalize_text,
    _strip_template_noise,
    _is_template_shell,
    _should_skip_readability,
    get_token_count,
)
from my_ai_search.utils.logger import setup_logger
import my_ai_search.process.process as process_module

logger = setup_logger("test_process")


@pytest.fixture(autouse=True)
def _force_bs4_cleaner(monkeypatch):
    def _raise_readability_error(_html):
        raise RuntimeError("force bs4 fallback in unit tests")

    monkeypatch.setattr(process_module, "_extract_with_readability", _raise_readability_error)


def test_clean_html():
    """测试HTML清洗功能"""
    print("\n=== 测试1: HTML清洗 ===")

    html = """
    <html>
    <head><title>Test</title></head>
    <body>
        <nav>This is navigation</nav>
        <div class="ad">This is an ad</div>
        <div class="content">
            <p>This is main content.</p>
            <script>alert('hello');</script>
        </div>
    </body>
    </html>
    """

    cleaned = clean_html(html)
    print(f"清洗后的文本: {cleaned}")

    assert "navigation" not in cleaned, "导航栏应该被移除"
    assert "ad" not in cleaned, "广告应该被移除"
    assert "alert" not in cleaned, "脚本应该被移除"
    assert "main content" in cleaned, "主要内容应该保留"

    print("✅ HTML清洗测试通过")
    return True


def test_chunk_text():
    """测试文本分块功能"""
    print("\n=== 测试2: 文本分块 ===")

    text = "Python " * 1000
    tokens = get_token_count(text)
    print(f"总token数: {tokens}")

    chunks = chunk_text(text, chunk_size=512, overlap=50)
    print(f"分块数量: {len(chunks)}")
    print(f"第一个块长度: {len(chunks[0])}")
    print(f"第一个块token数: {get_token_count(chunks[0])}")

    assert len(chunks) > 1, "应该生成多个分块"
    assert all(len(c) > 0 for c in chunks), "所有分块都不应为空"

    print("✅ 文本分块测试通过")
    return True


def test_normalize_text():
    """测试文本规范化功能"""
    print("\n=== 测试3: 文本规范化 ===")

    text = "  Hello   World!  \n\n  测试文本  "
    normalized = normalize_text(text)
    print(f"规范化前: '{text}'")
    print(f"规范化后: '{normalized}'")

    assert "  " not in normalized, "多余的空格应该被移除"
    assert normalized == "Hello World! \n\n 测试文本", "文本应该被正确规范化"

    print("✅ 文本规范化测试通过")
    return True


def test_process_content():
    """测试完整处理流程"""
    print("\n=== 测试4: 完整处理流程 ===")

    html = (
        """
    <html>
    <body>
        <h1>Python Tutorial</h1>
        <p>Python is a great programming language. """
        + ("Hello Python. " * 100)
        + """</p>
    </body>
    </html>
    """
    )

    results = process_content(html, url="https://example.com")
    print(f"处理后的分块数: {len(results)}")

    assert len(results) > 0, "应该生成分块"
    assert all("text" in r for r in results), "每个结果都应该包含text字段"
    assert all("chunk_id" in r for r in results), "每个结果都应该包含chunk_id字段"
    assert all("url" in r for r in results), "每个结果都应该包含url字段"
    assert results[0]["url"] == "https://example.com", "URL应该被正确设置"

    print("✅ 完整处理流程测试通过")
    return True


def test_empty_html():
    """测试空HTML处理"""
    print("\n=== 测试5: 空HTML处理 ===")

    results = process_content("")
    assert results == [], "空HTML应该返回空列表"

    results = process_content("<html><body></body></html>")
    assert len(results) == 0, "没有内容的HTML应该返回空列表"

    print("✅ 空HTML处理测试通过")
    return True


def test_get_token_count():
    """测试token计数功能"""
    print("\n=== 测试6: Token计数 ===")

    text = "Hello world!"
    tokens = get_token_count(text)
    print(f"'{text}' 的token数: {tokens}")

    assert tokens > 0, "token数应该大于0"

    long_text = "Python " * 100
    long_tokens = get_token_count(long_text)
    print(f"长文本的token数: {long_tokens}")

    assert long_tokens > tokens, "长文本的token数应该更多"

    print("✅ Token计数测试通过")
    return True


def test_ad_removal():
    """测试广告移除功能"""
    print("\n=== 测试7: 广告移除 ===")

    html = """
    <html>
    <body>
        <div class="advertisement">This is an advertisement</div>
        <div class="banner">This is a banner</div>
        <div class="content">This is real content</div>
        <div class="popup">This is a popup</div>
    </body>
    </html>
    """

    cleaned = clean_html(html)
    print(f"清洗后: {cleaned}")

    assert "advertisement" not in cleaned.lower(), "advertisement应该被移除"
    assert "banner" not in cleaned.lower(), "banner应该被移除"
    assert "popup" not in cleaned.lower(), "popup应该被移除"
    assert "real content" in cleaned, "真实内容应该保留"

    print("✅ 广告移除测试通过")
    return True


def test_main_content_extraction():
    """测试主要内容提取"""
    print("\n=== 测试8: 主要内容提取 ===")

    html = """
    <html>
    <body>
        <nav>Navigation</nav>
        <aside>Sidebar</aside>
        <article>
            <h1>Main Article</h1>
            <p>This is the main article content.</p>
        </article>
        <footer>Footer</footer>
    </body>
    </html>
    """

    cleaned = clean_html(html)
    print(f"提取的内容: {cleaned}")

    assert "Main Article" in cleaned, "文章标题应该被提取"
    assert "main article content" in cleaned, "文章内容应该被提取"
    assert "Navigation" not in cleaned, "导航应该被移除"
    assert "Sidebar" not in cleaned, "侧边栏应该被移除"
    assert "Footer" not in cleaned, "页脚应该被移除"

    print("✅ 主要内容提取测试通过")
    return True


def test_strip_template_noise_removes_shell_lines():
    text = """OpenAI 推出了 GPT-5.4 mini 模型
No Result
View All Result
Sign in to your account
该模型在推理和多模态理解方面表现更强。"""

    cleaned = _strip_template_noise(text)

    assert "No Result" not in cleaned
    assert "View All Result" not in cleaned
    assert "Sign in" not in cleaned
    assert "OpenAI 推出了 GPT-5.4 mini 模型" in cleaned
    assert "该模型在推理和多模态理解方面表现更强。" in cleaned


def test_is_template_shell_detects_shell_page():
    text = """Just a moment
View All Result
Sign in to your account
Community
Documentation"""

    assert _is_template_shell(text) is True


def test_process_content_skips_template_shell_page():
    html = """
    <html>
      <body>
        <div>Just a moment...</div>
        <div>View All Result</div>
        <div>Sign in to your account</div>
        <div>Community</div>
        <div>Documentation</div>
      </body>
    </html>
    """

    results = process_content(html, url="https://example.com/challenge")
    assert results == []


def test_should_skip_readability_for_challenge_html():
    html = """
    <html>
      <body>
        <div>Browser not supported</div>
        <div>Your browser does not support the security verification required.</div>
      </body>
    </html>
    """

    assert _should_skip_readability(html) is True


def test_limit_chunks_per_page_preserves_head_middle_tail():
    """测试长页面分块采样覆盖头中尾"""
    chunks = [f"chunk-{i}" for i in range(30)]

    limited, indices = limit_chunks_per_page(
        chunks, max_chunks=10, head_chunks=3, tail_chunks=2
    )

    assert len(limited) == 10
    assert indices[:3] == [0, 1, 2]
    assert indices[-2:] == [28, 29]
    assert any(10 <= idx <= 20 for idx in indices), "中间段应该被保留"


def test_process_content_applies_sampling_metadata(monkeypatch):
    """测试 process_content 对超长页面应用采样元数据"""
    monkeypatch.setenv("TEXT_CHUNK_SIZE", "40")
    monkeypatch.setenv("TEXT_OVERLAP", "0")
    monkeypatch.setenv("TEXT_MAX_CHUNKS_PER_PAGE", "6")
    monkeypatch.setenv("TEXT_HEAD_CHUNKS_PER_PAGE", "2")
    monkeypatch.setenv("TEXT_TAIL_CHUNKS_PER_PAGE", "2")

    html = "<html><body><article>" + ("Python testing sentence. " * 80) + "</article></body></html>"
    results = process_content(html, url="https://example.com/long")

    assert len(results) == 6
    assert all(r["metadata"]["chunk_sampling_applied"] is True for r in results)
    assert results[0]["metadata"]["original_chunk_index"] == 0
    assert results[-1]["metadata"]["original_total_chunks"] >= 6


def run_all_tests():
    """运行所有测试"""
    print("\n" + "=" * 50)
    print("开始运行处理层所有测试...")
    print("=" * 50)

    tests = [
        test_clean_html,
        test_chunk_text,
        test_normalize_text,
        test_process_content,
        test_empty_html,
        test_get_token_count,
        test_ad_removal,
        test_main_content_extraction,
    ]

    passed = 0
    failed = 0

    for test_func in tests:
        try:
            if test_func():
                passed += 1
        except AssertionError as e:
            print(f"❌ {test_func.__name__} 失败: {e}")
            failed += 1
        except Exception as e:
            print(f"❌ {test_func.__name__} 出错: {e}")
            failed += 1

    print("\n" + "=" * 50)
    print(f"测试完成: {passed} 通过, {failed} 失败")
    print("=" * 50)

    return failed == 0


if __name__ == "__main__":
    success = run_all_tests()
    sys.exit(0 if success else 1)
