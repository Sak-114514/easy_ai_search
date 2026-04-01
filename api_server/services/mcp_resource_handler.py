"""
MCP资源处理器

实现MCP协议的资源管理和读取
"""

import json
import logging
from typing import Any, Dict, List

from ..models.mcp import MCPResource
from .log_service import LogService
from .config_service import ConfigService
from .vector_service import VectorService
from .cache_service import CacheService

logger = logging.getLogger(__name__)


class MCPResourceHandler:
    """MCP资源处理器"""

    def __init__(self):
        """初始化处理器"""
        self.log_service = LogService()
        self.config_service = ConfigService()
        self.vector_service = VectorService()
        self.cache_service = CacheService()

        self._init_resources()

    def _init_resources(self):
        """初始化资源定义"""
        self.resources = {
            "logs://latest": MCPResource(
                uri="logs://latest",
                name="最新日志",
                description="系统最新的日志记录",
                mime_type="text/plain",
            ),
            "config://current": MCPResource(
                uri="config://current",
                name="当前配置",
                description="系统当前的配置信息",
                mime_type="application/json",
            ),
            "vector://db": MCPResource(
                uri="vector://db",
                name="向量库",
                description="向量库的统计信息和元数据",
                mime_type="application/json",
            ),
            "cache://stats": MCPResource(
                uri="cache://stats",
                name="缓存统计",
                description="URL缓存的统计信息",
                mime_type="application/json",
            ),
        }

    async def list_resources(self) -> List[Dict[str, Any]]:
        """
        列出所有可用资源

        Returns:
            资源列表
        """
        resources = [
            {
                "uri": resource.uri,
                "name": resource.name,
                "description": resource.description,
                "mimeType": resource.mime_type,
            }
            for resource in self.resources.values()
        ]
        logger.info(f"列出资源: {len(resources)}个")
        return resources

    async def read_resource(self, uri: str) -> Dict[str, Any]:
        """
        读取资源内容

        Args:
            uri: 资源URI

        Returns:
            资源内容

        Raises:
            ValueError: 资源不存在
        """
        logger.info(f"读取资源: {uri}")

        if uri == "logs://latest":
            return await self._read_logs()
        elif uri == "config://current":
            return await self._read_config()
        elif uri == "vector://db":
            return await self._read_vector_db()
        elif uri == "cache://stats":
            return await self._read_cache_stats()
        else:
            raise ValueError(f"未知资源: {uri}")

    async def _read_logs(self) -> Dict[str, Any]:
        """读取最新日志"""
        try:
            log_page = self.log_service.list_search_logs(page=1, size=10)
            logs = log_page.get("logs", [])

            content = "\n".join(
                f"[{log['timestamp']}] {log['query']} - {log['source']} - {log['results_count']} results"
                for log in logs
            )

            return {
                "contents": [
                    {"uri": "logs://latest", "mimeType": "text/plain", "text": content}
                ]
            }
        except Exception as e:
            logger.error(f"读取日志失败: {str(e)}")
            return {
                "contents": [
                    {
                        "uri": "logs://latest",
                        "mimeType": "text/plain",
                        "text": f"读取日志失败: {str(e)}",
                    }
                ]
            }

    async def _read_config(self) -> Dict[str, Any]:
        """读取当前配置"""
        try:
            config = self.config_service.get_config()

            content = json.dumps(config, indent=2, ensure_ascii=False)

            return {
                "contents": [
                    {
                        "uri": "config://current",
                        "mimeType": "application/json",
                        "text": content,
                    }
                ]
            }
        except Exception as e:
            logger.error(f"读取配置失败: {str(e)}")
            return {
                "contents": [
                    {
                        "uri": "config://current",
                        "mimeType": "application/json",
                        "text": f"读取配置失败: {str(e)}",
                    }
                ]
            }

    async def _read_vector_db(self) -> Dict[str, Any]:
        """读取向量库信息"""
        try:
            stats = self.vector_service.get_stats()

            content = json.dumps(stats, indent=2, ensure_ascii=False)

            return {
                "contents": [
                    {
                        "uri": "vector://db",
                        "mimeType": "application/json",
                        "text": content,
                    }
                ]
            }
        except Exception as e:
            logger.error(f"读取向量库信息失败: {str(e)}")
            return {
                "contents": [
                    {
                        "uri": "vector://db",
                        "mimeType": "application/json",
                        "text": f"读取向量库信息失败: {str(e)}",
                    }
                ]
            }

    async def _read_cache_stats(self) -> Dict[str, Any]:
        """读取缓存统计"""
        try:
            stats = self.cache_service.get_stats()

            content = json.dumps(stats, indent=2, ensure_ascii=False)

            return {
                "contents": [
                    {
                        "uri": "cache://stats",
                        "mimeType": "application/json",
                        "text": content,
                    }
                ]
            }
        except Exception as e:
            logger.error(f"读取缓存统计失败: {str(e)}")
            return {
                "contents": [
                    {
                        "uri": "cache://stats",
                        "mimeType": "application/json",
                        "text": f"读取缓存统计失败: {str(e)}",
                    }
                ]
            }
