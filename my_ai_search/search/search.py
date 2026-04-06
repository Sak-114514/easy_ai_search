import time
from collections import OrderedDict

import requests

from my_ai_search.config import get_config
from my_ai_search.search.intent_provider import get_search_intent
from my_ai_search.utils.exceptions import SearchException
from my_ai_search.utils.logger import setup_logger
from my_ai_search.utils.text import extract_query_terms, normalize_domain

logger = setup_logger("search")

_SEARCH_CACHE: OrderedDict[tuple[str, str, str], tuple[float, dict]] = OrderedDict()


def _search_config():
    config = get_config()
    return getattr(config, "search", None)


def _domain_rules():
    rules = _search_config()
    if rules is None:
        return type(
            "SearchRulesFallback",
            (),
            {
                "preferred_domains": (),
                "blocked_domains": (),
                "blocked_title_patterns": (),
                "low_value_url_hints": ("/video/", "/shorts/"),
                "low_value_result_hints": (),
                "low_value_title_hints": (),
                "recipe_domains": (),
                "science_domains": (),
                "product_domains": (),
                "news_domains": (),
                "social_domains": (),
                "tech_community_domains": (),
                "cache_ttl": 300,
                "cache_max_entries": 128,
            },
        )()
    return rules


def _domain_rules_signature() -> str:
    rules = _domain_rules()
    return "|".join(
        [
            ",".join(rules.preferred_domains),
            ",".join(rules.blocked_domains),
            ",".join(rules.blocked_title_patterns),
        ]
    )


def _normalize_cache_query(query: str) -> str:
    return " ".join(query.lower().split())


def _cache_key(query: str, engines: str | None) -> tuple[str, str, str]:
    return (_normalize_cache_query(query), (engines or "").strip().lower(), _domain_rules_signature())


def _get_cached_response(query: str, engines: str | None) -> dict | None:
    config = _domain_rules()
    key = _cache_key(query, engines)
    entry = _SEARCH_CACHE.get(key)
    if entry is None:
        return None
    cached_at, payload = entry
    if time.time() - cached_at > config.cache_ttl:
        _SEARCH_CACHE.pop(key, None)
        return None
    _SEARCH_CACHE.move_to_end(key)
    return payload


def _store_cached_response(query: str, engines: str | None, payload: dict) -> None:
    config = _domain_rules()
    key = _cache_key(query, engines)
    _SEARCH_CACHE[key] = (time.time(), payload)
    _SEARCH_CACHE.move_to_end(key)
    while len(_SEARCH_CACHE) > config.cache_max_entries:
        _SEARCH_CACHE.popitem(last=False)


