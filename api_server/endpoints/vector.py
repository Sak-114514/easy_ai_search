"""
向量库管理端点

提供向量库的 CRUD 操作
"""

from fastapi import APIRouter, HTTPException, Depends, Query, Body
from typing import Optional, List
from ..services.vector_service import VectorService
from ..middleware.auth import get_api_key, require_admin
from ..middleware.errors import build_internal_http_exception

router = APIRouter()
vector_service = VectorService()


@router.get("/stats")
async def get_vector_stats(api_key: str = Depends(get_api_key)):
    """获取向量库统计信息"""
    try:
        return vector_service.get_stats()
    except Exception as e:
        raise build_internal_http_exception("Get vector stats", e)


@router.get("/documents")
async def list_documents(
    page: int = Query(1, ge=1),
    size: int = Query(20, ge=1, le=100),
    query: Optional[str] = None,
    api_key: str = Depends(require_admin),
):
    """查询文档列表"""
    try:
        return vector_service.list_documents(page, size, query)
    except Exception as e:
        raise build_internal_http_exception("List vector documents", e)


@router.post("/documents")
async def add_document(data: dict, api_key: str = Depends(require_admin)):
    """添加文档"""
    try:
        return vector_service.add_document(data)
    except Exception as e:
        raise build_internal_http_exception("Add vector document", e)


@router.post("/documents/manual")
async def add_manual_document(data: dict, api_key: str = Depends(require_admin)):
    """手动录入文档并向量化"""
    try:
        return vector_service.create_manual_entry(data)
    except Exception as e:
        raise build_internal_http_exception("Create manual vector document", e)


@router.get("/documents/{doc_id:path}")
async def get_document(doc_id: str, api_key: str = Depends(require_admin)):
    """根据 ID 获取文档"""
    try:
        document = vector_service.get_document_by_id(doc_id)
        if not document:
            raise HTTPException(status_code=404, detail="Document not found")
        return document
    except HTTPException:
        raise
    except Exception as e:
        raise build_internal_http_exception("Get vector document", e)


@router.put("/documents/{doc_id:path}")
async def update_document(doc_id: str, data: dict, api_key: str = Depends(require_admin)):
    """更新文档"""
    try:
        result = vector_service.update_document(doc_id, data)
        if not result.get("success"):
            if result.get("error") == "Document not found":
                raise HTTPException(status_code=404, detail=result["error"])
            raise HTTPException(status_code=400, detail=result.get("error", "Update failed"))
        return result
    except HTTPException:
        raise
    except Exception as e:
        raise build_internal_http_exception("Update vector document", e)


@router.delete("/documents")
async def delete_documents(
    ids: List[str] = Body(...), api_key: str = Depends(require_admin)
):
    """删除文档"""
    try:
        return vector_service.delete_documents(ids)
    except Exception as e:
        raise build_internal_http_exception("Delete vector documents", e)


@router.delete("/collection")
async def clear_collection(api_key: str = Depends(require_admin)):
    """清空集合"""
    try:
        vector_service.clear_collection()
        return {"success": True, "message": "Collection cleared"}
    except Exception as e:
        raise build_internal_http_exception("Clear vector collection", e)
