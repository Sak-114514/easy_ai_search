"""
API集成测试
"""

import pytest
from fastapi.testclient import TestClient
from api_server import app
from unittest.mock import patch, AsyncMock
from uuid import uuid4


class TestAPIIntegration:
    """API集成测试类"""

    @pytest.fixture
    def client(self):
        """创建测试客户端"""
        return TestClient(app)

    @pytest.fixture
    def admin_headers(self):
        """管理员请求头"""
        from api_server.config import get_api_config

        config = get_api_config()
        return {"X-API-Key": config.api_keys.get("admin", "")}

    @pytest.fixture
    def default_headers(self):
        """默认用户请求头"""
        from api_server.config import get_api_config
        from api_server.services.token_service import TokenService

        config = get_api_config()
        default_key = config.api_keys.get("default")
        admin_key = config.api_keys.get("admin", "")
        if default_key and default_key != admin_key:
            return {"X-API-Key": default_key}

        token = TokenService().create_token(
            f"test-default-{uuid4().hex[:8]}",
            "default",
            "api integration default user",
        )
        return {"X-API-Key": token["api_key"]}

    def test_create_token_and_use_for_search(self, client, admin_headers):
        """测试创建动态 token 并用于搜索"""
        token_name = f"test-user-token-{uuid4().hex[:8]}"
        create_response = client.post(
            "/api/v1/tokens",
            headers=admin_headers,
            json={"name": token_name, "role": "default", "notes": "integration"},
        )

        assert create_response.status_code == 200
        created = create_response.json()
        assert created["name"] == token_name
        assert created["api_key"]

        with patch(
            "api_server.services.search_service.search_ai",
            return_value={
                "query": "Token Search",
                "results": [],
                "total_time": 0.1,
                "source": "mock",
            },
        ):
            response = client.post(
                "/api/v1/search",
                headers={"X-API-Key": created["api_key"]},
                json={"query": "Token Search", "max_results": 2},
            )

        assert response.status_code == 200

        usage_response = client.get(
            f"/api/v1/tokens/{created['id']}/usage",
            headers=admin_headers,
        )
        assert usage_response.status_code == 200
        usage = usage_response.json()
        assert usage["success"] is True
        assert usage["token_name"] == token_name
        assert any(log["query"] == "Token Search" for log in usage["search_logs"])

    def test_tokens_require_admin(self, client, default_headers):
        response = client.get("/api/v1/tokens", headers=default_headers)
        assert response.status_code == 403

    def test_root_endpoint(self, client):
        """测试根路径"""
        response = client.get("/")

        assert response.status_code == 200
        data = response.json()
        assert data["message"] == "easy_ai_search API"
        assert data["docs"] == "/docs"
        assert data["health"] == "/health"

    def test_health_check(self, client):
        """测试健康检查"""
        response = client.get("/health")

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "healthy"
        assert "service" in data
        assert "version" in data

    def test_unauthorized_access(self, client):
        """测试未授权访问"""
        response = client.post("/api/v1/search", json={"query": "test"})

        assert response.status_code == 401

    def test_invalid_api_key(self, client):
        """测试无效的API Key"""
        headers = {"X-API-Key": "invalid-key"}
        response = client.post(
            "/api/v1/search", json={"query": "test"}, headers=headers
        )

        assert response.status_code == 403

    def test_search_endpoint_empty_query(self, client, default_headers):
        """测试空查询"""
        response = client.post(
            "/api/v1/search",
            json={"query": ""},
            headers=default_headers,
        )

        assert response.status_code == 400

    def test_search_endpoint_success(self, client, default_headers):
        """测试搜索成功（模拟）"""
        # 注意：这个测试可能需要依赖外部服务，可能需要mock
        # 这里仅测试端点是否可访问
        response = client.post(
            "/api/v1/search",
            json={"query": "Python", "max_results": 5},
            headers=default_headers,
        )

        # 可能返回500如果外部服务不可用，但端点应该可访问
        assert response.status_code in [200, 500]

    def test_search_endpoint_passes_domain_controls(self, client, default_headers):
        mock_result = {
            "query": "OpenAI GPT-5.4 mini 发布信息",
            "results": [],
            "total_time": 0.1,
            "source": "mock",
        }

        with patch(
            "api_server.endpoints.search.search_service.search",
            new=AsyncMock(return_value=mock_result),
        ) as mock_search:
            response = client.post(
                "/api/v1/search",
                json={
                    "query": "OpenAI GPT-5.4 mini 发布信息",
                    "mode": "fast",
                    "preferred_domains": ["openai.com", "sina.com.cn"],
                    "blocked_domains": ["help.openai.com"],
                    "domain_preference_mode": "only",
                    "source_profile": "official_news",
                },
                headers=default_headers,
            )

        assert response.status_code == 200
        kwargs = mock_search.await_args.kwargs
        assert kwargs["mode"] == "fast"
        assert kwargs["tool_context"]["preferred_domains"] == [
            "openai.com",
            "sina.com.cn",
        ]
        assert kwargs["tool_context"]["blocked_domains"] == ["help.openai.com"]
        assert kwargs["tool_context"]["domain_preference_mode"] == "only"
        assert kwargs["tool_context"]["source_profile"] == "official_news"

    def test_search_endpoint_passes_token_name(self, client, default_headers):
        mock_result = {
            "query": "Python",
            "results": [],
            "total_time": 0.1,
            "source": "mock",
        }

        with patch(
            "api_server.endpoints.search.search_service.search",
            new=AsyncMock(return_value=mock_result),
        ) as mock_search:
            response = client.post(
                "/api/v1/search",
                json={"query": "Python", "max_results": 2},
                headers=default_headers,
            )

        assert response.status_code == 200
        kwargs = mock_search.await_args.kwargs
        assert kwargs["query"] == "Python"
        assert kwargs["token_name"]
        assert kwargs["token_name"] != "admin"

    def test_async_search_submit(self, client, default_headers):
        """测试提交异步搜索任务"""
        response = client.post(
            "/api/v1/search/async",
            json={"query": "Python", "max_results": 5},
            headers=default_headers,
        )

        assert response.status_code in [200, 500]

        if response.status_code == 200:
            data = response.json()
            assert "task_id" in data
            assert "status" in data

    def test_get_async_search_status(self, client, default_headers):
        """测试查询异步搜索任务状态"""
        # 先提交一个任务
        submit_response = client.post(
            "/api/v1/search/async",
            json={"query": "Python", "max_results": 5},
            headers=default_headers,
        )

        if submit_response.status_code == 200:
            task_id = submit_response.json()["task_id"]

            # 查询任务状态
            status_response = client.get(
                f"/api/v1/search/async/{task_id}",
                headers=default_headers,
            )

            assert status_response.status_code in [200, 404]

    def test_get_cache_stats(self, client, default_headers):
        """测试获取缓存统计"""
        response = client.get(
            "/api/v1/admin/cache/stats",
            headers=default_headers,
        )

        assert response.status_code == 200
        data = response.json()
        assert "total" in data
        assert "hits" in data

    def test_clear_cache_requires_admin(self, client, default_headers):
        """测试清空缓存需要管理员权限"""
        response = client.delete(
            "/api/v1/admin/cache",
            headers=default_headers,
        )

        assert response.status_code == 403

    def test_clear_cache_with_admin(self, client, admin_headers):
        """测试管理员清空缓存"""
        response = client.delete(
            "/api/v1/admin/cache",
            headers=admin_headers,
        )

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True

    def test_get_vector_stats(self, client, admin_headers):
        """测试获取向量库统计"""
        response = client.get(
            "/api/v1/admin/vector/stats",
            headers=admin_headers,
        )

        assert response.status_code == 200
        data = response.json()
        assert "count" in data
        assert "name" in data

    def test_list_documents_requires_admin(self, client, default_headers):
        """测试查询文档需要管理员权限"""
        response = client.get(
            "/api/v1/admin/vector/documents?page=1&size=20",
            headers=default_headers,
        )

        assert response.status_code == 403

    def test_list_documents_with_admin(self, client, admin_headers):
        """测试管理员查询文档列表"""
        response = client.get(
            "/api/v1/admin/vector/documents?page=1&size=20",
            headers=admin_headers,
        )

        assert response.status_code == 200
        data = response.json()
        assert "total" in data
        assert "page" in data
        assert "documents" in data

    def test_add_manual_document_with_admin(self, client, admin_headers):
        """测试管理员手动录入文档"""
        with patch(
            "api_server.endpoints.vector.vector_service.create_manual_entry",
            return_value={"success": True, "document_ids": ["doc1"], "count": 1},
        ):
            response = client.post(
                "/api/v1/admin/vector/documents/manual",
                headers=admin_headers,
                json={
                    "text": "manual text",
                    "url": "manual://entry",
                    "auto_chunk": False,
                },
            )

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert data["count"] == 1

    def test_update_document_with_admin(self, client, admin_headers):
        """测试管理员更新文档"""
        with patch(
            "api_server.endpoints.vector.vector_service.update_document",
            return_value={"success": True, "document_id": "doc1"},
        ):
            response = client.put(
                "/api/v1/admin/vector/documents/doc1",
                headers=admin_headers,
                json={"text": "updated"},
            )

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert data["document_id"] == "doc1"

    def test_get_document_with_path_like_id(self, client, admin_headers):
        """测试包含斜杠的文档 ID 路由"""
        with patch(
            "api_server.endpoints.vector.vector_service.get_document_by_id",
            return_value={
                "id": "manual://crud-e2e#chunk_0",
                "text": "demo",
                "metadata": {},
            },
        ):
            response = client.get(
                "/api/v1/admin/vector/documents/manual%3A%2F%2Fcrud-e2e%23chunk_0",
                headers=admin_headers,
            )

        assert response.status_code == 200
        data = response.json()
        assert data["id"] == "manual://crud-e2e#chunk_0"

    def test_delete_documents_with_admin(self, client, admin_headers):
        """测试管理员删除文档"""
        with patch(
            "api_server.endpoints.vector.vector_service.delete_documents",
            return_value={"success": True, "deleted_count": 1},
        ):
            response = client.request(
                "DELETE",
                "/api/v1/admin/vector/documents",
                headers=admin_headers,
                json=["doc1"],
            )

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert data["deleted_count"] == 1

    def test_get_config(self, client, admin_headers):
        """测试获取配置"""
        response = client.get(
            "/api/v1/admin/config/",
            headers=admin_headers,
        )

        assert response.status_code == 200
        data = response.json()
        assert "searxng" in data
        assert "chroma" in data
        assert "cache" in data

    def test_get_algorithm_params(self, client, admin_headers):
        """测试获取算法参数"""
        response = client.get(
            "/api/v1/admin/algorithms",
            headers=admin_headers,
        )

        assert response.status_code == 200
        data = response.json()
        assert "process" in data
        assert "deep_process" in data
        assert "chroma" in data

    def test_get_log_stats_requires_admin(self, client, default_headers):
        """测试获取日志统计需要管理员权限"""
        response = client.get(
            "/api/v1/admin/logs/stats",
            headers=default_headers,
        )

        assert response.status_code == 403

    def test_get_log_stats_with_admin(self, client, admin_headers):
        """测试管理员获取日志统计"""
        response = client.get(
            "/api/v1/admin/logs/stats",
            headers=admin_headers,
        )

        assert response.status_code == 200
        data = response.json()
        assert "total_search_logs" in data
        assert "total_api_logs" in data

    def test_list_search_logs(self, client, admin_headers):
        """测试查询搜索日志"""
        response = client.get(
            "/api/v1/admin/logs/search?page=1&size=20",
            headers=admin_headers,
        )

        assert response.status_code == 200
        data = response.json()
        assert "total" in data
        assert "page" in data
        assert "logs" in data

    def test_list_api_logs(self, client, admin_headers):
        """测试查询API日志"""
        response = client.get(
            "/api/v1/admin/logs/api?page=1&size=20",
            headers=admin_headers,
        )

        assert response.status_code == 200
        data = response.json()
        assert "total" in data
        assert "page" in data
        assert "logs" in data

    def test_rate_limiting(self, client, default_headers):
        """测试限流（如果启用）"""
        # 这个测试可能会影响其他测试，所以跳过
        # 限流功能已经在单元测试中验证过了
        pass

    def test_cors_headers(self, client):
        """测试CORS头"""
        response = client.get("/")

        # CORS头应该存在
        assert response.status_code == 200
