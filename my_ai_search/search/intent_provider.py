import json
import os
import re

import requests

from my_ai_search.utils.logger import setup_logger
from my_ai_search.utils.openai_client import (
    extract_openai_content,
    normalize_openai_compatible_url,
)

logger = setup_logger("intent_provider")

_VALID_INTENTS = {"technical", "news", "howto", "explanation", "general"}
_VALID_PREFERRED_SOURCES = {
    "official",
    "news",
    "tech_media",
    "official_docs",
    "tutorial",
    "tech_blog",
    "guide",
    "recipe",
    "reference",
    "education",
    "science_media",
    "general_web",
}
_VALID_AVOID_PAGE_TYPES = {
    "captcha",
    "repo_list",
    "comment_thread",
    "video",
}


def get_search_intent(query: str) -> dict:
    """获取搜索意图，优先走外部 LLM，失败时回退规则分类。"""
    rule_plan = _classify_with_rules(query)
    backend = (os.getenv("SEARCH_INTENT_BACKEND") or "rule").lower()
    api_url = os.getenv("SEARCH_INTENT_API_URL") or "http://127.0.0.1:1234"
    model = os.getenv("SEARCH_INTENT_MODEL") or "qwen3.5"
    timeout = float(os.getenv("SEARCH_INTENT_TIMEOUT") or "2.0")

    if backend in ("lmstudio", "openai_compatible"):
        try:
            result = _classify_with_openai_compatible(
                query=query,
                api_url=api_url,
                model=model,
                timeout=timeout,
            )
            if result:
                return _merge_with_rule_plan(query, result, rule_plan)
        except Exception as e:
            logger.warning(f"Intent provider failed, fallback to rules: {e}")

    return rule_plan


def _classify_with_openai_compatible(
    query: str, api_url: str, model: str, timeout: float
) -> dict:
    endpoint = normalize_openai_compatible_url(api_url)
    payload = {
        "model": model,
        "temperature": 0,
        "max_tokens": 220,
        "messages": [
            {
                "role": "system",
                "content": (
                    "你是搜索意图路由器。请只输出 JSON，不要输出额外解释。"
                    "字段固定为: intent, confidence, rewrite_query, preferred_sources, "
                    "avoid_page_types, max_results_per_domain。"
                    'intent 只能是 technical/news/howto/explanation/general。'
                    "preferred_sources 和 avoid_page_types 必须是字符串数组。"
                    "max_results_per_domain 必须是 1 到 3 的整数。"
                ),
            },
            {
                "role": "user",
                "content": f"请判断这个搜索请求的检索意图并返回 JSON: {query}",
            },
        ],
    }

    response = requests.post(endpoint, json=payload, timeout=timeout)
    response.raise_for_status()
    data = response.json()
    content = extract_openai_content(data)
    parsed = _parse_intent_json(content)
    if not parsed:
        raise ValueError("invalid intent JSON")
    return parsed


def _classify_with_rules(query: str) -> dict:
    query_lower = query.lower()

    categories = {
        "news": ["发布", "公告", "最新", "消息", "release", "news"],
        "howto": ["怎么", "如何", "步骤", "教程", "做法", "指南", "菜谱", "评测", "续航"],
        "explanation": ["为什么", "原理", "解释", "通俗", "是什么", "区别", "量子", "黑洞"],
        "technical": ["机制", "架构", "对比", "最佳实践", "实现", "性能", "调优", "mvcc", "taskgroup", "asyncio"],
    }
    scores = {key: 0 for key in categories}
    for intent, words in categories.items():
        for word in words:
            if word in query_lower:
                scores[intent] += 2 if len(word) > 1 else 1

    if "?" in query or "？" in query:
        scores["explanation"] += 1

    intent = max(scores, key=scores.get)
    if scores[intent] == 0:
        intent = "general"

    result = {"intent": intent, "confidence": 0.65 if intent != "general" else 0.4}
    result.update(_defaults_for_intent(intent, query))
    return result


