import requests

from my_ai_search.utils.logger import setup_logger
from my_ai_search.utils.openai_client import (
    extract_openai_content,
    normalize_openai_compatible_url,
)

logger = setup_logger("summary_provider")


def summarize_with_backend(
    text: str,
    backend: str,
    api_url: str,
    model: str,
    timeout: float,
    max_length: int,
    api_key: str = "",
) -> str:
    if not text or not text.strip():
        return ""

    prompt = (
        "你是信息提炼助手。请基于输入正文生成高信息密度摘要："
        "1) 保留关键事实、结论、数字和时间点；"
        "2) 不要编造；"
        "3) 输出纯文本，不要 Markdown；"
        f"4) 摘要长度不超过 {max_length} 字。\n\n"
        f"正文：\n{text}"
    )

    backend = (backend or "extractive").lower()
    try:
        if backend in ("lmstudio", "openai_compatible"):
            return _call_openai_compatible(
                prompt=prompt,
                api_url=api_url,
                model=model,
                timeout=timeout,
                max_length=max_length,
                api_key=api_key,
            )

        if backend == "ollama":
            return _call_ollama(
                prompt=prompt,
                api_url=api_url,
                model=model,
                timeout=timeout,
                max_length=max_length,
            )

        return ""
    except Exception as e:
        logger.warning(f"Summary backend call failed ({backend}): {e}")
        return ""


def _call_openai_compatible(
    prompt: str,
    api_url: str,
    model: str,
    timeout: float,
    max_length: int,
    api_key: str = "",
) -> str:
    endpoint = normalize_openai_compatible_url(api_url)
    headers = {"Content-Type": "application/json"}
    if api_key:
        headers["Authorization"] = f"Bearer {api_key}"

    payload = {
        "model": model,
        "messages": [
            {"role": "system", "content": "你擅长高保真中文摘要。"},
            {"role": "user", "content": prompt},
        ],
        "temperature": 0.2,
        "max_tokens": max(64, min(2048, max_length)),
    }

    response = requests.post(endpoint, json=payload, headers=headers, timeout=timeout)
    response.raise_for_status()
    data = response.json()
    content = extract_openai_content(data)
    return content[:max_length]


def _call_ollama(
    prompt: str,
    api_url: str,
    model: str,
    timeout: float,
    max_length: int,
) -> str:
    payload = {
        "model": model,
        "prompt": prompt,
        "stream": False,
        "options": {"temperature": 0.2},
    }
    response = requests.post(api_url, json=payload, timeout=timeout)
    response.raise_for_status()
    data = response.json()
    content = (data.get("response") or "").strip()
    return content[:max_length]
