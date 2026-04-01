"""
SSE (Server-Sent Events) 流式响应处理器

实现MCP协议的流式响应
"""

import json
import logging
from typing import Any, AsyncGenerator, Dict

logger = logging.getLogger(__name__)


class SSEHandler:
    """SSE处理器"""

    @staticmethod
    async def send_event(event_type: str, data: Dict[str, Any]) -> str:
        """
        构建SSE事件

        Args:
            event_type: 事件类型
            data: 事件数据

        Returns:
            SSE格式字符串
        """
        return f"event: {event_type}\ndata: {json.dumps(data, ensure_ascii=False)}\n\n"

    @staticmethod
    async def send_result(result: Any) -> str:
        """发送结果事件"""
        return await SSEHandler.send_event("result", {"content": result})

    @staticmethod
    async def send_error(error: str) -> str:
        """发送错误事件"""
        return await SSEHandler.send_event("error", {"message": error})

    @staticmethod
    async def send_progress(progress: int, message: str) -> str:
        """发送进度事件"""
        return await SSEHandler.send_event(
            "progress", {"progress": progress, "message": message}
        )


async def mcp_sse_stream(query: str, tool_handler) -> AsyncGenerator[str, None]:
    """
    MCP SSE流式响应生成器

    Args:
        query: 查询字符串
        tool_handler: 工具处理器

    Yields:
        SSE格式字符串
    """
    try:
        yield await SSEHandler.send_event("start", {"query": query})

        yield await SSEHandler.send_progress(10, "开始搜索...")

        result = await tool_handler.call_tool(
            name="search",
            arguments={
                "query": query,
                "max_results": 5,
                "use_cache": True,
                "skip_local": False,
            },
        )

        yield await SSEHandler.send_progress(80, "搜索完成，正在处理结果...")

        for item in result:
            if item.get("type") == "text":
                yield await SSEHandler.send_result(item.get("text", ""))

        yield await SSEHandler.send_progress(100, "处理完成")

        yield await SSEHandler.send_event("end", {"status": "completed"})

    except Exception as e:
        logger.error(f"SSE流式响应错误: {str(e)}")
        yield await SSEHandler.send_error(str(e))
