"""
MCP提示词处理器

实现MCP协议的提示词管理
"""

import logging
from typing import Any, Dict, List

from ..models.mcp import MCPPrompt

logger = logging.getLogger(__name__)


class MCPPromptHandler:
    """MCP提示词处理器"""

    def __init__(self):
        """初始化处理器"""
        self._init_prompts()

    def _init_prompts(self):
        """初始化提示词定义"""
        self.prompts = {
            "smart_search": MCPPrompt(
                name="smart_search",
                description="执行智能搜索，获取相关信息并分析结果",
                arguments=[
                    {"name": "query", "description": "搜索查询字符串", "required": True}
                ],
            ),
            "web_research": MCPPrompt(
                name="web_research",
                description="进行网络研究，深入搜索特定主题",
                arguments=[
                    {"name": "topic", "description": "研究主题", "required": True},
                    {"name": "depth", "description": "研究深度", "required": False},
                ],
            ),
            "quick_search": MCPPrompt(
                name="quick_search",
                description="快速搜索，获取简要信息",
                arguments=[
                    {"name": "query", "description": "搜索查询字符串", "required": True}
                ],
            ),
        }

    async def list_prompts(self) -> List[Dict[str, Any]]:
        """
        列出所有可用提示词

        Returns:
            提示词列表
        """
        prompts = [
            {
                "name": prompt.name,
                "description": prompt.description,
                "arguments": prompt.arguments or [],
            }
            for prompt in self.prompts.values()
        ]
        logger.info(f"列出提示词: {len(prompts)}个")
        return prompts

    async def get_prompt(self, name: str, arguments: Dict[str, Any]) -> str:
        """
        获取提示词内容

        Args:
            name: 提示词名称
            arguments: 提示词参数

        Returns:
            提示词内容

        Raises:
            ValueError: 提示词不存在
        """
        logger.info(f"获取提示词: {name}, 参数: {arguments}")

        if name == "smart_search":
            return self._get_smart_search_prompt(arguments)
        elif name == "web_research":
            return self._get_web_research_prompt(arguments)
        elif name == "quick_search":
            return self._get_quick_search_prompt(arguments)
        else:
            raise ValueError(f"未知提示词: {name}")

    def _get_smart_search_prompt(self, arguments: Dict[str, Any]) -> str:
        """获取智能搜索提示词"""
        query = arguments.get("query", "")

        return f"""请执行智能搜索并分析结果。

搜索查询: {query}

步骤:
1. 使用search工具搜索相关信息
2. 分析搜索结果，提取关键信息
3. 总结回答

请开始执行搜索。"""

    def _get_web_research_prompt(self, arguments: Dict[str, Any]) -> str:
        """获取网络研究提示词"""
        topic = arguments.get("topic", "")
        depth = arguments.get("depth", "moderate")

        return f"""请进行网络研究。

研究主题: {topic}
研究深度: {depth}

步骤:
1. 使用search工具进行多轮搜索
2. 收集不同角度的信息
3. 综合分析并形成研究报告

请开始研究。"""

    def _get_quick_search_prompt(self, arguments: Dict[str, Any]) -> str:
        """获取快速搜索提示词"""
        query = arguments.get("query", "")

        return f"""请快速搜索并简要回答。

搜索查询: {query}

步骤:
1. 使用search工具搜索
2. 提供简要回答，不超过200字

请开始搜索。"""
