"""
向量库服务
"""

from typing import Dict, List, Optional
from my_ai_search.vector import (
    get_collection,
    get_collection_stats,
    clear_collection,
    store_documents,
    upsert_documents,
)
from my_ai_search.process.process import chunk_text


class VectorService:
    """向量库服务类"""

    def get_stats(self) -> Dict:
        """
        获取向量库统计信息

        Returns:
            统计信息字典
        """
        return get_collection_stats()

    def list_documents(self, page: int = 1, size: int = 20, query: str = None) -> Dict:
        """
        查询文档列表（分页）

        Args:
            page: 页码
            size: 每页大小
            query: 查询字符串（可选）

        Returns:
            文档列表字典
        """
        try:
            collection = get_collection()
            raw_total = collection.count()
            result = collection.get()
            all_documents = self._build_document_items(result)

            if query:
                query_text = query.strip().lower()
                all_documents = [
                    doc
                    for doc in all_documents
                    if query_text in doc["id"].lower()
                    or query_text in doc["text"].lower()
                    or query_text in str(doc.get("metadata", {})).lower()
                ]

            total = len(all_documents) if query else raw_total
            offset = (page - 1) * size
            documents = all_documents[offset : offset + size]

            return {
                "total": total,
                "page": page,
                "size": size,
                "documents": documents,
            }
        except Exception as e:
            raise Exception(f"Failed to list documents: {str(e)}")

    def add_document(self, data: Dict) -> Dict:
        """
        添加文档到向量库

        Args:
            data: 文档数据，格式为 {"text": str, "url": str, "chunk_id": int, "metadata": dict}

        Returns:
            添加结果
        """
        try:
            text = data.get("text", "")
            url = data.get("url", "unknown")
            chunk_id = data.get("chunk_id", 0)
            metadata = data.get("metadata", {})

            if not text:
                return {"success": False, "error": "Text is required"}

            chunk = self._build_chunk(
                text=text,
                url=url,
                chunk_id=chunk_id,
                metadata=metadata,
                doc_id=data.get("id"),
            )

            ids = upsert_documents([chunk])

            return {
                "success": True,
                "document_id": ids[0] if ids else "",
            }
        except Exception as e:
            return {"success": False, "error": str(e)}

    def add_documents(self, documents: List[Dict]) -> Dict:
        """
        批量添加文档到向量库

        Args:
            documents: 文档列表

        Returns:
            添加结果
        """
        try:
            if not documents:
                return {"success": False, "error": "Documents list is empty"}

            chunks = []
            for doc in documents:
                text = doc.get("text", "")
                if not text:
                    continue
                chunks.append(
                    self._build_chunk(
                        text=text,
                        url=doc.get("url", "unknown"),
                        chunk_id=doc.get("chunk_id", 0),
                        metadata=doc.get("metadata", {}),
                        doc_id=doc.get("id"),
                    )
                )

            if not chunks:
                return {"success": False, "error": "All documents are empty"}

            ids = upsert_documents(chunks)

            return {
                "success": True,
                "document_ids": ids,
                "count": len(ids),
            }
        except Exception as e:
            return {"success": False, "error": str(e)}

    def delete_documents(self, ids: List[str]) -> Dict:
        """
        删除文档

        Args:
            ids: 文档ID列表

        Returns:
            删除结果
        """
        try:
            collection = get_collection()
            collection.delete(ids=ids)

            return {
                "success": True,
                "deleted_count": len(ids),
            }
        except Exception as e:
            return {"success": False, "error": str(e)}

    def update_document(self, doc_id: str, data: Dict) -> Dict:
        """
        更新单个文档
        """
        try:
            existing = self.get_document_by_id(doc_id)
            if not existing:
                return {"success": False, "error": "Document not found"}

            text = data.get("text", existing.get("text", ""))
            if not text:
                return {"success": False, "error": "Text is required"}

            metadata = existing.get("metadata", {}).copy()
            metadata.update(data.get("metadata", {}))
            url = data.get("url") or metadata.get("source_url") or "unknown"
            chunk_id = data.get("chunk_id", metadata.get("chunk_id", 0))

            chunk = self._build_chunk(
                text=text,
                url=url,
                chunk_id=chunk_id,
                metadata=metadata,
                doc_id=doc_id,
            )
            ids = upsert_documents([chunk])
            return {"success": True, "document_id": ids[0] if ids else doc_id}
        except Exception as e:
            return {"success": False, "error": str(e)}

    def create_manual_entry(self, data: Dict) -> Dict:
        """
        手动录入文本并向量化，可选自动分块。
        """
        try:
            text = (data.get("text") or "").strip()
            if not text:
                return {"success": False, "error": "Text is required"}

            url = (data.get("url") or "manual://entry").strip() or "manual://entry"
            metadata = data.get("metadata", {}) or {}
            auto_chunk = bool(data.get("auto_chunk", False))

            chunks = []
            if auto_chunk:
                parts = chunk_text(text)
                for index, part in enumerate(parts):
                    chunks.append(
                        self._build_chunk(
                            text=part,
                            url=url,
                            chunk_id=index,
                            metadata={
                                **metadata,
                                "source": "manual",
                                "manual_entry": True,
                                "total_chunks": len(parts),
                            },
                        )
                    )
            else:
                chunks.append(
                    self._build_chunk(
                        text=text,
                        url=url,
                        chunk_id=int(data.get("chunk_id", 0)),
                        metadata={
                            **metadata,
                            "source": "manual",
                            "manual_entry": True,
                        },
                        doc_id=data.get("id"),
                    )
                )

            ids = upsert_documents(chunks)
            return {
                "success": True,
                "document_ids": ids,
                "count": len(ids),
            }
        except Exception as e:
            return {"success": False, "error": str(e)}

    def clear_collection(self) -> Dict:
        """
        清空向量库集合

        Returns:
            清空结果
        """
        try:
            collection = get_collection()
            count = collection.count()
            clear_collection()

            return {
                "success": True,
                "cleared_count": count,
            }
        except Exception as e:
            return {"success": False, "error": str(e)}

    def get_document_by_id(self, doc_id: str) -> Optional[Dict]:
        """
        根据ID获取文档

        Args:
            doc_id: 文档ID

        Returns:
            文档信息
        """
        try:
            collection = get_collection()
            result = collection.get(ids=[doc_id])

            if result and result["ids"]:
                return {
                    "id": result["ids"][0],
                    "text": result["documents"][0] if result.get("documents") else "",
                    "metadata": result["metadatas"][0]
                    if result.get("metadatas")
                    else {},
                }
            return None
        except Exception as e:
            raise Exception(f"Failed to get document: {str(e)}")

    @staticmethod
    def _build_document_items(result: Optional[Dict]) -> List[Dict]:
        documents = []
        if result and result.get("ids"):
            for i, doc_id in enumerate(result["ids"]):
                metadata = result["metadatas"][i] if result.get("metadatas") else {}
                documents.append(
                    {
                        "id": doc_id,
                        "text": result["documents"][i] if result.get("documents") else "",
                        "metadata": metadata or {},
                        "url": (metadata or {}).get("source_url"),
                    }
                )
        return documents

    @staticmethod
    def _build_chunk(
        text: str,
        url: str,
        chunk_id: int,
        metadata: Optional[Dict] = None,
        doc_id: Optional[str] = None,
    ) -> Dict:
        chunk_metadata = (metadata or {}).copy()
        chunk_metadata.setdefault("source_url", url)
        chunk_metadata.setdefault("chunk_id", chunk_id)
        return {
            "id": doc_id,
            "text": text,
            "snippet": text[:200].strip(),
            "url": url,
            "chunk_id": chunk_id,
            "metadata": chunk_metadata,
        }
