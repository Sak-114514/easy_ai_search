"""
MCP 服务

封装 MCP 协议的工具、资源和提示词
"""

import json
import logging
from typing import Any, Dict, List

from .mcp_tool_handler import MCPToolHandler
from .mcp_resource_handler import MCPResourceHandler
from .mcp_prompt_handler import MCPPromptHandler
from .mcp_sse_handler import mcp_sse_stream

logger = logging.getLogger(__name__)


class MCPService:
    """MCP 服务类"""

    def __init__(self):
        """初始化服务"""
        self.tool_handler = MCPToolHandler()
        self.resource_handler = MCPResourceHandler()
        self.prompt_handler = MCPPromptHandler()

    def get_capabilities(self) -> Dict:
        """获取 MCP 服务器能力声明"""
        return {
            "protocolVersion": "2024-11-05",
            "capabilities": {
                "tools": {"listChanged": True},
                "resources": {"subscribe": True, "listChanged": True},
                "prompts": {"listChanged": True},
            },
            "serverInfo": {"name": "opensearch-mcp-server", "version": "2.0.0"},
        }

    async def handle_sse(self, query: str):
        """处理 SSE 连接"""
        async for event in mcp_sse_stream(query, self.tool_handler):
            yield event

    async def list_tools(self) -> List[Dict]:
        """列出所有可用工具"""
        return await self.tool_handler.list_tools()

    async def call_tool(self, name: str, arguments: Dict) -> List[Dict]:
        """调用工具"""
        return await self.tool_handler.call_tool(name, arguments)

    async def list_resources(self) -> List[Dict]:
        """列出所有可用资源"""
        return await self.resource_handler.list_resources()

    async def read_resource(self, uri: str) -> Dict:
        """获取资源"""
        return await self.resource_handler.read_resource(uri)

    async def list_prompts(self) -> List[Dict]:
        """列出所有可用提示词"""
        return await self.prompt_handler.list_prompts()

    async def get_prompt(self, name: str, arguments: Dict) -> str:
        """获取提示词"""
        return await self.prompt_handler.get_prompt(name, arguments)
