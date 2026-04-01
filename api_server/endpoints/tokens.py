"""
Token 管理端点
"""

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from ..dependencies import get_token_service
from ..middleware.auth import require_admin
from ..middleware.errors import build_internal_http_exception
from ..services.token_service import TokenService

router = APIRouter()


class TokenCreateRequest(BaseModel):
    name: str = Field(..., min_length=2, max_length=64)
    role: str = Field("default", pattern="^(default|admin)$")
    notes: str = Field("", max_length=500)


@router.get("")
async def list_tokens(
    api_key: str = Depends(require_admin),
    token_service: TokenService = Depends(get_token_service),
):
    return {"tokens": token_service.list_tokens()}


@router.post("")
async def create_token(
    payload: TokenCreateRequest,
    api_key: str = Depends(require_admin),
    token_service: TokenService = Depends(get_token_service),
):
    try:
        return token_service.create_token(payload.name, payload.role, payload.notes)
    except Exception as e:
        if "UNIQUE constraint failed" in str(e):
            raise HTTPException(status_code=400, detail="Token name already exists")
        raise build_internal_http_exception("Create token", e)


@router.post("/{token_id}/revoke")
async def revoke_token(
    token_id: int,
    api_key: str = Depends(require_admin),
    token_service: TokenService = Depends(get_token_service),
):
    result = token_service.revoke_token(token_id)
    if not result.get("success"):
        raise HTTPException(status_code=404, detail=result.get("error", "Token not found"))
    return result


@router.get("/{token_id}/usage")
async def get_token_usage(
    token_id: int,
    api_key: str = Depends(require_admin),
    token_service: TokenService = Depends(get_token_service),
):
    result = token_service.get_token_usage(token_id)
    if not result.get("success"):
        raise HTTPException(status_code=404, detail=result.get("error", "Token not found"))
    return result
