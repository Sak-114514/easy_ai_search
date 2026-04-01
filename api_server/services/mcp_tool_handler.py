"""
MCP工具处理器

实现MCP协议的工具管理和调用
"""

import json
import logging
from typing import Any, Dict, List

from ..models.mcp import MCPTool
from ..utils.mcp.validators import ParameterValidator
from .search_service import SearchService
from .vector_service import VectorService
from .cache_service import CacheService
from .log_service import LogService
from .config_service import ConfigService

logger = logging.getLogger(__name__)

_SUPPORTED_SEARCH_ENGINES = {
    "google",
    "bing",
    "baidu",
    "sogou",
    "360search",
    "duckduckgo",
    "brave",
    "startpage",
    "yahoo",
    "mojeek",
    "presearch",
    "mwmbl",
    "seznam",
    "qwant",
}


class MCPToolHandler:
    """MCP工具处理器"""

    def __init__(self):
        """初始化处理器"""
        self.search_service = SearchService()
        self.vector_service = VectorService()
        self.cache_service = CacheService()
        self.log_service = LogService()
        self.config_service = ConfigService()

        self.validator = ParameterValidator()

        self._init_tools()

    def _init_tools(self):
        """初始化工具定义"""
        self.tools = {
            "search": MCPTool(
                name="search",
                description="执行AI搜索，获取相关信息。支持本地优先策略，先查询本地向量库，命中即返回，否则进行在线搜索。",
                input_schema={
                    "type": "object",
                    "properties": {
                        "request": {
                            "type": "object",
                            "description": "结构化搜索请求。推荐 LLM/Agent 使用这个对象，而不是平铺参数。",
                            "properties": {
                                "query": {
                                    "type": "string",
                                    "description": "搜索查询字符串",
                                    "minLength": 1,
                                    "maxLength": 500,
                                },
                                "max_results": {
                                    "type": "integer",
                                    "description": "最大返回结果数",
                                    "default": 5,
                                    "minimum": 1,
                                    "maximum": 20,
                                },
                                "use_cache": {
                                    "type": "boolean",
                                    "description": "是否使用URL缓存",
                                    "default": True,
                                },
                                "skip_local": {
                                    "type": "boolean",
                                    "description": "是否跳过本地向量库查询",
                                    "default": False,
                                },
                                "disable_deep_process": {
                                    "type": "boolean",
                                    "description": "是否禁用深度处理（摘要/质量过滤/去重）",
                                    "default": False,
                                },
                                "mode": {
                                    "type": "string",
                                    "description": "搜索模式：fast 更适合工具调用，balanced 为默认平衡模式，deep 为更完整模式",
                                    "enum": ["fast", "balanced", "deep"],
                                    "default": "fast",
                                },
                                "engines": {
                                    "type": "array",
                                    "description": "指定搜索引擎列表，如 [\"bing\", \"baidu\"]。更适合 LLM 生成。",
                                    "items": {"type": "string", "maxLength": 64},
                                    "maxItems": 10,
                                },
                                "source_profile": {
                                    "type": "string",
                                    "description": "来源策略：general/official_news/social_realtime/official_plus_social/tech_community",
                                    "enum": ["general", "official_news", "social_realtime", "official_plus_social", "tech_community"],
                                },
                            },
                        },
                        "query": {
                            "type": "string",
                            "description": "搜索查询字符串",
                            "minLength": 1,
                            "maxLength": 500,
                        },
                        "max_results": {
                            "type": "integer",
                            "description": "最大返回结果数",
                            "default": 5,
                            "minimum": 1,
                            "maximum": 20,
                        },
                        "use_cache": {
                            "type": "boolean",
                            "description": "是否使用URL缓存",
                            "default": True,
                        },
                        "skip_local": {
                            "type": "boolean",
                            "description": "是否跳过本地向量库查询",
                            "default": False,
                        },
                        "disable_deep_process": {
                            "type": "boolean",
                            "description": "是否禁用深度处理（摘要/质量过滤/去重）",
                            "default": False,
                        },
                        "mode": {
                            "type": "string",
                            "description": "搜索模式：fast/balanced/deep",
                            "enum": ["fast", "balanced", "deep"],
                        },
                        "engines": {
                            "type": "string",
                            "description": "指定搜索引擎，逗号分隔，如 bing,baidu",
                            "maxLength": 200,
                        },
                        "tool_context": {
                            "type": "object",
                            "description": "调用方上下文。当前主要用于保留 LLM/Agent 传入的结构化意图，不直接改变搜索逻辑。",
                            "properties": {
                                "goal": {"type": "string", "maxLength": 300},
                                "language": {"type": "string", "maxLength": 32},
                                "time_sensitive": {"type": "boolean"},
                                "preferred_domains": {
                                    "type": "array",
                                    "items": {"type": "string", "maxLength": 200},
                                    "maxItems": 20,
                                },
                                "blocked_domains": {
                                    "type": "array",
                                    "items": {"type": "string", "maxLength": 200},
                                    "maxItems": 20,
                                },
                                "domain_preference_mode": {
                                    "type": "string",
                                    "enum": ["prefer", "strong_prefer", "only"],
                                },
                                "source_profile": {
                                    "type": "string",
                                    "enum": ["general", "official_news", "social_realtime", "official_plus_social", "tech_community"],
                                },
                            },
                        },
                        "response_format": {
                            "type": "string",
                            "description": "返回格式。text 保持兼容；json 更适合 LLM 解析。",
                            "enum": ["text", "json"],
                        },
                    },
                },
            ),
            "vector_query": MCPTool(
                name="vector_query",
                description="在向量库中执行语义查询，查找相似的文档片段。",
                input_schema={
                    "type": "object",
                    "properties": {
                        "query": {
                            "type": "string",
                            "description": "查询字符串",
                            "minLength": 1,
                            "maxLength": 500,
                        },
                        "top_k": {
                            "type": "integer",
                            "description": "返回最相似的结果数",
                            "default": 3,
                            "minimum": 1,
                            "maximum": 10,
                        },
                    },
                    "required": ["query"],
                },
            ),
            "cache_stats": MCPTool(
                name="cache_stats",
                description="获取URL缓存的统计信息，包括总数量、命中次数、命中率等。",
                input_schema={"type": "object", "properties": {}},
            ),
            "vector_stats": MCPTool(
                name="vector_stats",
                description="获取向量库的统计信息，包括文档数量、集合数量、向量维度等。",
                input_schema={"type": "object", "properties": {}},
            ),
            "clear_cache": MCPTool(
                name="clear_cache",
                description="清空URL缓存。",
                input_schema={"type": "object", "properties": {}},
            ),
            "clear_vector_db": MCPTool(
                name="clear_vector_db",
                description="清空向量库。",
                input_schema={"type": "object", "properties": {}},
            ),
        }

    async def list_tools(self) -> List[Dict[str, Any]]:
        """
        列出所有可用工具

        Returns:
            工具列表
        """
        tools = [
            {
                "name": tool.name,
                "description": tool.description,
                "inputSchema": tool.input_schema,
            }
            for tool in self.tools.values()
        ]
        logger.info(f"列出工具: {len(tools)}个")
        return tools

    async def call_tool(
        self, name: str, arguments: Dict[str, Any]
    ) -> List[Dict[str, Any]]:
        """
        调用工具

        Args:
            name: 工具名称
            arguments: 工具参数

        Returns:
            工具执行结果（文本内容或资源引用）

        Raises:
            ValueError: 工具不存在或参数无效
            Exception: 工具执行失败
        """
        logger.info(f"调用工具: {name}, 参数: {arguments}")

        try:
            if name == "search":
                return await self._handle_search(arguments)
            elif name == "vector_query":
                return await self._handle_vector_query(arguments)
            elif name == "cache_stats":
                return await self._handle_cache_stats(arguments)
            elif name == "vector_stats":
                return await self._handle_vector_stats(arguments)
            elif name == "clear_cache":
                return await self._handle_clear_cache(arguments)
            elif name == "clear_vector_db":
                return await self._handle_clear_vector_db(arguments)
            else:
                raise ValueError(f"未知工具: {name}")
        except ValueError as e:
            logger.error(f"工具调用失败（参数错误）: {name}, {str(e)}")
            raise
        except Exception as e:
            logger.error(f"工具调用失败（执行错误）: {name}, {str(e)}")
            raise

    async def _handle_search(self, arguments: Dict[str, Any]) -> List[Dict[str, Any]]:
        """处理搜索工具调用"""
        name = "search"
        if name not in self.tools:
            raise ValueError(f"Unknown tool: {name}")

        tool = self.tools[name]

        try:
            validated_args = self.validator.validate(tool.input_schema, arguments)
        except Exception as e:
            raise ValueError(f"参数验证失败: {str(e)}")

        normalized_args = self._normalize_search_arguments(validated_args)

        query = normalized_args.get("query")
        max_results = normalized_args.get("max_results", 5)
        use_cache = normalized_args.get("use_cache", True)
        skip_local = normalized_args.get("skip_local", False)
        disable_deep_process = normalized_args.get("disable_deep_process", False)
        mode = normalized_args.get("mode", "fast")
        engines = normalized_args.get("engines")
        response_format = normalized_args.get("response_format", "text")

        if not query:
            raise ValueError("query参数必填")

        result = await self.search_service.search(
            query=query,
            max_results=max_results,
            use_cache=use_cache,
            skip_local=skip_local,
            disable_deep_process=disable_deep_process,
            client_type="mcp",
            engines=engines,
            mode=mode,
            tool_context=normalized_args.get("tool_context") or {},
        )

        tool_context = normalized_args.get("tool_context") or {}
        content = self._format_search_result(
            result=result,
            response_format=response_format,
            tool_context=tool_context,
        )
        return [{"type": "text", "text": content}]

    async def _handle_vector_query(
        self, arguments: Dict[str, Any]
    ) -> List[Dict[str, Any]]:
        """处理向量查询工具调用"""
        name = "vector_query"
        if name not in self.tools:
            raise ValueError(f"Unknown tool: {name}")

        tool = self.tools[name]

        try:
            validated_args = self.validator.validate(tool.input_schema, arguments)
        except Exception as e:
            raise ValueError(f"参数验证失败: {str(e)}")

        query = validated_args.get("query")
        top_k = validated_args.get("top_k", 3)

        if not query:
            raise ValueError("query参数必填")

        from my_ai_search.vector import hybrid_search

        results = hybrid_search(query, top_k=top_k)

        content = self._format_vector_results(results)
        return [{"type": "text", "text": content}]

    async def _handle_cache_stats(
        self, arguments: Dict[str, Any]
    ) -> List[Dict[str, Any]]:
        """处理缓存统计工具调用"""
        stats = self.cache_service.get_stats()

        content = json.dumps(stats, indent=2, ensure_ascii=False)
        return [{"type": "text", "text": f"缓存统计信息：\n```json\n{content}\n```"}]

    async def _handle_vector_stats(
        self, arguments: Dict[str, Any]
    ) -> List[Dict[str, Any]]:
        """处理向量库统计工具调用"""
        stats = self.vector_service.get_stats()

        content = json.dumps(stats, indent=2, ensure_ascii=False)
        return [{"type": "text", "text": f"向量库统计信息：\n```json\n{content}\n```"}]

    async def _handle_clear_cache(
        self, arguments: Dict[str, Any]
    ) -> List[Dict[str, Any]]:
        """处理清空缓存工具调用"""
        result = self.cache_service.clear_cache()

        if result.get("success"):
            content = f"缓存已清空，共清除 {result.get('cleared', 0)} 条记录"
        else:
            content = f"清空缓存失败: {result.get('error', 'Unknown error')}"

        return [{"type": "text", "text": content}]

    async def _handle_clear_vector_db(
        self, arguments: Dict[str, Any]
    ) -> List[Dict[str, Any]]:
        """处理清空向量库工具调用"""
        result = self.vector_service.clear_collection()

        if result.get("success"):
            content = f"向量库已清空，共清除 {result.get('cleared_count', 0)} 条记录"
        else:
            content = f"清空向量库失败: {result.get('error', 'Unknown error')}"

        return [{"type": "text", "text": content}]

    def _normalize_search_arguments(self, arguments: Dict[str, Any]) -> Dict[str, Any]:
        """兼容旧平铺参数和新的结构化 request 对象。"""
        request = arguments.get("request") or {}
        normalized = dict(arguments)
        for key in (
            "query",
            "max_results",
            "use_cache",
            "skip_local",
            "disable_deep_process",
            "mode",
            "engines",
            "source_profile",
        ):
            if key not in normalized or normalized.get(key) is None:
                if key in request:
                    normalized[key] = request[key]
        if isinstance(normalized.get("engines"), list):
            normalized["engines"] = ",".join(
                engine
                for engine in (
                    str(item).strip().lower() for item in normalized["engines"] if str(item).strip()
                )
                if engine in _SUPPORTED_SEARCH_ENGINES
            ) or None
        elif isinstance(normalized.get("engines"), str):
            normalized["engines"] = ",".join(
                engine
                for engine in (
                    item.strip().lower() for item in normalized["engines"].split(",") if item.strip()
                )
                if engine in _SUPPORTED_SEARCH_ENGINES
            ) or None
        mode = str(normalized.get("mode") or "").strip().lower()
        normalized["mode"] = mode if mode in {"fast", "balanced", "deep"} else ("fast" if request else "balanced")
        source_profile = str(normalized.get("source_profile") or "").strip().lower()
        if source_profile:
            normalized.setdefault("tool_context", {})
            normalized["tool_context"]["source_profile"] = source_profile
        normalized["response_format"] = normalized.get("response_format") or "text"
        return normalized

    def _format_search_result(
        self,
        result: Dict[str, Any],
        response_format: str = "text",
        tool_context: Dict[str, Any] | None = None,
    ) -> str:
        """格式化搜索结果，支持 text/json 两种模式。"""
        if response_format == "json":
            payload = {
                "query": result.get("query", ""),
                "source": result.get("source", "unknown"),
                "total_time": result.get("total_time", 0),
                "results_count": len(result.get("results", [])),
                "tool_context": tool_context or {},
                "results": [
                    {
                        "rank": i,
                        "title": item.get("title", "N/A"),
                        "url": item.get("url", "N/A"),
                        "content": item.get("cleaned_content", item.get("snippet", "")),
                        "similarity": item.get(
                            "similarity_score",
                            item.get("similarity", 0),
                        ),
                        "metadata": item.get("metadata", {}),
                    }
                    for i, item in enumerate(result.get("results", []), 1)
                ],
            }
            return json.dumps(payload, ensure_ascii=False, indent=2)

        lines = [
            f"查询: {result.get('query', '')}",
            f"来源: {result.get('source', 'unknown')}",
            f"总耗时: {result.get('total_time', 0):.2f}秒",
            f"结果数量: {len(result.get('results', []))}",
            "",
            "搜索结果:",
            "",
        ]

        for i, item in enumerate(result.get("results", []), 1):
            lines.append(f"{i}. {item.get('title', 'N/A')}")
            lines.append(f"   URL: {item.get('url', 'N/A')}")
            content = item.get("cleaned_content", item.get("snippet", "N/A"))
            lines.append(f"   内容: {content}")
            lines.append(f"   相似度: {item.get('similarity_score', item.get('similarity', 0)):.3f}")
            lines.append("")

        return "\n".join(lines)

    def _format_vector_results(self, results: List[Dict[str, Any]]) -> str:
        """格式化向量查询结果为文本"""
        lines = [f"找到 {len(results)} 条相关结果:", ""]

        for i, item in enumerate(results, 1):
            lines.append(f"{i}. 相似度: {item.get('similarity', 0):.3f}")
            metadata = item.get("metadata") or {}
            url = metadata.get("source_url", metadata.get("url", "N/A"))
            lines.append(f"   URL: {url}")
            doc = item.get("text", item.get("document", "N/A"))
            lines.append(f"   内容: {doc[:200]}")
            lines.append("")

        return "\n".join(lines)
