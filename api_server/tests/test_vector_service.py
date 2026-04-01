"""
向量服务测试
"""

import pytest
from unittest.mock import Mock, patch
from api_server.services.vector_service import VectorService


class TestVectorService:
    """向量服务测试类"""

    @pytest.fixture
    def vector_service(self):
        """创建向量服务实例"""
        return VectorService()

    @patch("api_server.services.vector_service.get_collection_stats")
    def test_get_stats(self, mock_get_stats, vector_service):
        """测试获取向量库统计"""
        mock_get_stats.return_value = {
            "count": 100,
            "name": "ai_search",
            "metadata": {"description": "AI Search Vector Store"},
        }

        stats = vector_service.get_stats()

        assert stats["count"] == 100
        assert stats["name"] == "ai_search"
        assert "metadata" in stats

    @patch("api_server.services.vector_service.get_collection")
    def test_list_documents(self, mock_get_collection, vector_service):
        """测试查询文档列表"""
        mock_collection = Mock()
        mock_collection.count.return_value = 100
        mock_collection.get.return_value = {
            "ids": ["doc1", "doc2"],
            "documents": ["Document 1", "Document 2"],
            "metadatas": [
                {"url": "https://example.com/1"},
                {"url": "https://example.com/2"},
            ],
        }
        mock_get_collection.return_value = mock_collection

        result = vector_service.list_documents(page=1, size=20)

        assert result["total"] == 100
        assert result["page"] == 1
        assert result["size"] == 20
        assert len(result["documents"]) == 2

    @patch("api_server.services.vector_service.upsert_documents")
    def test_add_document(self, mock_upsert, vector_service):
        """测试添加单个文档"""
        mock_upsert.return_value = ["doc1"]

        data = {
            "text": "This is a test document",
            "url": "https://example.com/test",
            "chunk_id": 0,
            "metadata": {"author": "test"},
        }

        result = vector_service.add_document(data)

        assert result["success"] is True
        assert "document_id" in result

    def test_add_document_empty_text(self, vector_service):
        """测试添加空文本文档"""
        data = {
            "text": "",
            "url": "https://example.com/test",
            "chunk_id": 0,
        }

        result = vector_service.add_document(data)

        assert result["success"] is False
        assert "error" in result

    @patch("api_server.services.vector_service.upsert_documents")
    def test_add_documents(self, mock_upsert, vector_service):
        """测试批量添加文档"""
        mock_upsert.return_value = ["doc1", "doc2", "doc3"]

        documents = [
            {
                "text": f"Document {i}",
                "url": f"https://example.com/{i}",
                "chunk_id": i,
            }
            for i in range(3)
        ]

        result = vector_service.add_documents(documents)

        assert result["success"] is True
        assert result["count"] == 3
        assert len(result["document_ids"]) == 3

    def test_add_documents_empty_list(self, vector_service):
        """测试添加空文档列表"""
        result = vector_service.add_documents([])

        assert result["success"] is False
        assert "error" in result

    @patch("api_server.services.vector_service.get_collection")
    def test_delete_documents(self, mock_get_collection, vector_service):
        """测试删除文档"""
        mock_collection = Mock()
        mock_get_collection.return_value = mock_collection

        result = vector_service.delete_documents(["doc1", "doc2"])

        assert result["success"] is True
        assert result["deleted_count"] == 2
        mock_collection.delete.assert_called_once_with(ids=["doc1", "doc2"])

    @patch("api_server.services.vector_service.clear_collection")
    @patch("api_server.services.vector_service.get_collection")
    def test_clear_collection(self, mock_get_collection, mock_clear, vector_service):
        """测试清空向量库"""
        mock_collection = Mock()
        mock_collection.count.return_value = 100
        mock_get_collection.return_value = mock_collection

        result = vector_service.clear_collection()

        assert result["success"] is True
        assert result["cleared_count"] == 100
        mock_clear.assert_called_once()

    @patch("api_server.services.vector_service.get_collection")
    def test_get_document_by_id(self, mock_get_collection, vector_service):
        """测试根据ID获取文档"""
        mock_collection = Mock()
        mock_collection.get.return_value = {
            "ids": ["doc1"],
            "documents": ["Test document content"],
            "metadatas": [{"url": "https://example.com/test", "chunk_id": 0}],
        }
        mock_get_collection.return_value = mock_collection

        doc = vector_service.get_document_by_id("doc1")

        assert doc is not None
        assert doc["id"] == "doc1"
        assert doc["text"] == "Test document content"

    @patch("api_server.services.vector_service.get_collection")
    def test_get_document_by_id_not_found(self, mock_get_collection, vector_service):
        """测试获取不存在的文档"""
        mock_collection = Mock()
        mock_collection.get.return_value = {"ids": []}
        mock_get_collection.return_value = mock_collection

        doc = vector_service.get_document_by_id("nonexistent")

        assert doc is None

    @patch("api_server.services.vector_service.upsert_documents")
    def test_add_document_with_metadata(self, mock_upsert, vector_service):
        """测试添加带元数据的文档"""
        mock_upsert.return_value = ["doc1"]

        data = {
            "text": "Test document",
            "url": "https://example.com/test",
            "chunk_id": 0,
            "metadata": {
                "author": "John Doe",
                "date": "2026-03-20",
                "tags": ["python", "test"],
            },
        }

        result = vector_service.add_document(data)

        assert result["success"] is True
        mock_upsert.assert_called_once()

    @patch("api_server.services.vector_service.get_collection")
    def test_list_documents_with_query(self, mock_get_collection, vector_service):
        """测试按关键字过滤文档"""
        mock_collection = Mock()
        mock_collection.get.return_value = {
            "ids": ["doc1", "doc2"],
            "documents": ["Python document", "Java document"],
            "metadatas": [
                {"source_url": "https://example.com/python"},
                {"source_url": "https://example.com/java"},
            ],
        }
        mock_get_collection.return_value = mock_collection

        result = vector_service.list_documents(page=1, size=20, query="python")

        assert result["total"] == 1
        assert result["documents"][0]["id"] == "doc1"

    @patch("api_server.services.vector_service.get_collection")
    @patch("api_server.services.vector_service.upsert_documents")
    def test_update_document(self, mock_upsert, mock_get_collection, vector_service):
        """测试更新文档"""
        mock_collection = Mock()
        mock_collection.get.return_value = {
            "ids": ["doc1"],
            "documents": ["Old text"],
            "metadatas": [{"source_url": "https://example.com/test", "chunk_id": 0}],
        }
        mock_get_collection.return_value = mock_collection
        mock_upsert.return_value = ["doc1"]

        result = vector_service.update_document(
            "doc1",
            {
                "text": "Updated text",
                "url": "https://example.com/new",
                "chunk_id": 3,
                "metadata": {"source": "manual"},
            },
        )

        assert result["success"] is True
        assert result["document_id"] == "doc1"
        mock_upsert.assert_called_once()

    @patch("api_server.services.vector_service.upsert_documents")
    @patch("api_server.services.vector_service.chunk_text")
    def test_create_manual_entry_auto_chunk(
        self, mock_chunk_text, mock_upsert, vector_service
    ):
        """测试手动录入自动分块"""
        mock_chunk_text.return_value = ["part1", "part2"]
        mock_upsert.return_value = ["doc1", "doc2"]

        result = vector_service.create_manual_entry(
            {
                "url": "manual://note",
                "text": "long text",
                "auto_chunk": True,
                "metadata": {"category": "manual"},
            }
        )

        assert result["success"] is True
        assert result["count"] == 2
        mock_upsert.assert_called_once()