def search(
    query: str,
    max_results: int | None = None,
    engines: str | None = None,
    allow_second_pass: bool = True,
    intent_plan: dict | None = None,
    tool_context: dict | None = None,
) -> list[dict]:
    """
    执行搜索查询

    Args:
        query: 搜索关键词
        max_results: 最大结果数，None则使用配置默认值
        engines: 指定搜索引擎，逗号分隔，如 "bing,baidu"。None则使用全部启用引擎

    Returns:
        搜索结果列表

    Raises:
        SearchException: 搜索失败时抛出
    """
    if not query or not query.strip():
        raise SearchException("Query cannot be empty")

    config = get_config()
    actual_max_results = max_results or config.searxng.max_results

    logger.info(f"Starting search: query='{query}', max_results={actual_max_results}, engines={engines}")

    try:
        intent_plan = intent_plan or get_search_intent(query)
        # 多请求一些结果，弥补反爬网站（知乎等）被过滤后的损失
        fetch_count = actual_max_results * 3

        results = _run_search_once(
            query=query,
            fetch_count=fetch_count,
            engines=engines,
            timeout=config.searxng.timeout,
            intent_plan=intent_plan,
            tool_context=tool_context,
        )

        if allow_second_pass and _should_trigger_second_pass(results, actual_max_results):
            refined_query = _build_refined_query(query, intent_plan, tool_context)
            if refined_query != query:
                logger.info(f"Triggering second-pass search with refined query: '{refined_query}'")
                refined_results = _run_search_once(
                    query=refined_query,
                    fetch_count=fetch_count,
                    engines=engines,
                    timeout=config.searxng.timeout,
                    intent_plan=intent_plan,
                    tool_context=tool_context,
                )
                results = _merge_search_results(
                    primary_results=results,
                    refined_results=refined_results,
                    max_results=fetch_count,
                )

        if allow_second_pass and (
            _needs_recall_boost(results, actual_max_results, intent_plan)
            or _needs_source_profile_boost(results, tool_context)
        ):
            fallback_query = _build_recall_boost_query(query, intent_plan, tool_context)
            if fallback_query and fallback_query not in {query, _build_refined_query(query, intent_plan, tool_context)}:
                logger.info(f"Triggering recall-boost search with query: '{fallback_query}'")
                boosted_results = _run_search_once(
                    query=fallback_query,
                    fetch_count=fetch_count,
                    engines=engines,
                    timeout=config.searxng.timeout,
                    intent_plan=intent_plan,
                    tool_context=tool_context,
                )
                results = _merge_search_results(
                    primary_results=results,
                    refined_results=boosted_results,
                    max_results=fetch_count,
                )

        logger.info(f"Search completed: {len(results)} results found")
        return results

    except Exception as e:
        logger.error(f"Search failed: {e}")
        raise SearchException(f"Search operation failed: {e}") from e


def _call_searxng_api(query: str, params: dict) -> dict:
    """
    调用SearXNG API

    Args:
        query: 搜索查询
        params: API参数

    Returns:
        API响应JSON

    Raises:
        SearchException: API调用失败
    """
    config = get_config()
    api_url = config.searxng.api_url

    try:
        logger.debug(f"Calling SearXNG API: {api_url}")
        headers = {
            "User-Agent": (
                "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
            ),
            "Accept": "application/json",
            "Accept-Language": "en-US,en;q=0.9",
            "Content-Type": "application/x-www-form-urlencoded",
        }
        proxies = {"http": None, "https": None, "socks": None}
        response = requests.post(
            api_url,
            data=params,
            headers=headers,
            proxies=proxies,
            timeout=config.searxng.timeout,
        )
        response.raise_for_status()

        data = response.json()
        return data

    except requests.exceptions.Timeout as exc:
        raise SearchException("SearXNG API timeout") from exc
    except requests.exceptions.ConnectionError as exc:
        raise SearchException("Failed to connect to SearXNG") from exc
    except requests.exceptions.HTTPError as e:
        raise SearchException(f"SearXNG API returned HTTP {e.response.status_code}") from e
    except Exception as e:
        raise SearchException(f"Unexpected error: {e}") from e


def _parse_results(
    response: dict,
    max_results: int,
    query: str = "",
    intent_plan: dict | None = None,
    tool_context: dict | None = None,
) -> list[dict]:
    """
    解析SearXNG响应，优先返回高质量来源

    Args:
        response: API响应
        max_results: 最大结果数

    Returns:
        标准化结果列表
    """
    results_list = response.get("results", [])

    parsed_results = []
    for item in results_list:
        url = item.get("url", "").strip()
        if not url:
            continue

        title = item.get("title", "").strip()
        content = item.get("content", "").strip()

        if _should_block_result(url, title):
            logger.debug(f"Skipping blocked domain: {url}")
            continue

        quality_score = _estimate_result_quality(
            query=query,
            title=title,
            url=url,
            content=content,
            intent_plan=intent_plan,
            tool_context=tool_context,
        )
        if quality_score <= -900:
            logger.debug(f"Skipping tool-context blocked result: {url}")
            continue

        result = {
            "title": title,
            "url": url,
            "content": content,
            "score": item.get("score", 0.0),
            "_priority": quality_score,
        }
        parsed_results.append(result)

    source_profile = str((tool_context or {}).get("source_profile") or "general").strip().lower()
    max_results_per_domain = _source_profile_domain_cap(
        source_profile,
        int((intent_plan or {}).get("max_results_per_domain", 2)),
    )

    # 按质量分从高到低排序，同级保持原搜索引擎顺序
    parsed_results.sort(key=lambda x: x["_priority"], reverse=True)

    # 取 top N 并清理临时字段，同时限制同域名霸榜
    final = []
    domain_counts: dict[str, int] = {}
    for r in parsed_results:
        domain = _normalize_domain(r.get("url", ""))
        if domain_counts.get(domain, 0) >= max_results_per_domain:
            continue
        domain_counts[domain] = domain_counts.get(domain, 0) + 1
        r.pop("_priority", None)
        final.append(r)
        if len(final) >= max_results:
            break

    return final


