"""
MCP (Model Context Protocol) 数据模型
"""

from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


class MCPTool(BaseModel):
    """MCP工具定义"""

    name: str = Field(..., description="工具名称")
    description: str = Field(..., description="工具描述")
    input_schema: Dict[str, Any] = Field(..., description="输入模式(JSON Schema)")


class MCPResource(BaseModel):
    """MCP资源定义"""

    uri: str = Field(..., description="资源唯一标识符")
    name: str = Field(..., description="资源名称")
    description: str = Field(..., description="资源描述")
    mime_type: Optional[str] = Field(None, alias="mimeType", description="资源MIME类型")


class MCPPrompt(BaseModel):
    """MCP提示词定义"""

    name: str = Field(..., description="提示词名称")
    description: str = Field(..., description="提示词描述")
    arguments: Optional[List[Dict[str, Any]]] = Field(None, description="提示词参数")


class MCPMessage(BaseModel):
    """MCP消息"""

    type: str = Field(..., description="消息类型: text, image, resource")
    text: Optional[str] = Field(None, description="文本内容")
    data: Optional[str] = Field(None, description="二进制数据(base64)")
    uri: Optional[str] = Field(None, description="资源URI")
    mime_type: Optional[str] = Field(None, alias="mimeType", description="MIME类型")


class MCPContent(BaseModel):
    """MCP内容"""

    type: str = Field(..., description="内容类型")
    text: Optional[str] = Field(None, description="文本内容")


class MCPCapabilities(BaseModel):
    """MCP服务器能力声明"""

    tools: Dict[str, Any] = Field(default_factory=lambda: {"listChanged": True})
    resources: Dict[str, Any] = Field(
        default_factory=lambda: {"subscribe": True, "listChanged": True}
    )
    prompts: Dict[str, Any] = Field(default_factory=lambda: {"listChanged": True})


class MCPServerInfo(BaseModel):
    """MCP服务器信息"""

    name: str = Field(..., description="服务器名称")
    version: str = Field(..., description="服务器版本")


class MCPInitializeParams(BaseModel):
    """MCP初始化参数"""

    protocol_version: str = Field(..., alias="protocolVersion")
    capabilities: Dict[str, Any] = Field(default_factory=dict)
    client_info: Dict[str, str] = Field(default_factory=dict, alias="clientInfo")
