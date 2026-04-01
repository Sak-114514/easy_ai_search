"""
MCP工具处理器单元测试
"""

import pytest
import json
from unittest.mock import AsyncMock
from api_server.services.mcp_tool_handler import MCPToolHandler


class TestMCPTools:
    """MCP工具测试"""

    @pytest.fixture
    def tool_handler(self):
        """创建工具处理器实例"""
        return MCPToolHandler()

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
                        "title": "Mock Result",
                        "url": "https://example.com/mock",
                        "cleaned_content": "mock content",
                        "similarity_score": 0.95,
                    }
                ],
            }

        monkeypatch.setattr(
            "api_server.services.search_service.SearchService.search",
            _mock_search,
        )

    @pytest.mark.asyncio
    async def test_list_tools(self, tool_handler):
        """测试列出工具"""
        tools = await tool_handler.list_tools()

        assert len(tools) > 0
        assert any(t["name"] == "search" for t in tools)
        assert any(t["name"] == "vector_query" for t in tools)
        assert all("name" in t and "description" in t for t in tools)

    @pytest.mark.asyncio
    async def test_call_search_tool(self, tool_handler):
        """测试调用搜索工具"""
        result = await tool_handler.call_tool(
            name="search", arguments={"query": "Python异步编程", "max_results": 3}
        )

        assert len(result) > 0
        assert result[0]["type"] == "text"
        assert "搜索结果" in result[0]["text"]

    @pytest.mark.asyncio
    async def test_call_search_tool_with_structured_request_json_response(self, tool_handler):
        """测试调用搜索工具：结构化 JSON 入参与 JSON 返回。"""
        result = await tool_handler.call_tool(
            name="search",
            arguments={
                "request": {
                    "query": "Redis 持久化机制对比",
                    "max_results": 2,
                    "skip_local": True,
                    "disable_deep_process": True,
                    "mode": "fast",
                    "engines": ["bing", "baidu"],
                },
                "tool_context": {
                    "goal": "为后续回答准备可引用资料",
                    "language": "zh",
                    "time_sensitive": False,
                },
                "response_format": "json",
            },
        )

        assert len(result) > 0
        assert result[0]["type"] == "text"
        payload = json.loads(result[0]["text"])
        assert payload["query"] == "Redis 持久化机制对比"
        assert payload["results_count"] == 1
        assert payload["tool_context"]["language"] == "zh"
        assert payload["results"][0]["url"] == "https://example.com/mock"

    def test_normalize_search_arguments_filters_unsupported_engines(self, tool_handler):
        normalized = tool_handler._normalize_search_arguments(
            {
                "request": {
                    "query": "黑洞为什么会蒸发",
                    "engines": ["google", "wikipedia", "bing"],
                }
            }
        )
        assert normalized["engines"] == "google,bing"

    def test_normalize_search_arguments_defaults_structured_request_to_fast_mode(self, tool_handler):
        normalized = tool_handler._normalize_search_arguments(
            {
                "request": {
                    "query": "黑洞为什么会蒸发",
                }
            }
        )
        assert normalized["mode"] == "fast"

    @pytest.mark.asyncio
    async def test_call_search_tool_passes_tool_context_to_search_service(self, tool_handler):
        tool_handler.search_service.search = AsyncMock(
            return_value={
                "query": "Redis 持久化机制对比",
                "source": "mock",
                "total_time": 0.01,
                "results": [],
            }
        )

        await tool_handler.call_tool(
            name="search",
            arguments={
                "request": {
                    "query": "Redis 持久化机制对比",
                },
                "tool_context": {
                    "preferred_domains": ["redis.io"],
                    "blocked_domains": ["example.com"],
                    "domain_preference_mode": "only",
                    "source_profile": "tech_community",
                },
                "response_format": "json",
            },
        )

        kwargs = tool_handler.search_service.search.await_args.kwargs
        assert kwargs["tool_context"]["preferred_domains"] == ["redis.io"]
        assert kwargs["tool_context"]["blocked_domains"] == ["example.com"]
        assert kwargs["tool_context"]["domain_preference_mode"] == "only"
        assert kwargs["tool_context"]["source_profile"] == "tech_community"

    @pytest.mark.asyncio
    async def test_call_vector_query_tool(self, tool_handler):
        """测试调用向量查询工具"""
        result = await tool_handler.call_tool(
            name="vector_query", arguments={"query": "Python编程", "top_k": 3}
        )

        assert len(result) > 0
        assert result[0]["type"] == "text"

    @pytest.mark.asyncio
    async def test_call_cache_stats_tool(self, tool_handler):
        """测试调用缓存统计工具"""
        result = await tool_handler.call_tool(name="cache_stats", arguments={})

        assert len(result) > 0
        assert result[0]["type"] == "text"
        assert "缓存统计信息" in result[0]["text"]

    @pytest.mark.asyncio
    async def test_call_vector_stats_tool(self, tool_handler):
        """测试调用向量库统计工具"""
        result = await tool_handler.call_tool(name="vector_stats", arguments={})

        assert len(result) > 0
        assert result[0]["type"] == "text"
        assert "向量库统计信息" in result[0]["text"]

    @pytest.mark.asyncio
    async def test_call_unknown_tool(self, tool_handler):
        """测试调用未知工具"""
        with pytest.raises(ValueError, match="未知工具"):
            await tool_handler.call_tool(name="unknown_tool", arguments={})

    @pytest.mark.asyncio
    async def test_search_tool_missing_query(self, tool_handler):
        """测试搜索工具缺少query参数"""
        with pytest.raises(ValueError, match="query"):
            await tool_handler.call_tool(name="search", arguments={})