def _retry_search(
    query: str, params: dict, timeout: float, max_retries: int = 2
) -> dict:
    """
    带重试的搜索

    Args:
        query: 搜索查询
        params: API参数
        timeout: 超时时间
        max_retries: 最大重试次数

    Returns:
        API响应

    Raises:
        SearchException: 重试后仍失败
    """
    last_exception = None

    for attempt in range(max_retries + 1):
        try:
            logger.debug(f"Search attempt {attempt + 1}/{max_retries + 1}")
            return _call_searxng_api(query, params)

        except SearchException as e:
            last_exception = e
            if attempt < max_retries:
                logger.warning(
                    f"Search attempt {attempt + 1} failed, retrying... Error: {e}"
                )
                continue
            else:
                logger.error("All search attempts failed")
                break

    raise last_exception


def _run_search_once(
    query: str,
    fetch_count: int,
    engines: str | None,
    timeout: float,
    intent_plan: dict | None = None,
    tool_context: dict | None = None,
) -> list[dict]:
    params = {"q": query, "format": "json", "language": "auto", "pageno": 1}
    if engines:
        params["engines"] = engines
    response_data = _get_cached_response(query, engines)
    if response_data is None:
        response_data = _retry_search(query, params, timeout)
        _store_cached_response(query, engines, response_data)
    return _parse_results(
        response_data,
        fetch_count,
        query=query,
        intent_plan=intent_plan,
        tool_context=tool_context,
    )


def _should_block_result(url: str, title: str) -> bool:
    rules = _domain_rules()
    url_lower = url.lower()
    title_lower = title.lower()

    for domain in rules.blocked_domains:
        if domain in url_lower:
            return True

    return any(pattern in title_lower for pattern in rules.blocked_title_patterns)


def _normalize_domain_hints(domains: list[str] | None) -> set[str]:
    normalized = set()
    for domain in domains or []:
        value = str(domain).strip().lower()
        if not value:
            continue
        normalized.add(value)
        if value.startswith("www."):
            normalized.add(value[4:])
    return normalized


def _domain_matches_hints(domain: str, hints: set[str]) -> bool:
    return any(hint and (domain == hint or domain.endswith("." + hint) or hint in domain) for hint in hints)


def _estimate_source_profile_score(domain: str, url_lower: str, title_lower: str, source_profile: str) -> float:
    rules = _domain_rules()
    profile = (source_profile or "general").strip().lower()
    score = 0.0

    if profile == "official_news":
        if any(marker in domain for marker in rules.news_domains):
            score += 4.0
        if any(marker in domain for marker in rules.social_domains):
            score -= 2.5
        if "forum" in domain or "forums." in domain:
            score -= 2.0
    elif profile == "social_realtime":
        if any(marker in domain for marker in rules.social_domains):
            score += 5.0
        if any(marker in domain for marker in rules.news_domains):
            score += 1.2
        if "wikipedia.org" in url_lower or "baike.baidu.com" in url_lower:
            score -= 1.5
    elif profile == "official_plus_social":
        if any(marker in domain for marker in rules.news_domains):
            score += 3.5
        if any(marker in domain for marker in rules.social_domains):
            score += 3.5
        if "forum" in domain or "forums." in domain:
            score -= 1.5
    elif profile == "tech_community":
        if any(marker in domain for marker in rules.tech_community_domains):
            score += 4.5
        if any(marker in domain for marker in rules.news_domains):
            score += 0.8
        if "github.com" in url_lower and any(marker in url_lower for marker in ("/issues", "/pull", "/releases")):
            score += 2.0
        if "video" in title_lower:
            score -= 2.0

    return score


