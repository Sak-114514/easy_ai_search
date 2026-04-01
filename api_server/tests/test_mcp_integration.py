"""
MCP协议集成测试
"""

import pytest
import json
from fastapi.testclient import TestClient
from api_server.main import app


class TestMCPIntegration:
    """MCP协议集成测试"""

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
                "total_time": 0.02,
                "results": [
                    {
                        "title": "Mock Result",
                        "url": "https://example.com/mock",
                        "cleaned_content": "mock content",
                        "similarity_score": 0.93,
                    }
                ],
            }

        monkeypatch.setattr(
            "api_server.services.search_service.SearchService.search",
            _mock_search,
        )

    def test_jsonrpc_initialize(self, client, default_headers):
        """测试MCP协议初始化"""
        response = client.post(
            "/mcp/jsonrpc",
            json={"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {}},
            headers=default_headers,
        )

        assert response.status_code == 200
        data = response.json()
        assert "result" in data
        assert "protocolVersion" in data["result"]
        assert "capabilities" in data["result"]

    def test_jsonrpc_tools_list(self, client, default_headers):
        """测试工具列表"""
        response = client.post(
            "/mcp/jsonrpc",
            json={"jsonrpc": "2.0", "id": 1, "method": "tools/list", "params": {}},
            headers=default_headers,
        )

        assert response.status_code == 200
        data = response.json()
        assert "result" in data
        assert "tools" in data["result"]
        assert len(data["result"]["tools"]) > 0

    def test_jsonrpc_tools_call_search(self, client, default_headers):
        """测试工具调用-搜索"""
        response = client.post(
            "/mcp/jsonrpc",
            json={
                "jsonrpc": "2.0",
                "id": 1,
                "method": "tools/call",
                "params": {
                    "name": "search",
                    "arguments": {"query": "Python异步编程", "max_results": 3},
                },
            },
            headers=default_headers,
        )

        assert response.status_code == 200
        data = response.json()
        assert "result" in data
        assert "content" in data["result"]
        assert len(data["result"]["content"]) > 0

    def test_jsonrpc_tools_call_search_structured_request(
        self, client, default_headers
    ):
        """测试工具调用-搜索：结构化 JSON 请求。"""
        response = client.post(
            "/mcp/jsonrpc",
            json={
                "jsonrpc": "2.0",
                "id": 2,
                "method": "tools/call",
                "params": {
                    "name": "search",
                    "arguments": {
                        "request": {
                            "query": "黑洞为什么会蒸发 霍金辐射 通俗解释",
                            "max_results": 2,
                            "skip_local": True,
                            "disable_deep_process": True,
                        },
                        "tool_context": {
                            "goal": "为解释型回答准备上下文",
                            "language": "zh",
                        },
                        "response_format": "json",
                    },
                },
            },
            headers=default_headers,
        )

        assert response.status_code == 200
        data = response.json()
        assert "result" in data
        assert "content" in data["result"]
        assert len(data["result"]["content"]) > 0
        payload = json.loads(data["result"]["content"][0]["text"])
        assert payload["query"] == "黑洞为什么会蒸发 霍金辐射 通俗解释"
        assert payload["tool_context"]["language"] == "zh"

    def test_jsonrpc_resources_list(self, client, default_headers):
        """测试资源列表"""
        response = client.post(
            "/mcp/jsonrpc",
            json={"jsonrpc": "2.0", "id": 1, "method": "resources/list", "params": {}},
            headers=default_headers,
        )

        assert response.status_code == 200
        data = response.json()
        assert "result" in data
        assert "resources" in data["result"]
        assert len(data["result"]["resources"]) > 0

    def test_jsonrpc_resources_read(self, client, default_headers):
        """测试资源读取"""
        response = client.post(
            "/mcp/jsonrpc",
            json={
                "jsonrpc": "2.0",
                "id": 1,
                "method": "resources/read",
                "params": {"uri": "config://current"},
            },
            headers=default_headers,
        )

        assert response.status_code == 200
        data = response.json()
        assert "result" in data
        assert "contents" in data["result"]

    def test_jsonrpc_prompts_list(self, client, default_headers):
        """测试提示词列表"""
        response = client.post(
            "/mcp/jsonrpc",
            json={"jsonrpc": "2.0", "id": 1, "method": "prompts/list", "params": {}},
            headers=default_headers,
        )

        assert response.status_code == 200
        data = response.json()
        assert "result" in data
        assert "prompts" in data["result"]
        assert len(data["result"]["prompts"]) > 0

    def test_jsonrpc_prompts_get(self, client, default_headers):
        """测试获取提示词"""
        response = client.post(
            "/mcp/jsonrpc",
            json={
                "jsonrpc": "2.0",
                "id": 1,
                "method": "prompts/get",
                "params": {"name": "smart_search", "arguments": {"query": "Python"}},
            },
            headers=default_headers,
        )

        assert response.status_code == 200
        data = response.json()
        assert "result" in data
        assert "description" in data["result"]

    def test_jsonrpc_method_not_found(self, client, default_headers):
        """测试方法不存在"""
        response = client.post(
            "/mcp/jsonrpc",
            json={"jsonrpc": "2.0", "id": 1, "method": "unknown/method", "params": {}},
            headers=default_headers,
        )

        assert response.status_code == 200
        data = response.json()
        assert "error" in data
        assert data["error"]["code"] == -32601

    def test_jsonrpc_invalid_params(self, client, default_headers):
        """测试无效参数"""
        response = client.post(
            "/mcp/jsonrpc",
            json={
                "jsonrpc": "2.0",
                "id": 1,
                "method": "tools/call",
                "params": {"name": "search"},
            },
            headers=default_headers,
        )

        assert response.status_code == 200
        data = response.json()
        assert "error" in data
        assert data["error"]["code"] == -32602

    def test_get_tools(self, client, default_headers):
        """测试GET工具列表"""
        response = client.get("/mcp/tools", headers=default_headers)

        assert response.status_code == 200
        data = response.json()
        assert "tools" in data
        assert len(data["tools"]) > 0

    def test_post_tools_call(self, client, default_headers):
        """测试POST工具调用"""
        response = client.post(
            "/mcp/tools/call",
            json={
                "name": "search",
                "arguments": {"query": "Python异步编程", "max_results": 3},
            },
            headers=default_headers,
        )

        assert response.status_code == 200
        data = response.json()
        assert "content" in data

    def test_get_resources(self, client, default_headers):
        """测试GET资源列表"""
        response = client.get("/mcp/resources", headers=default_headers)

        assert response.status_code == 200
        data = response.json()
        assert "resources" in data
        assert len(data["resources"]) > 0

    def test_post_resources_read(self, client, default_headers):
        """测试POST资源读取"""
        response = client.post(
            "/mcp/resources/read",
            json={"uri": "vector://db"},
            headers=default_headers,
        )

        assert response.status_code == 200
        data = response.json()
        assert "contents" in data

    def test_get_prompts(self, client, default_headers):
        """测试GET提示词列表"""
        response = client.get("/mcp/prompts", headers=default_headers)

        assert response.status_code == 200
        data = response.json()
        assert "prompts" in data
        assert len(data["prompts"]) > 0

    def test_get_capabilities(self, client, default_headers):
        """测试获取能力声明"""
        response = client.get("/mcp/capabilities", headers=default_headers)

        assert response.status_code == 200
        data = response.json()
        assert "protocolVersion" in data
        assert "capabilities" in data
        assert "serverInfo" in data

    def test_mcp_requires_api_key(self, client):
        response = client.get("/mcp/tools")
        assert response.status_code == 401
