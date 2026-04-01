"""
配置管理端点
"""

from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel, Field
from ..services.config_service import ConfigService
from ..middleware.auth import require_admin
from ..middleware.errors import build_internal_http_exception

router = APIRouter()
config_service = ConfigService()


class ConfigUpdateRequest(BaseModel):
    section: str = Field(..., description="配置分组，如 searxng/cache/chroma")
    data: dict = Field(default_factory=dict, description="该分组下的配置项")


@router.get("/")
async def get_config(api_key: str = Depends(require_admin)):
    """获取系统配置"""
    try:
        return config_service.get_config()
    except Exception as e:
        raise build_internal_http_exception("Get config", e)


@router.put("/")
async def update_config(
    payload: ConfigUpdateRequest, api_key: str = Depends(require_admin)
):
    """更新系统配置"""
    try:
        return config_service.update_config(payload.section, payload.data)
    except Exception as e:
        raise build_internal_http_exception("Update config", e)


@router.post("/reload")
async def reload_config(api_key: str = Depends(require_admin)):
    """重新加载配置"""
    try:
        config_service.reload_config()
        return {"success": True, "message": "Config reloaded"}
    except Exception as e:
        raise build_internal_http_exception("Reload config", e)


@router.get("/validators")
async def get_validators(api_key: str = Depends(require_admin)):
    """获取配置验证规则"""
    try:
        return config_service.get_validators()
    except Exception as e:
        raise build_internal_http_exception("Get config validators", e)