def _source_profile_domain_cap(source_profile: str, default_cap: int = 2) -> int:
    profile = (source_profile or "general").strip().lower()
    if profile in {"tech_community", "social_realtime"}:
        return 1
    return default_cap


def _matches_source_profile_domain(domain: str, source_profile: str) -> bool:
    rules = _domain_rules()
    profile = (source_profile or "general").strip().lower()
    if profile == "official_news":
        return any(marker in domain for marker in rules.news_domains)
    if profile == "social_realtime":
        return any(marker in domain for marker in rules.social_domains)
    if profile == "official_plus_social":
        return any(marker in domain for marker in rules.news_domains + rules.social_domains)
    if profile == "tech_community":
        return any(marker in domain for marker in rules.tech_community_domains)
    return False


def _build_site_filter_clause(tool_context: dict | None, limit: int = 2) -> str:
    preferred_domains = list(dict.fromkeys(
        str(item).strip().lower()
        for item in (tool_context or {}).get("preferred_domains", [])
        if str(item).strip()
    ))
    site_terms = [f"site:{domain}" for domain in preferred_domains[:limit]]
    return " OR ".join(site_terms)


def _is_low_value_result(url: str, title: str, content: str = "") -> bool:
    rules = _domain_rules()
    url_lower = url.lower()
    title_lower = title.lower()
    content_lower = content.lower()

    if any(hint in url_lower for hint in rules.low_value_result_hints):
        return True
    if any(hint in title_lower for hint in rules.low_value_title_hints):
        return True
    return "github.com" in url_lower and not any(
        term in title_lower or term in content_lower
        for term in ("best practice", "guide", "tutorial", "文档", "教程", "指南")
    )


def _count_query_term_hits(query: str, text: str) -> int:
    haystack = text.lower()
    return sum(1 for term in _extract_query_terms(query) if term in haystack)


def _normalize_domain(url: str) -> str:
    return normalize_domain(url)


def _extract_query_terms(query: str) -> list[str]:
    return extract_query_terms(query)


def _looks_intent_mismatched(query: str, title: str, url: str, content: str, intent: str) -> bool:
    query_lower = query.lower()
    title_lower = title.lower()
    url_lower = url.lower()
    content_lower = content.lower()
    joined = " ".join([title_lower, url_lower, content_lower])
    term_hits = _count_query_term_hits(query, joined)
    if any(term in joined for term in ("bokep", "porn", "adult", "open enrollment", "health insurance")):
        return True

    if intent == "howto":
        recipe_terms = ("做法", "菜谱", "食材", "步骤", "下厨", "美食", "recipe", "cook")
        if any(term in query_lower for term in ("做法", "菜", "鸡丁", "红烧", "宫保", "recipe")):
            if not any(term in joined for term in recipe_terms):
                return True
            if not any(term in joined for term in ("鸡丁", "宫保", "鸡肉", "花生", "辣椒", "烹饪")):
                return True
            if term_hits == 0:
                return True
    elif intent == "explanation":
        science_terms = ("原理", "解释", "纠缠", "黑洞", "量子", "辐射", "physics", "science")
        if any(term in query_lower for term in ("为什么", "原理", "量子", "黑洞", "纠缠")):
            if not any(term in joined for term in science_terms):
                return True
            if any(term in joined for term in ("insurance", "coverage", "health plan", "open enrollment")):
                return True
            if term_hits == 0:
                return True
    elif intent == "news":
        news_terms = ("发布", "推出", "announcement", "released", "模型", "news")
        if any(term in query_lower for term in ("发布", "公告", "news", "release")):
            if not any(term in joined for term in news_terms):
                return True
            if term_hits == 0:
                return True
    elif any(term in query_lower for term in ("评测", "续航", "review", "对比")) and term_hits == 0:
        return True
    return False


