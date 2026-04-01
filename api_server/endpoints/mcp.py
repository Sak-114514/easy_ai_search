"""
MCP (Model Context Protocol) 端点

提供 MCP 协议支持，用于 LLM 集成
"""

import json
import logging
from fastapi import APIRouter, Request, Query, Depends
from fastapi.responses import StreamingResponse, JSONResponse
from typing import Dict, Any

from ..services.mcp_service import MCPService
from ..utils.mcp import JSONRPCHandler
from ..middleware.auth import get_api_key

logger = logging.getLogger(__name__)

router = APIRouter()
mcp_service = MCPService()
jsonrpc_handler = JSONRPCHandler()


def register_jsonrpc_handlers():
    """注册JSON-RPC处理器"""

    async def handle_tools_list(method: str, params: Dict) -> Dict[str, Any]:
        """处理tools/list方法"""
        tools = await mcp_service.list_tools()
        return {"tools": tools}

    async def handle_tools_call(method: str, params: Dict) -> Dict[str, Any]:
        """处理tools/call方法"""
        name = params.get("name")
        arguments = params.get("arguments", {})
        result = await mcp_service.call_tool(name, arguments)
        return {"content": result}

    async def handle_resources_list(method: str, params: Dict) -> Dict[str, Any]:
        """处理resources/list方法"""
        resources = await mcp_service.list_resources()
        return {"resources": resources}

    async def handle_resources_read(method: str, params: Dict) -> Dict[str, Any]:
        """处理resources/read方法"""
        uri = params.get("uri")
        result = await mcp_service.read_resource(uri)
        return result

    async def handle_prompts_list(method: str, params: Dict) -> Dict[str, Any]:
        """处理prompts/list方法"""
        prompts = await mcp_service.list_prompts()
        return {"prompts": prompts}

    async def handle_prompts_get(method: str, params: Dict) -> Dict[str, Any]:
        """处理prompts/get方法"""
        name = params.get("name")
        arguments = params.get("arguments", {})
        result = await mcp_service.get_prompt(name, arguments)
        return {"description": result}

    async def handle_initialize(method: str, params: Dict) -> Dict[str, Any]:
        """处理initialize方法"""
        return mcp_service.get_capabilities()

    jsonrpc_handler.register_method("tools/list", handle_tools_list)
    jsonrpc_handler.register_method("tools/call", handle_tools_call)
    jsonrpc_handler.register_method("resources/list", handle_resources_list)
    jsonrpc_handler.register_method("resources/read", handle_resources_read)
    jsonrpc_handler.register_method("prompts/list", handle_prompts_list)
    jsonrpc_handler.register_method("prompts/get", handle_prompts_get)
    jsonrpc_handler.register_method("initialize", handle_initialize)


register_jsonrpc_handlers()


@router.get("/capabilities")
async def mcp_capabilities(api_key: str = Depends(get_api_key)):
    """MCP 能力声明端点"""
    return mcp_service.get_capabilities()


@router.post("/sse")
async def mcp_sse(request: Request, api_key: str = Depends(get_api_key)):
    """MCP Server-Sent Events 端点"""
    body = await request.json()
    query = body.get("query", "")

    return StreamingResponse(
        mcp_service.handle_sse(query),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


@router.post("/jsonrpc")
async def handle_jsonrpc(request: Request, api_key: str = Depends(get_api_key)):
    """
    JSON-RPC 2.0 端点

    支持MCP协议的JSON-RPC格式
    """
    try:
        request_data = await request.body()
        response = await jsonrpc_handler.handle_request(request_data.decode("utf-8"))
        return JSONResponse(content=response.to_dict())
    except Exception as e:
        logger.error(f"JSON-RPC请求处理失败: {str(e)}")
        return JSONResponse(
            status_code=500,
            content={
                "jsonrpc": "2.0",
                "id": None,
                "error": {"code": -32603, "message": "Internal error"},
            },
        )


@router.get("/tools")
async def list_tools(api_key: str = Depends(get_api_key)):
    """列出所有 MCP 工具"""
    return {"tools": await mcp_service.list_tools()}


@router.post("/tools/call")
async def call_tool(request: Request, api_key: str = Depends(get_api_key)):
    """调用 MCP 工具"""
    body = await request.json()
    name = body.get("name")
    arguments = body.get("arguments", {})

    result = await mcp_service.call_tool(name, arguments)
    return {"content": result}


@router.get("/resources")
async def list_resources(api_key: str = Depends(get_api_key)):
    """列出所有 MCP 资源"""
    return {"resources": await mcp_service.list_resources()}


@router.post("/resources/read")
async def read_resource(request: Request, api_key: str = Depends(get_api_key)):
    """读取 MCP 资源"""
    body = await request.json()
    uri = body.get("uri")

    result = await mcp_service.read_resource(uri)
    return result


@router.get("/prompts")
async def list_prompts(api_key: str = Depends(get_api_key)):
    """列出所有 MCP 提示词"""
    return {"prompts": await mcp_service.list_prompts()}


@router.post("/prompts/get")
async def get_prompt(request: Request, api_key: str = Depends(get_api_key)):
    """获取 MCP 提示词"""
    body = await request.json()
    name = body.get("name")
    arguments = body.get("arguments", {})

    result = await mcp_service.get_prompt(name, arguments)
    return {"description": result}
