import pytest
from deep_process import (
    assess_quality,
    deep_process_content,
    detect_duplicates,
    estimate_query_relevance,
    extract_key_info,
    generate_summary,
    select_deep_process_candidates,
)


def test_generate_summary_short_text():
    """测试短文本摘要生成"""
    text = "Python是一门高级编程语言。"
    summary = generate_summary(text)
    assert len(summary) > 0
    assert "Python" in summary


def test_generate_summary_long_text():
    """测试长文本摘要生成"""
    text = (
        "Python是一门高级编程语言。Python具有简洁清晰的语法，易于学习。"
        "Python支持多种编程范式，包括面向对象、命令式、函数式和过程式编程。"
        "Python广泛应用于Web开发、数据科学、人工智能等领域。"
    )
    summary = generate_summary(text, max_length=100)
    assert len(summary) > 0
    assert len(summary) <= 100
    assert "Python" in summary


def test_generate_summary_empty_text():
    """测试空文本摘要生成"""
    summary = generate_summary("")
    assert summary == ""


def test_assess_quality_good_text():
    """测试高质量文本评估"""
    good_text = (
        "Python是一门高级编程语言，具有简洁清晰的语法。"
        "它支持多种编程范式，被广泛应用于Web开发、数据科学和人工智能等领域。"
    )
    quality = assess_quality(good_text)
    assert quality["overall_score"] > 0.5
    assert quality["is_valid"]
    assert "readability" in quality
    assert "length_score" in quality
    assert "content_score" in quality


def test_assess_quality_bad_text():
    """测试低质量文本评估"""
    bad_text = "测试测试测试测试测试"
    quality = assess_quality(bad_text)
    assert quality["overall_score"] < 0.5
    assert not quality["is_valid"]


def test_assess_quality_empty_text():
    """测试空文本质量评估"""
    quality = assess_quality("")
    assert quality["overall_score"] == 0.0
    assert not quality["is_valid"]


def test_detect_duplicates_exact():
    """测试精确重复检测"""
    chunks = [
        {"text": "Python是一门编程语言", "chunk_id": 0, "url": "https://test.com"},
        {"text": "Python是一门编程语言", "chunk_id": 1, "url": "https://test.com"},
        {"text": "Java也是一门编程语言", "chunk_id": 2, "url": "https://test.com"},
    ]
    result = detect_duplicates(chunks, similarity_threshold=1.0)
    assert len(result["duplicate_ids"]) == 1
    assert len(result["keep_ids"]) == 2


def test_detect_duplicates_near():
    """测试近似重复检测"""
    chunks = [
        {"text": "Python是一门编程语言", "chunk_id": 0, "url": "https://test.com"},
        {
            "text": "Python是一门非常流行的编程语言",
            "chunk_id": 1,
            "url": "https://test.com",
        },
        {"text": "Java也是一门编程语言", "chunk_id": 2, "url": "https://test.com"},
    ]
    result = detect_duplicates(chunks, similarity_threshold=0.7)
    assert len(result["duplicate_ids"]) >= 1
    assert len(result["keep_ids"]) >= 2


def test_detect_duplicates_empty():
    """测试空列表重复检测"""
    result = detect_duplicates([])
    assert result["duplicate_ids"] == []
    assert result["keep_ids"] == []
    assert result["mapping"] == {}


def test_extract_key_info():
    """测试关键信息提取"""
    text = (
        "Python是一门编程语言。Python广泛应用于Web开发和数据科学。"
        "Python具有简洁的语法。"
    )
    info = extract_key_info(text)
    assert "keywords" in info
    assert "sentences_count" in info
    assert "word_count" in info
    assert info["sentences_count"] > 0
    assert info["word_count"] > 0


def test_extract_key_info_empty():
    """测试空文本关键信息提取"""
    info = extract_key_info("")
    assert info["keywords"] == []
    assert info["sentences_count"] == 0
    assert info["word_count"] == 0


