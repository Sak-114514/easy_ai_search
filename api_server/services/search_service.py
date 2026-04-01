"""
搜索服务

封装 OpenSearch 核心搜索功能
"""

import asyncio
import uuid
from typing import Dict, Optional
from my_ai_search.main import search_ai_async
from ..services.log_service import LogService

search_ai = search_ai_async


class SearchService:
    """搜索服务类"""

    def __init__(self, log_service: Optional[LogService] = None):
        self.log_service = log_service or LogService()
        self._async_tasks = {}

    async def search(
        self,
        query: str,
        max_results: Optional[int] = None,
        use_cache: bool = True,
        skip_local: bool = False,
        disable_deep_process: bool = False,
        client_type: str = "rest",
        engines: Optional[str] = None,
        mode: str = "balanced",
        tool_context: Optional[Dict] = None,
        token_name: Optional[str] = None,
    ) -> Dict:
        """
        执行同步搜索

        Args:
            query: 搜索查询
            max_results: 最大结果数
            use_cache: 是否使用缓存
            skip_local: 是否跳过本地搜索
            disable_deep_process: 是否禁用深度处理
            client_type: 客户端类型
            engines: 指定搜索引擎（逗号分隔）
            mode: 搜索模式
            tool_context: 工具调用附加上下文

        Returns:
            搜索结果
        """
        result = await search_ai(
            query=query,
            max_results=max_results,
            use_cache=use_cache,
            skip_local=skip_local,
            disable_deep_process=disable_deep_process,
            engines=engines,
            mode=mode,
            client_type=client_type,
            tool_context=tool_context,
        )

        # 记录日志
        await self.log_service.log_search(
            query=query,
            max_results=max_results or 5,
            source=result.get("source", "online"),
            total_time=result.get("total_time", 0),
            results_count=len(result.get("results", [])),
            client_type=client_type,
            token_name=token_name,
        )

        return result

    async def submit_async_search(
        self,
        query: str,
        max_results: Optional[int] = None,
        use_cache: bool = True,
        skip_local: bool = False,
        disable_deep_process: bool = False,
        mode: str = "balanced",
    ) -> str:
        """
        提交异步搜索任务

        Args:
            query: 搜索查询
            max_results: 最大结果数
            use_cache: 是否使用缓存
            skip_local: 是否跳过本地搜索

        Returns:
            任务 ID
        """
        task_id = str(uuid.uuid4())
        self._async_tasks[task_id] = {
            "status": "pending",
            "progress": 0,
            "result": None,
            "error": None,
        }

        # 在后台执行搜索
        asyncio.create_task(
            self._execute_async_search(
                task_id, query, max_results, use_cache, skip_local, disable_deep_process, mode
            )
        )

        return task_id

    async def _execute_async_search(
        self,
        task_id: str,
        query: str,
        max_results: Optional[int],
        use_cache: bool,
        skip_local: bool,
        disable_deep_process: bool,
        mode: str,
    ):
        """执行异步搜索"""
        try:
            self._async_tasks[task_id]["status"] = "in_progress"
            self._async_tasks[task_id]["progress"] = 50

            result = await self.search(
                query=query,
                max_results=max_results,
                use_cache=use_cache,
                skip_local=skip_local,
                disable_deep_process=disable_deep_process,
                client_type="rest",
                mode=mode,
            )

            self._async_tasks[task_id]["status"] = "completed"
            self._async_tasks[task_id]["progress"] = 100
            self._async_tasks[task_id]["result"] = result
        except Exception as e:
            self._async_tasks[task_id]["status"] = "failed"
            self._async_tasks[task_id]["error"] = str(e)

    async def get_async_search_status(self, task_id: str) -> Dict:
        """
        查询异步搜索任务状态

        Args:
            task_id: 任务 ID

        Returns:
            任务状态
        """
        if task_id not in self._async_tasks:
            raise ValueError(f"Task not found: {task_id}")

        status = self._async_tasks[task_id].copy()
        status["task_id"] = task_id  # 确保包含task_id字段
        return status