def _build_refined_query(query: str, intent_plan: dict | None = None, tool_context: dict | None = None) -> str:
    if intent_plan and intent_plan.get("rewrite_query"):
        base_query = intent_plan["rewrite_query"]
    else:
        query_lower = query.lower()

        if any(term in query_lower for term in ("发布", "release", "发布信息", "公告", "news")):
            base_query = f"{query} 官方 公告 详解"
        elif any(term in query_lower for term in ("最佳实践", "asyncio", "教程", "guide", "文档", "架构")):
            base_query = f"{query} 官方文档 教程 最佳实践"
        elif any(term in query_lower for term in ("做法", "菜谱", "技巧", "红烧肉", "recipe")):
            base_query = f"{query} 做法 步骤 图文"
        elif any(term in query_lower for term in ("评测", "续航", "体验", "review")):
            base_query = f"{query} 评测 体验 实测"
        elif any(term in query_lower for term in ("为什么", "原理", "通俗", "解释")):
            base_query = f"{query} 原理 通俗 科普"
        else:
            base_query = f"{query} 详解 教程"

    source_profile = str((tool_context or {}).get("source_profile") or "general").strip().lower()
    if source_profile == "social_realtime":
        site_clause = _build_site_filter_clause(tool_context, limit=3)
        if site_clause:
            return f"{base_query} ({site_clause}) 首发 讨论"
        return f"{base_query} x twitter 微博 reddit 首发 讨论"
    if source_profile == "official_plus_social":
        site_clause = _build_site_filter_clause(tool_context, limit=3)
        if site_clause:
            return f"{base_query} 官方 ({site_clause}) 首发"
        return f"{base_query} 官方 x 微博 首发"
    if source_profile == "tech_community":
        site_clause = _build_site_filter_clause(tool_context, limit=3)
        if site_clause:
            return f"{base_query} ({site_clause}) stackoverflow github 讨论"
        return f"{base_query} stackoverflow github 讨论"
    return base_query


def _build_recall_boost_query(query: str, intent_plan: dict | None = None, tool_context: dict | None = None) -> str:
    intent = (intent_plan or {}).get("intent", "general")
    query_lower = query.lower()
    if intent == "howto":
        base_query = f"{query} 家常 做法 图文 菜谱"
    elif intent == "explanation":
        base_query = f"{query} 原理 科普 详解"
    elif intent == "news":
        base_query = f"{query} 新闻 报道 官方"
    elif intent == "technical":
        base_query = f"{query} 原理 文档 教程"
    elif any(term in query_lower for term in ("评测", "续航", "review", "对比")):
        base_query = f"{query} 评测 对比 体验"
    else:
        base_query = f"{query} 详解"

    source_profile = str((tool_context or {}).get("source_profile") or "general").strip().lower()
    if source_profile == "social_realtime":
        site_clause = _build_site_filter_clause(tool_context, limit=4)
        if site_clause:
            return f"{base_query} ({site_clause})"
        return f"{base_query} x twitter 微博 reddit"
    if source_profile == "official_plus_social":
        site_clause = _build_site_filter_clause(tool_context, limit=4)
        if site_clause:
            return f"{base_query} 官方 ({site_clause})"
        return f"{base_query} 官方 x 微博"
    if source_profile == "tech_community":
        site_clause = _build_site_filter_clause(tool_context, limit=4)
        if site_clause:
            return f"{base_query} ({site_clause}) stackoverflow github"
        return f"{base_query} stackoverflow github"
    return base_query


