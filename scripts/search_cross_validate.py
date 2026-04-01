#!/usr/bin/env python3
import json
import os
import sys
import time
import urllib.request


DEFAULT_QUERIES = [
    ("tech", "PostgreSQL MVCC 原理 通俗解释"),
    ("news", "OpenAI GPT-5.4 mini 发布信息"),
    ("howto", "家常宫保鸡丁做法和技巧"),
    ("science", "量子纠缠为什么不能超光速通信"),
    ("product", "MacBook Air M4 续航 评测"),
    ("coding", "Python asyncio gather 和 TaskGroup 区别"),
]


def _get_api_key():
    key = os.getenv("OPENSEARCH_API_KEY")
    if key:
        return key
    try:
        from dotenv import load_dotenv

        load_dotenv()
        raw = os.getenv("API_KEYS_JSON", "{}")
        keys = json.loads(raw.strip().strip("'\""))
        return keys.get("admin", keys.get("default", ""))
    except Exception:
        return ""


def run_query(query: str, mode: str) -> dict:
    payload = {
        "query": query,
        "max_results": 3,
        "use_cache": False,
        "skip_local": True,
        "disable_deep_process": True,
        "mode": mode,
    }
    req = urllib.request.Request(
        "http://127.0.0.1:8000/api/v1/search",
        data=json.dumps(payload).encode("utf-8"),
        headers={
            "X-API-Key": _get_api_key(),
            "Content-Type": "application/json",
        },
        method="POST",
    )
    start = time.time()
    with urllib.request.urlopen(req, timeout=180) as resp:
        result = json.loads(resp.read().decode("utf-8"))
    elapsed = time.time() - start
    return {
        "elapsed": round(elapsed, 2),
        "total_time": round(result.get("total_time", 0), 2),
        "count": len(result.get("results", [])),
        "urls": [item.get("url") for item in result.get("results", [])[:3]],
        "titles": [item.get("title") for item in result.get("results", [])[:3]],
    }


def main() -> int:
    mode = sys.argv[1] if len(sys.argv) > 1 else "fast"
    for label, query in DEFAULT_QUERIES:
        result = run_query(query, mode=mode)
        print(
            json.dumps(
                {
                    "label": label,
                    "query": query,
                    "mode": mode,
                    **result,
                },
                ensure_ascii=False,
            )
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
