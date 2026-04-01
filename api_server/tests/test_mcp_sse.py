"""
SSE流式响应单元测试
"""

import pytest
from fastapi.testclient import TestClient
from api_server.main import app


class TestMCPSSE:
    """MCP SSE测试"""

    @pytest.fixture
    def client(self):
        """创建测试客户端"""
        return TestClient(app)

    @pytest.fixture
    def default_headers(self):
        from api_server.config import get_api_config

        config = get_api_config()
        return {
            "X-API-Key": config.api_keys.get(
                "default", config.api_keys.get("admin", "")
            )
        }

    @pytest.fixture(autouse=True)
    def mock_search_service(self, monkeypatch):
        """隔离外部搜索依赖，保证离线环境可测试。"""

        async def _mock_search(*args, **kwargs):
            return {
                "query": kwargs.get("query", ""),
                "source": "mock",
                "total_time": 0.01,
                "results": [
                    {
                        "title": "Mock SSE Result",
                        "url": "https://example.com/sse",
                        "cleaned_content": "mock content",
                        "similarity_score": 0.9,
                    }
                ],
            }

        monkeypatch.setattr(
            "api_server.services.search_service.SearchService.search",
            _mock_search,
        )

    def test_sse_stream(self, client, default_headers):
        """测试SSE流式响应"""
        with client.stream(
            "POST",
            "/mcp/sse",
            json={"query": "Python异步编程"},
            headers={**default_headers, "Accept": "text/event-stream"},
        ) as response:
            assert response.status_code == 200
            assert "text/event-stream" in response.headers["content-type"]

            events = []
            for line in response.iter_lines():
                if line:
                    events.append(line if isinstance(line, str) else line.decode())
                    if len(events) >= 20:  # 读取前20个事件
                        break

            assert any("event: start" in e for e in events)
            assert any("event: progress" in e for e in events)
            assert any("event: result" in e for e in events)

    def test_sse_with_empty_query(self, client, default_headers):
        """测试空查询的SSE响应"""
        with client.stream(
            "POST",
            "/mcp/sse",
            json={"query": ""},
            headers={**default_headers, "Accept": "text/event-stream"},
        ) as response:
            assert response.status_code == 200
