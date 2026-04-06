from unittest.mock import patch

from my_ai_search.search.intent_provider import (
    _classify_with_rules,
    _merge_with_rule_plan,
    _parse_intent_json,
    get_search_intent,
)


def test_rule_intent_classifies_news():
    result = _classify_with_rules("OpenAI GPT-5.4 mini 发布信息")
    assert result["intent"] == "news"
    assert "官方" in result["rewrite_query"]


def test_rule_intent_classifies_howto():
    result = _classify_with_rules("家常红烧肉做法和技巧")
    assert result["intent"] == "howto"
    assert "步骤" in result["rewrite_query"]


def test_parse_intent_json_extracts_structured_fields():
    payload = """
    {
      "intent": "technical",
      "confidence": 0.91,
      "rewrite_query": "Redis 持久化机制对比 官方文档 教程 最佳实践",
      "preferred_sources": ["official_docs", "tutorial"],
      "avoid_page_types": ["repo_list", "comment_thread"],
      "max_results_per_domain": 2
    }
    """
    result = _parse_intent_json(payload)
    assert result["intent"] == "technical"
    assert result["confidence"] == 0.91
    assert result["max_results_per_domain"] == 2


def test_get_search_intent_lmstudio_fallbacks_to_rules(monkeypatch):
    monkeypatch.setenv("SEARCH_INTENT_BACKEND", "lmstudio")
    with patch("my_ai_search.search.intent_provider.requests.post", side_effect=RuntimeError("boom")):
        result = get_search_intent("Redis 持久化机制对比")
    assert result["intent"] == "technical"


def test_merge_with_rule_plan_rejects_vague_general_output():
    rule_plan = _classify_with_rules("家常红烧肉做法和技巧")
    llm_plan = {
        "intent": "general",
        "confidence": 0.95,
        "rewrite_query": "how_to 详解",
        "preferred_sources": ["recipe"],
        "avoid_page_types": ["video"],
        "max_results_per_domain": 1,
    }
    result = _merge_with_rule_plan("家常红烧肉做法和技巧", llm_plan, rule_plan)
    assert result["intent"] == "howto"
    assert "步骤" in result["rewrite_query"]


def test_merge_with_rule_plan_filters_invalid_strategy_fields():
    rule_plan = _classify_with_rules("OpenAI GPT-5.4 mini 发布信息")
    llm_plan = {
        "intent": "news",
        "confidence": 0.88,
        "rewrite_query": "OpenAI GPT-5.4 mini release",
        "preferred_sources": ["https://openai.com/news/", "news"],
        "avoid_page_types": ["blog", "captcha"],
        "max_results_per_domain": 3,
    }
    result = _merge_with_rule_plan("OpenAI GPT-5.4 mini 发布信息", llm_plan, rule_plan)
    assert result["intent"] == "news"
    assert result["preferred_sources"] == ["news"]
    assert result["avoid_page_types"] == ["captcha"]
    assert result["max_results_per_domain"] == 3
