from typing import Any, Dict


def normalize_openai_compatible_url(api_url: str, default_url: str = "http://127.0.0.1:1234/v1/chat/completions") -> str:
    normalized = (api_url or default_url).rstrip("/")
    if normalized.endswith("/v1/chat/completions"):
        return normalized
    if normalized.endswith("/v1"):
        return normalized + "/chat/completions"
    return normalized + "/v1/chat/completions"



def extract_openai_content(data: Dict[str, Any]) -> str:
    try:
        content = data.get("choices", [{}])[0].get("message", {}).get("content", "")
    except Exception:
        return ""

    if isinstance(content, str):
        return content.strip()
    if isinstance(content, list):
        texts = []
        for part in content:
            if isinstance(part, dict) and part.get("type") == "text":
                texts.append(part.get("text", ""))
        return "".join(texts).strip()
    return ""
