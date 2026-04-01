"""
算法管理端点
"""

from fastapi import APIRouter, HTTPException, Depends
from ..services.algorithm_service import AlgorithmService
from ..middleware.auth import require_admin
from ..middleware.errors import build_internal_http_exception

router = APIRouter()
algorithm_service = AlgorithmService()


@router.get("/")
async def get_algorithms(api_key: str = Depends(require_admin)):
    """获取算法参数"""
    try:
        return algorithm_service.get_params()
    except Exception as e:
        raise build_internal_http_exception("Get algorithms", e)


@router.put("/")
async def update_algorithms(data: dict, api_key: str = Depends(require_admin)):
    """更新算法参数"""
    try:
        return algorithm_service.update_params(data)
    except Exception as e:
        raise build_internal_http_exception("Update algorithms", e)


@router.post("/reset")
async def reset_algorithms(api_key: str = Depends(require_admin)):
    """重置算法参数为默认值"""
    try:
        algorithm_service.reset_params()
        return {"success": True, "message": "Algorithms reset to default"}
    except Exception as e:
        raise build_internal_http_exception("Reset algorithms", e)