def test_deep_process_full():
    """测试完整深度处理流程"""
    chunks = [
        {
            "text": (
                "Python是一门高级编程语言，具有简洁清晰的语法。"
                "它支持多种编程范式，被广泛应用于Web开发、数据科学和人工智能等领域。"
            ),
            "chunk_id": 0,
            "url": "https://python.org",
            "metadata": {},
        },
        {
            "text": (
                "Python是一门高级编程语言，具有简洁清晰的语法。"
                "它支持多种编程范式，被广泛应用于Web开发、数据科学和人工智能等领域。"
            ),
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
    assert processed[0]["quality_score"] > 0.5
    assert not processed[0]["is_duplicate"]


def test_deep_process_empty():
    """测试空输入处理"""
    result = deep_process_content([])
    assert result == []

    result = deep_process_content([{"text": "", "chunk_id": 0}])
    assert len(result) == 0


def test_deep_process_only_summary():
    """测试仅生成摘要"""
    chunks = [
        {
            "text": "Python是一门高级编程语言。它支持多种编程范式。",
            "chunk_id": 0,
            "url": "https://python.org",
            "metadata": {},
        }
    ]

    processed = deep_process_content(
        chunks, enable_summary=True, enable_dedup=False, enable_quality_check=False
    )

    assert len(processed) == 1
    assert "summary" in processed[0]
    assert processed[0]["summary"] != ""


def test_deep_process_only_quality():
    """测试仅质量检查"""
    chunks = [
        {
            "text": "Python是一门高级编程语言。它支持多种编程范式。",
            "chunk_id": 0,
            "url": "https://python.org",
            "metadata": {},
        }
    ]

    processed = deep_process_content(
        chunks, enable_summary=False, enable_dedup=False, enable_quality_check=True
    )

    assert len(processed) == 1
    assert "quality_score" in processed[0]
    assert "quality_details" in processed[0]


def test_deep_process_low_quality_filter():
    """测试低质量内容过滤"""
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

    processed = deep_process_content(
        chunks, enable_summary=False, enable_dedup=False, enable_quality_check=True
    )

    assert len(processed) == 1
    assert processed[0]["chunk_id"] == 0


def test_estimate_query_relevance_prefers_matching_title_and_snippet():
    chunk = {
        "text": "这是一段介绍 GPT-5.4 mini 发布情况的正文内容。",
        "snippet": "GPT-5.4 mini 正式发布",
        "chunk_id": 0,
        "url": "https://openai.com/post",
        "metadata": {
            "title": "OpenAI GPT-5.4 mini 发布",
            "source_url": "https://openai.com/post",
        },
    }
    unrelated = {
        "text": "今天分享家常红烧肉的做法与技巧。",
        "snippet": "红烧肉教程",
        "chunk_id": 1,
        "url": "https://cook.example.com",
        "metadata": {
            "title": "红烧肉教程",
            "source_url": "https://cook.example.com",
        },
    }

    assert estimate_query_relevance("GPT-5.4 mini 发布", chunk) > estimate_query_relevance(
        "GPT-5.4 mini 发布", unrelated
    )


def test_select_deep_process_candidates_prefers_relevant_chunks():
    chunks = [
        {
            "text": "这是关于 Python asyncio 最佳实践的正文。",
            "snippet": "Python asyncio 最佳实践",
            "chunk_id": 0,
            "url": "https://example.com/python",
            "metadata": {
                "title": "Python asyncio 最佳实践",
                "source_url": "https://example.com/python",
            },
        },
        {
            "text": "这是一篇关于家常菜做法的文章。",
            "snippet": "家常菜",
            "chunk_id": 1,
            "url": "https://example.com/cook",
            "metadata": {
                "title": "家常菜",
                "source_url": "https://example.com/cook",
            },
        },
        {
            "text": "asyncio 中的任务调度、取消与超时控制。",
            "snippet": "任务调度与取消",
            "chunk_id": 2,
            "url": "https://example.com/asyncio",
            "metadata": {
                "title": "任务调度与取消",
                "source_url": "https://example.com/asyncio",
            },
        },
    ]

    selected = select_deep_process_candidates(
        chunks,
        query="Python asyncio 最佳实践",
        max_candidates=2,
    )

    selected_ids = {chunk["chunk_id"] for chunk in selected}
    assert selected_ids == {0, 2}


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
