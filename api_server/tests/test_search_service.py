"""
搜索服务测试
"""

import pytest
import asyncio
from unittest.mock import Mock, patch, AsyncMock
from api_server.services.search_service import SearchService


class TestSearchService:
    """搜索服务测试类"""

    @pytest.fixture
    def search_service(self):
        """创建搜索服务实例"""
        return SearchService()

    @pytest.mark.asyncio
    async def test_search_success(self, search_service):
        """测试搜索成功"""
        mock_result = {
            "query": "Python",
            "results": [
                {
                    "title": "Python教程",
                    "url": "https://example.com/python",
                    "snippet": "Python是一种编程语言",
                }
            ],
            "total_time": 1.5,
            "source": "online",
        }

        with patch(
            "api_server.services.search_service.search_ai", return_value=mock_result
        ):
            with patch.object(
                search_service.log_service, "log_search", new_callable=AsyncMock
            ):
                result = await search_service.search(
                    query="Python",
                    max_results=5,
                    use_cache=True,
                    skip_local=False,
                    client_type="rest",
                )

                assert result["query"] == "Python"
                assert result["source"] == "online"
                assert len(result["results"]) == 1

    @pytest.mark.asyncio
    async def test_search_passes_disable_deep_process_flag(self, search_service):
        """测试 disable_deep_process 参数透传"""
        mock_result = {
            "query": "Python",
            "results": [],
            "total_time": 0.1,
            "source": "online",
        }

        with patch(
            "api_server.services.search_service.search_ai", return_value=mock_result
        ) as mock_search_ai:
            with patch.object(
                search_service.log_service, "log_search", new_callable=AsyncMock
            ):
                await search_service.search(
                    query="Python",
                    max_results=5,
                    use_cache=True,
                    skip_local=False,
                    disable_deep_process=True,
                    client_type="rest",
                )

        assert mock_search_ai.call_count == 1
        assert mock_search_ai.call_args.kwargs["disable_deep_process"] is True

    @pytest.mark.asyncio
    async def test_search_passes_mode_flag(self, search_service):
        """测试 mode 参数透传"""
        mock_result = {
            "query": "Python",
            "results": [],
            "total_time": 0.1,
            "source": "online",
        }

        with patch(
            "api_server.services.search_service.search_ai", return_value=mock_result
        ) as mock_search_ai:
            with patch.object(
                search_service.log_service, "log_search", new_callable=AsyncMock
            ):
                await search_service.search(
                    query="Python",
                    max_results=5,
                    use_cache=True,
                    skip_local=False,
                    mode="fast",
                    client_type="rest",
                )

        assert mock_search_ai.call_count == 1
        assert mock_search_ai.call_args.kwargs["mode"] == "fast"

    @pytest.mark.asyncio
    async def test_search_logs_token_name(self, search_service):
        mock_result = {
            "query": "Python",
            "results": [],
            "total_time": 0.1,
            "source": "online",
        }

        with patch(
            "api_server.services.search_service.search_ai", return_value=mock_result
        ):
            with patch.object(
                search_service.log_service, "log_search", new_callable=AsyncMock
            ) as mock_log:
                await search_service.search(
                    query="Python",
                    max_results=3,
                    use_cache=True,
                    skip_local=False,
                    client_type="rest",
                    token_name="token-user-a",
                )

        assert mock_log.await_count == 1
        assert mock_log.await_args.kwargs["token_name"] == "token-user-a"

    @pytest.mark.asyncio
    async def test_search_empty_query(self, search_service):
        """测试空查询"""
        with pytest.raises(Exception):
            await search_service.search(
                query="",
                max_results=5,
                use_cache=True,
                skip_local=False,
                client_type="rest",
            )

    @pytest.mark.asyncio
    async def test_submit_async_search(self, search_service):
        """测试提交异步搜索任务"""
        task_id = await search_service.submit_async_search(
            query="Python",
            max_results=5,
            use_cache=True,
            skip_local=False,
        )

        assert task_id is not None
        assert len(task_id) > 0
        assert task_id in search_service._async_tasks

    @pytest.mark.asyncio
    async def test_get_async_search_status(self, search_service):
        """测试查询异步搜索任务状态"""
        task_id = await search_service.submit_async_search(
            query="Python",
            max_results=5,
            use_cache=True,
            skip_local=False,
        )

        status = await search_service.get_async_search_status(task_id)

        assert "status" in status
        assert "progress" in status
        assert "result" in status
        assert "error" in status

    @pytest.mark.asyncio
    async def test_get_async_search_status_not_found(self, search_service):
        """测试查询不存在的任务"""
        with pytest.raises(ValueError):
            await search_service.get_async_search_status("invalid-task-id")

    @pytest.mark.asyncio
    async def test_async_search_execution(self, search_service):
        """测试异步搜索执行流程"""
        mock_result = {
            "query": "Python",
            "results": [
                {
                    "title": "Python教程",
                    "url": "https://example.com/python",
                    "snippet": "Python是一种编程语言",
                }
            ],
            "total_time": 1.5,
            "source": "online",
        }

        with patch(
            "api_server.services.search_service.search_ai", return_value=mock_result
        ):
            with patch.object(
                search_service.log_service, "log_search", new_callable=AsyncMock
            ):
                task_id = await search_service.submit_async_search(
                    query="Python",
                    max_results=5,
                    use_cache=True,
                    skip_local=False,
                )

                # 等待任务完成
                await asyncio.sleep(0.1)

                status = await search_service.get_async_search_status(task_id)
                assert status["status"] == "completed"
                assert status["progress"] == 100
                assert status["result"] is not None