def _parse_intent_json(content: str) -> dict:
    if not content:
        return {}

    match = re.search(r"\{.*\}", content, re.S)
    if not match:
        return {}

    try:
        data = json.loads(match.group(0))
    except json.JSONDecodeError:
        return {}

    intent = str(data.get("intent", "general")).lower()
    if intent not in _VALID_INTENTS:
        intent = "general"

    preferred_sources = data.get("preferred_sources") or []
    avoid_page_types = data.get("avoid_page_types") or []
    if not isinstance(preferred_sources, list) or not isinstance(avoid_page_types, list):
        return {}

    confidence = float(data.get("confidence", 0.5))
    max_results_per_domain = int(data.get("max_results_per_domain", 2))
    max_results_per_domain = max(1, min(3, max_results_per_domain))

    rewrite_query = str(data.get("rewrite_query") or "").strip()
    if not rewrite_query:
        rewrite_query = _classify_with_rules(data.get("intent", "")).get("rewrite_query", "")

    return {
        "intent": intent,
        "confidence": max(0.0, min(1.0, confidence)),
        "rewrite_query": rewrite_query,
        "preferred_sources": [str(item) for item in preferred_sources if str(item).strip()],
        "avoid_page_types": [str(item) for item in avoid_page_types if str(item).strip()],
        "max_results_per_domain": max_results_per_domain,
    }

def _merge_with_rule_plan(query: str, llm_plan: dict, rule_plan: dict) -> dict:
    intent = str(llm_plan.get("intent") or "general").lower()
    confidence = float(llm_plan.get("confidence", 0.0))

    if intent not in _VALID_INTENTS:
        return rule_plan

    # 外部模型如果只给出模糊 general，优先保留规则版的明确分类，避免质量退化。
    if intent == "general" and rule_plan.get("intent") != "general":
        return rule_plan

    merged = dict(rule_plan if intent == "general" else _defaults_for_intent(intent, query))
    merged["intent"] = intent
    merged["confidence"] = max(0.0, min(1.0, confidence)) if confidence else merged["confidence"]

    rewrite_query = str(llm_plan.get("rewrite_query") or "").strip()
    if _is_valid_rewrite_query(rewrite_query):
        merged["rewrite_query"] = rewrite_query

    preferred_sources = [
        str(item).strip().lower()
        for item in (llm_plan.get("preferred_sources") or [])
        if str(item).strip().lower() in _VALID_PREFERRED_SOURCES
    ]
    if preferred_sources:
        merged["preferred_sources"] = preferred_sources

    avoid_page_types = [
        str(item).strip().lower()
        for item in (llm_plan.get("avoid_page_types") or [])
        if str(item).strip().lower() in _VALID_AVOID_PAGE_TYPES
    ]
    if avoid_page_types:
        merged["avoid_page_types"] = avoid_page_types

    try:
        max_results_per_domain = int(llm_plan.get("max_results_per_domain", merged["max_results_per_domain"]))
    except (TypeError, ValueError):
        max_results_per_domain = merged["max_results_per_domain"]
    merged["max_results_per_domain"] = max(1, min(3, max_results_per_domain))
    return merged


def _defaults_for_intent(intent: str, query: str) -> dict:
    defaults = {
        "technical": {
            "preferred_sources": ["official_docs", "tutorial", "tech_blog"],
            "avoid_page_types": ["repo_list", "comment_thread", "video"],
            "rewrite_query": f"{query} 官方文档 教程 最佳实践",
            "max_results_per_domain": 2,
        },
        "news": {
            "preferred_sources": ["official", "news", "tech_media"],
            "avoid_page_types": ["captcha", "repo_list", "comment_thread", "video"],
            "rewrite_query": f"{query} 官方 公告 详解",
            "max_results_per_domain": 2,
        },
        "howto": {
            "preferred_sources": ["guide", "tutorial", "recipe"],
            "avoid_page_types": ["video", "comment_thread", "repo_list"],
            "rewrite_query": f"{query} 步骤 图文 教程",
            "max_results_per_domain": 2,
        },
        "explanation": {
            "preferred_sources": ["reference", "education", "science_media"],
            "avoid_page_types": ["repo_list", "comment_thread", "video"],
            "rewrite_query": f"{query} 原理 通俗解释",
            "max_results_per_domain": 2,
        },
        "general": {
            "preferred_sources": ["general_web"],
            "avoid_page_types": ["captcha", "video"],
            "rewrite_query": f"{query} 详解",
            "max_results_per_domain": 2,
        },
    }
    return defaults[intent]


def _is_valid_rewrite_query(rewrite_query: str) -> bool:
    if not rewrite_query or len(rewrite_query) < 4:
        return False
    lowered = rewrite_query.lower()
    if "http://" in lowered or "https://" in lowered:
        return False
    return "technical/news/howto/explanation/general" not in lowered
