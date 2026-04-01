"""
算法服务
"""

from typing import Dict
from my_ai_search.config import get_config
from my_ai_search.utils.env_store import persist_env_values


class AlgorithmService:
    """算法服务类"""

    def get_params(self) -> Dict:
        """
        获取算法参数

        Returns:
            算法参数字典
        """
        config = get_config()
        return {
            "process": {
                "chunk_size": config.process.chunk_size,
                "overlap": config.process.overlap,
                "max_chunks_per_page": config.process.max_chunks_per_page,
                "head_chunks_per_page": config.process.head_chunks_per_page,
                "tail_chunks_per_page": config.process.tail_chunks_per_page,
            },
            "deep_process": {
                "summary_length": config.deep_process.summary_length,
                "min_quality_score": config.deep_process.min_quality_score,
                "dedup_threshold": config.deep_process.dedup_threshold,
                "min_content_length": config.deep_process.min_content_length,
                "max_content_length": config.deep_process.max_content_length,
                "enable_summary": config.deep_process.enable_summary,
                "enable_dedup": config.deep_process.enable_dedup,
                "enable_quality_check": config.deep_process.enable_quality_check,
            },
            "chroma": {
                "top_k": config.chroma.top_k,
                "embedding_model": config.chroma.embedding_model,
            },
        }

    def get_params_info(self) -> Dict:
        """
        获取算法参数信息（包含说明）

        Returns:
            算法参数信息字典
        """
        return {
            "process": {
                "chunk_size": {
                    "value": 512,
                    "default": 512,
                    "min": 128,
                    "max": 2048,
                    "type": "int",
                    "description": "文本分块大小（字符数）",
                },
                "overlap": {
                    "value": 50,
                    "default": 50,
                    "min": 0,
                    "max": 512,
                    "type": "int",
                    "description": "文本块之间的重叠字符数",
                },
                "max_chunks_per_page": {
                    "value": 24,
                    "default": 24,
                    "min": 1,
                    "max": 200,
                    "type": "int",
                    "description": "单页最多保留的文本块数量",
                },
                "head_chunks_per_page": {
                    "value": 8,
                    "default": 8,
                    "min": 0,
                    "max": 100,
                    "type": "int",
                    "description": "长页面优先保留的前部文本块数量",
                },
                "tail_chunks_per_page": {
                    "value": 4,
                    "default": 4,
                    "min": 0,
                    "max": 100,
                    "type": "int",
                    "description": "长页面优先保留的尾部文本块数量",
                },
            },
            "deep_process": {
                "summary_length": {
                    "value": 200,
                    "default": 200,
                    "min": 50,
                    "max": 500,
                    "type": "int",
                    "description": "摘要生成长度（字符数）",
                },
                "min_quality_score": {
                    "value": 0.5,
                    "default": 0.5,
                    "min": 0.0,
                    "max": 1.0,
                    "type": "float",
                    "description": "最低质量评分阈值",
                },
                "dedup_threshold": {
                    "value": 0.85,
                    "default": 0.85,
                    "min": 0.0,
                    "max": 1.0,
                    "type": "float",
                    "description": "去重相似度阈值",
                },
                "min_content_length": {
                    "value": 50,
                    "default": 50,
                    "min": 10,
                    "max": 1000,
                    "type": "int",
                    "description": "最小内容长度",
                },
                "max_content_length": {
                    "value": 10000,
                    "default": 10000,
                    "min": 100,
                    "max": 50000,
                    "type": "int",
                    "description": "最大内容长度",
                },
                "enable_summary": {
                    "value": True,
                    "default": True,
                    "type": "bool",
                    "description": "是否启用摘要生成",
                },
                "enable_dedup": {
                    "value": True,
                    "default": True,
                    "type": "bool",
                    "description": "是否启用去重",
                },
                "enable_quality_check": {
                    "value": True,
                    "default": True,
                    "type": "bool",
                    "description": "是否启用质量检查",
                },
            },
            "chroma": {
                "top_k": {
                    "value": 3,
                    "default": 3,
                    "min": 1,
                    "max": 10,
                    "type": "int",
                    "description": "向量检索返回的相似结果数量",
                },
                "embedding_model": {
                    "value": "sentence-transformers/all-MiniLM-L6-v2",
                    "default": "sentence-transformers/all-MiniLM-L6-v2",
                    "type": "string",
                    "description": "嵌入模型名称",
                },
            },
        }

    def update_params(self, data: Dict) -> Dict:
        """
        更新算法参数

        Args:
            data: 算法参数字典

        Returns:
            更新结果
        """
        try:
            updated = []

            field_env_map = {
                "chunk_size": "TEXT_CHUNK_SIZE",
                "overlap": "TEXT_OVERLAP",
                "max_chunks_per_page": "TEXT_MAX_CHUNKS_PER_PAGE",
                "head_chunks_per_page": "TEXT_HEAD_CHUNKS_PER_PAGE",
                "tail_chunks_per_page": "TEXT_TAIL_CHUNKS_PER_PAGE",
                "summary_length": "DEEP_SUMMARY_LENGTH",
                "min_quality_score": "DEEP_MIN_QUALITY_SCORE",
                "dedup_threshold": "DEEP_DEDUP_THRESHOLD",
                "min_content_length": "DEEP_MIN_CONTENT_LENGTH",
                "max_content_length": "DEEP_MAX_CONTENT_LENGTH",
                "enable_summary": "DEEP_ENABLE_SUMMARY",
                "enable_dedup": "DEEP_ENABLE_DEDUP",
                "enable_quality_check": "DEEP_ENABLE_QUALITY_CHECK",
                "top_k": "CHROMA_TOP_K",
                "embedding_model": "CHROMA_EMBEDDING_MODEL",
            }

            env_updates = {}
            for key, value in data.items():
                if key in field_env_map:
                    env_key = field_env_map[key]
                    env_updates[env_key] = value
                    updated.append(key)

            if updated:
                persist_env_values(env_updates)
                return {
                    "success": True,
                    "updated": updated,
                    "message": "Algorithm parameters updated. Please restart the service to apply changes.",
                }
            else:
                return {
                    "success": False,
                    "error": "No valid algorithm parameters provided",
                }

        except Exception as e:
            return {"success": False, "error": str(e)}

    def reset_params(self) -> Dict:
        """
        重置算法参数为默认值

        Returns:
            重置结果
        """
        try:
            default_params = {
                "chunk_size": 512,
                "overlap": 50,
                "max_chunks_per_page": 24,
                "head_chunks_per_page": 8,
                "tail_chunks_per_page": 4,
                "summary_length": 200,
                "min_quality_score": 0.5,
                "dedup_threshold": 0.85,
                "min_content_length": 50,
                "max_content_length": 10000,
                "enable_summary": True,
                "enable_dedup": True,
                "enable_quality_check": True,
                "top_k": 3,
                "embedding_model": "sentence-transformers/all-MiniLM-L6-v2",
            }

            result = self.update_params(default_params)

            if result["success"]:
                result["message"] = (
                    "Algorithm parameters reset to defaults. Please restart the service to apply changes."
                )

            return result
        except Exception as e:
            return {"success": False, "error": str(e)}
