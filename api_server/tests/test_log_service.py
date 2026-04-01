"""
日志服务测试
"""

import pytest
from datetime import datetime
from api_server.services.log_service import LogService
import os


class TestLogService:
    """日志服务测试类"""

    @pytest.fixture
    def log_service(self):
        """创建日志服务实例"""
        # 使用临时数据库
        os.environ["DATABASE_URL"] = "sqlite:///test_logs.db"
        return LogService()

    @pytest.mark.asyncio
    async def test_log_search(self, log_service):
        """测试记录搜索日志"""
        await log_service.log_search(
            query="Python",
            max_results=5,
            source="online",
            total_time=1.5,
            results_count=3,
            client_type="rest",
            ip="127.0.0.1",
        )

        stats = log_service.get_stats()
        assert stats["total_search_logs"] >= 1

    @pytest.mark.asyncio
    async def test_log_api(self, log_service):
        """测试记录API日志"""
        await log_service.log_api(
            endpoint="/api/v1/search",
            method="POST",
            status_code=200,
            response_time=0.5,
            client_type="rest",
            ip="127.0.0.1",
        )

        stats = log_service.get_stats()
        assert stats["total_api_logs"] >= 1

    def test_list_search_logs(self, log_service):
        """测试查询搜索日志"""
        result = log_service.list_search_logs(page=1, size=20)

        assert "total" in result
        assert "page" in result
        assert "size" in result
        assert "logs" in result
        assert result["page"] == 1
        assert result["size"] == 20

    def test_list_search_logs_with_filters(self, log_service):
        """测试带过滤条件的日志查询"""
        start_time = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
        end_time = datetime.now()

        result = log_service.list_search_logs(
            start_time=start_time,
            end_time=end_time,
            query="Python",
            page=1,
            size=10,
        )

        assert "logs" in result
        assert result["size"] == 10

    def test_list_api_logs(self, log_service):
        """测试查询API日志"""
        result = log_service.list_api_logs(page=1, size=20)

        assert "total" in result
        assert "page" in result
        assert "size" in result
        assert "logs" in result
        assert result["page"] == 1
        assert result["size"] == 20

    def test_list_api_logs_with_filters(self, log_service):
        """测试带过滤条件的API日志查询"""
        start_time = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
        end_time = datetime.now()

        result = log_service.list_api_logs(
            start_time=start_time,
            end_time=end_time,
            endpoint="/api/v1/search",
            page=1,
            size=10,
        )

        assert "logs" in result
        assert result["size"] == 10

    def test_get_stats(self, log_service):
        """测试获取统计信息"""
        stats = log_service.get_stats()

        assert "total_search_logs" in stats
        assert "total_api_logs" in stats
        assert "source_stats" in stats
        assert "avg_search_time" in stats
        assert "last_24h_searches" in stats

    @pytest.mark.asyncio
    async def test_multiple_logs_and_stats(self, log_service):
        """测试多条日志和统计"""
        # 记录多条日志
        for i in range(5):
            await log_service.log_search(
                query=f"Test query {i}",
                max_results=5,
                source="online",
                total_time=1.0 + i * 0.1,
                results_count=i,
                client_type="rest",
            )

        stats = log_service.get_stats()
        assert stats["total_search_logs"] >= 5

        # 测试分页
        result = log_service.list_search_logs(page=1, size=3)
        assert len(result["logs"]) <= 3
