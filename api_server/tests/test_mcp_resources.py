"""
MCP资源处理器单元测试
"""

import pytest
from api_server.services.mcp_resource_handler import MCPResourceHandler


class TestMCPResources:
    """MCP资源测试"""

    @pytest.fixture
    def resource_handler(self):
        """创建资源处理器实例"""
        return MCPResourceHandler()

    @pytest.mark.asyncio
    async def test_list_resources(self, resource_handler):
        """测试列出资源"""
        resources = await resource_handler.list_resources()

        assert len(resources) > 0
        assert any(r["uri"] == "logs://latest" for r in resources)
        assert any(r["uri"] == "config://current" for r in resources)
        assert any(r["uri"] == "vector://db" for r in resources)
        assert all("uri" in r and "name" in r for r in resources)

    @pytest.mark.asyncio
    async def test_read_logs_resource(self, resource_handler):
        """测试读取日志资源"""
        result = await resource_handler.read_resource("logs://latest")

        assert "contents" in result
        assert len(result["contents"]) > 0
        assert result["contents"][0]["uri"] == "logs://latest"
        assert "text" in result["contents"][0]

    @pytest.mark.asyncio
    async def test_read_config_resource(self, resource_handler):
        """测试读取配置资源"""
        result = await resource_handler.read_resource("config://current")

        assert "contents" in result
        assert len(result["contents"]) > 0
        assert result["contents"][0]["uri"] == "config://current"

    @pytest.mark.asyncio
    async def test_read_vector_db_resource(self, resource_handler):
        """测试读取向量库资源"""
        result = await resource_handler.read_resource("vector://db")

        assert "contents" in result
        assert len(result["contents"]) > 0
        assert result["contents"][0]["uri"] == "vector://db"

    @pytest.mark.asyncio
    async def test_read_cache_stats_resource(self, resource_handler):
        """测试读取缓存统计资源"""
        result = await resource_handler.read_resource("cache://stats")

        assert "contents" in result
        assert len(result["contents"]) > 0
        assert result["contents"][0]["uri"] == "cache://stats"

    @pytest.mark.asyncio
    async def test_read_unknown_resource(self, resource_handler):
        """测试读取未知资源"""
        with pytest.raises(ValueError, match="未知资源"):
            await resource_handler.read_resource("unknown://resource")