def _should_trigger_second_pass(results: list[dict], actual_max_results: int) -> bool:
    if not results:
        return False

    window = results[: max(actual_max_results, 5)]
    low_value_count = sum(
        1 for item in window if _is_low_value_result(item["url"], item["title"], item["content"])
    )
    good_count = len(window) - low_value_count

    return low_value_count >= 2 and good_count < max(2, actual_max_results // 2)


def _needs_recall_boost(results: list[dict], actual_max_results: int, intent_plan: dict | None) -> bool:
    if len(results) < actual_max_results:
        return True
    intent = (intent_plan or {}).get("intent", "general")
    return intent in {"howto", "explanation"} and len(results) < max(2, actual_max_results)


def _needs_source_profile_boost(results: list[dict], tool_context: dict | None) -> bool:
    source_profile = str((tool_context or {}).get("source_profile") or "general").strip().lower()
    if source_profile not in {"social_realtime", "official_plus_social", "tech_community"}:
        return False
    return not any(
        _matches_source_profile_domain(_normalize_domain(item.get("url", "")), source_profile)
        for item in results
    )


def _merge_search_results(
    primary_results: list[dict], refined_results: list[dict], max_results: int
) -> list[dict]:
    merged: list[dict] = []
    seen_urls = set()

    ordered_groups = [
        [r for r in primary_results if not _is_low_value_result(r["url"], r["title"], r["content"])],
        [r for r in refined_results if not _is_low_value_result(r["url"], r["title"], r["content"])],
        primary_results,
        refined_results,
    ]

    for group in ordered_groups:
        for result in group:
            url = result["url"]
            if url in seen_urls:
                continue
            seen_urls.add(url)
            merged.append(result)
            if len(merged) >= max_results:
                return merged

    return merged


def _estimate_result_quality(
    query: str,
    title: str,
    url: str,
    content: str,
    intent_plan: dict | None = None,
    tool_context: dict | None = None,
) -> float:
    """
    搜索结果轻量质量分：
    - 可靠域名加分
    - 明显低价值/壳页减分
    - 有有效 title/snippet 加分
    """
    rules = _domain_rules()
    score = 0.0
    url_lower = url.lower()
    title_lower = title.lower()
    content_lower = content.lower()
    domain = _normalize_domain(url)
    preferred_domains = _normalize_domain_hints((tool_context or {}).get("preferred_domains"))
    blocked_domains = _normalize_domain_hints((tool_context or {}).get("blocked_domains"))
    domain_preference_mode = str((tool_context or {}).get("domain_preference_mode") or "prefer").strip().lower()
    source_profile = str((tool_context or {}).get("source_profile") or "general").strip().lower()
    query_term_hits = _count_query_term_hits(query, " ".join([title_lower, content_lower, url_lower]))

    if blocked_domains and _domain_matches_hints(domain, blocked_domains):
        return -999.0

    if preferred_domains:
        matched_preferred = _domain_matches_hints(domain, preferred_domains)
        if domain_preference_mode == "only" and not matched_preferred:
            return -999.0
        if matched_preferred:
            score += 12.0 if domain_preference_mode == "strong_prefer" else 6.0

    score += _estimate_source_profile_score(domain, url_lower, title_lower, source_profile)
    if source_profile in {"social_realtime", "official_plus_social"}:
        if query_term_hits == 0:
            score -= 10.0
        has_social_domain = any(marker in domain for marker in rules.social_domains)
        has_news_domain = any(marker in domain for marker in rules.news_domains)
        if not (has_social_domain or has_news_domain):
            score -= 4.0
    elif source_profile == "tech_community" and query_term_hits == 0:
        score -= 6.0

    for idx, preferred in enumerate(rules.preferred_domains):
        if preferred in domain or preferred in url_lower:
            score += max(12 - idx * 0.3, 6)
            break

    if title:
        score += min(len(title) / 40, 2.0)
    if content:
        score += min(len(content) / 80, 2.5)

    if any(hint in url_lower for hint in rules.low_value_url_hints):
        score -= 4.0

    if _is_low_value_result(url, title, content):
        score -= 5.0

    intent = (intent_plan or {}).get("intent", "general")
    if _looks_intent_mismatched(query, title, url, content, intent):
        score -= 8.0
    if intent == "news":
        if any(marker in domain for marker in ("openai.com", "qq.com", "sina.com.cn", "msn.cn")):
            score += 2.5
        if any(marker in url_lower for marker in ("wikipedia.org", "baike.baidu.com")):
            score -= 1.5
    elif intent == "technical":
        tech_official_domains = (
            "docs.python.org",
            "developer.",
            "go.dev",
            "developer.mozilla.org",
            "redis.io",
        )
        if any(marker in domain for marker in tech_official_domains):
            score += 4.0
        elif any(marker in domain for marker in ("cnblogs.com", "csdn.net", "juejin.cn", "segmentfault.com")):
            score += 1.6
        if any(marker in url_lower for marker in ("stackoverflow.com/questions", "github.com/")):
            score -= 1.2
    if source_profile == "tech_community":
        tech_official_domains = (
            "docs.python.org",
            "developer.",
            "go.dev",
            "developer.mozilla.org",
            "redis.io",
        )
        if any(marker in domain for marker in tech_official_domains):
            score += 3.0
        elif any(marker in domain for marker in ("cnblogs.com", "csdn.net", "juejin.cn", "segmentfault.com")):
            score += 0.8
    elif intent == "howto":
        if any(marker in domain for marker in ("meishichina.com", "xiachufang.com", "xiangha.com", "dachu.co")):
            score += 5.0
        elif not any(marker in domain for marker in rules.recipe_domains):
            score -= 1.5
    elif intent == "explanation":
        if any(marker in url_lower for marker in ("baike.baidu.com", "wikipedia.org")):
            score += 2.5
        if any(marker in domain for marker in rules.science_domains):
            score += 1.2
    elif (
        intent == "general"
        and any(term in query.lower() for term in ("评测", "续航", "review"))
        and any(marker in domain for marker in rules.product_domains)
    ):
        score += 2.0

    suspicious_terms = [
        "app下载",
        "官网入口",
        "网页版入口",
        "免费下载",
        "install",
        "download",
        "app",
    ]
    if any(term in title_lower for term in suspicious_terms):
        score -= 3.5
    if any(term in content_lower for term in suspicious_terms):
        score -= 1.5

    if "question" in url_lower or "ask" in url_lower:
        score -= 0.8

    score += _estimate_query_match_score(query, title, content, url)

    return score


def _estimate_query_match_score(query: str, title: str, content: str, url: str) -> float:
    if not query.strip():
        return 0.0

    query_lower = query.lower()
    title_lower = title.lower()
    content_lower = content.lower()
    url_lower = url.lower()

    terms = _extract_query_terms(query)
    if not terms:
        terms = [query_lower]

    score = 0.0
    if query_lower in title_lower:
        score += 6.0
    if query_lower in content_lower:
        score += 3.0

    unique_terms = list(dict.fromkeys(terms))
    for term in unique_terms:
        if len(term) < 2:
            continue
        if term in title_lower:
            score += 2.0
        if term in content_lower:
            score += 1.2
        if term in url_lower:
            score += 0.6

    generic_low_value_terms = [
        "reddit",
        "comment",
        "issue",
        "video",
        "download",
        "community",
    ]
    if not any(term in query_lower for term in ("github", "reddit", "视频", "下载")):
        for marker in generic_low_value_terms:
            if marker in title_lower or marker in url_lower:
                score -= 1.0

    return score
