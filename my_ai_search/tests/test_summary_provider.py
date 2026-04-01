from my_ai_search.deep_process.summary_provider import summarize_with_backend


class _FakeResponse:
    def __init__(self, payload):
        self._payload = payload

    def raise_for_status(self):
        return None

    def json(self):
        return self._payload


def test_lmstudio_base_url_auto_append(monkeypatch):
    captured = {}

    def _fake_post(url, json, headers, timeout):
        captured["url"] = url
        captured["json"] = json
        captured["headers"] = headers
        captured["timeout"] = timeout
        return _FakeResponse(
            {"choices": [{"message": {"content": "这是本地模型摘要结果"}}]}
        )

    monkeypatch.setattr("requests.post", _fake_post)

    summary = summarize_with_backend(
        text="这是一个很长的正文，用于测试 LM Studio 的本地摘要服务接入。",
        backend="lmstudio",
        api_url="http://127.0.0.1:1234",
        model="qwen2.5-7b-instruct",
        timeout=5.0,
        max_length=30,
    )

    assert summary == "这是本地模型摘要结果"
    assert captured["url"] == "http://127.0.0.1:1234/v1/chat/completions"
    assert captured["json"]["model"] == "qwen2.5-7b-instruct"


def test_openai_compatible_content_array(monkeypatch):
    def _fake_post(url, json, headers, timeout):
        return _FakeResponse(
            {
                "choices": [
                    {
                        "message": {
                            "content": [
                                {"type": "text", "text": "第一句。"},
                                {"type": "text", "text": "第二句。"},
                            ]
                        }
                    }
                ]
            }
        )

    monkeypatch.setattr("requests.post", _fake_post)

    summary = summarize_with_backend(
        text="测试 content array 返回结构。",
        backend="openai_compatible",
        api_url="http://127.0.0.1:1234/v1",
        model="demo-model",
        timeout=5.0,
        max_length=50,
    )

    assert summary == "第一句。第二句。"
