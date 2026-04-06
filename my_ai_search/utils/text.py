import re
from urllib.parse import urlparse

_QUERY_STOP_TERMS = {
    "为什么",
    "如何",
    "怎么",
    "通俗",
    "解释",
    "原理",
    "做法",
    "技巧",
    "步骤",
    "and",
    "the",
    "for",
    "with",
    "how",
    "what",
    "when",
    "where",
    "why",
    "best",
    "vs",
    "教程",
    "指南",
    "最佳实践",
    "发布信息",
    "发布",
    "信息",
    "评测",
    "续航",
    "家常",
    "不能",
    "以及",
    "和",
    "的",
    "是什么",
    "详解",
    "实测",
}

_LOW_VALUE_URL_HINTS = [
    "github.com/",
    "/pulls",
    "/issues",
    "/releases",
    "reddit.com/r/",
    "/comments/",
    "bilibili.com/video/",
    "haokan.baidu.com/v",
    "quanmin.baidu.com/sv",
]

_LOW_VALUE_TITLE_HINTS = [
    "pull requests",
    "issues",
    "discussion",
    "comments",
    "论坛",
    "社区",
    "视频",
]


def normalize_domain(url: str) -> str:
    try:
        return urlparse(url).netloc.lower()
    except Exception:
        return (url or "").lower()



def canonical_path_key(url: str) -> str:
    try:
        parsed = urlparse(url)
        path = (parsed.path or "/").lower()
    except Exception:
        path = (url or "").lower()

    path = path.strip("/")
    parts = [part for part in path.split("/") if part]
    normalized_parts = []
    for part in parts[:4]:
        if re.fullmatch(r"\d+(\.\d+)*", part):
            normalized_parts.append("{version}")
        elif len(part) in (2, 5) and part.replace("-", "").isalpha():
            normalized_parts.append("{lang}")
        else:
            normalized_parts.append(part)
    return "/".join(normalized_parts)



def extract_query_terms(query: str, limit: int = 8) -> list[str]:
    if not (query or "").strip():
        return []

    fragments = re.findall(r"[a-z0-9.+#-]+|[\u4e00-\u9fff]+", query.lower())
    terms: list[str] = []
    seen = set()

    for fragment in fragments:
        normalized = fragment
        for stop_term in _QUERY_STOP_TERMS:
            normalized = normalized.replace(stop_term, " ")
        for piece in re.split(r"\s+", normalized):
            token = piece.strip()
            if len(token) < 2 or token in seen:
                continue
            seen.add(token)
            terms.append(token)

    if not terms:
        fallback = query.lower().strip()
        if fallback:
            terms.append(fallback)
    return terms[:limit]



def looks_non_article_page(url: str, title: str, query: str) -> bool:
    lowered_url = (url or "").lower()
    lowered_title = (title or "").lower()
    lowered_query = (query or "").lower()

    if any(term in lowered_query for term in ("github", "git", "issue", "pull request", "视频", "bilibili", "reddit")):
        return False

    if any(hint in lowered_url for hint in _LOW_VALUE_URL_HINTS):
        return True
    return any(hint in lowered_title for hint in _LOW_VALUE_TITLE_HINTS)
