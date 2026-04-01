"""
配置服务
"""

from typing import Dict
from my_ai_search.config import get_config, reload_config
from my_ai_search.utils.env_store import persist_env_values


class ConfigService:
    """配置服务类"""

    def get_config(self) -> Dict:
        """
        获取系统配置

        Returns:
            配置字典
        """
        config = get_config()
        return {
            "searxng": {
                "api_url": config.searxng.api_url,
                "timeout": config.searxng.timeout,
                "max_results": config.searxng.max_results,
            },
            "lightpanda": {
                "cdp_url": config.lightpanda.cdp_url,
                "timeout": config.lightpanda.timeout,
                "max_concurrent": config.lightpanda.max_concurrent,
                "retry_times": config.lightpanda.retry_times,
            },
            "chroma": {
                "persist_dir": config.chroma.persist_dir,
                "collection_name": config.chroma.collection_name,
                "embedding_model": config.chroma.embedding_model,
                "embedding_model_path": config.chroma.embedding_model_path,
                "top_k": config.chroma.top_k,
            },
            "process": {
                "chunk_size": config.process.chunk_size,
                "overlap": config.process.overlap,
            },
            "deep_process": {
                "summary_length": config.deep_process.summary_length,
                "summary_backend": config.deep_process.summary_backend,
                "summary_api_url": config.deep_process.summary_api_url,
                "summary_model": config.deep_process.summary_model,
                "summary_model_path": config.deep_process.summary_model_path,
                "summary_timeout": config.deep_process.summary_timeout,
                "min_content_length": config.deep_process.min_content_length,
                "max_content_length": config.deep_process.max_content_length,
                "min_quality_score": config.deep_process.min_quality_score,
                "dedup_threshold": config.deep_process.dedup_threshold,
                "enable_summary": config.deep_process.enable_summary,
                "enable_dedup": config.deep_process.enable_dedup,
                "enable_quality_check": config.deep_process.enable_quality_check,
            },
            "cache": {
                "enabled": config.cache.enabled,
                "ttl": config.cache.ttl,
                "persist_dir": config.cache.persist_dir,
            },
        }

    def update_config(self, section: str, data: Dict) -> Dict:
        """
        更新系统配置（通过环境变量）

        注意：配置更新需要重启服务才能生效

        Args:
            section: 配置章节
            data: 配置数据

        Returns:
            更新结果
        """
        try:
            updated = []

            section_config_map = {
                "searxng": "SEARXNG_",
                "lightpanda": "LIGHTPANDA_",
                "chroma": "CHROMA_",
                "process": "TEXT_",
                "deep_process": "DEEP_",
                "cache": "CACHE_",
            }

            prefix = section_config_map.get(section, "")
            if not prefix:
                return {"success": False, "error": f"Unknown section: {section}"}

            field_env_map = {
                "searxng": {
                    "api_url": "API_URL",
                    "timeout": "TIMEOUT",
                    "max_results": "MAX_RESULTS",
                },
                "lightpanda": {
                    "cdp_url": "CDP_URL",
                    "timeout": "TIMEOUT",
                    "max_concurrent": "MAX_CONCURRENT",
                    "retry_times": "RETRY_TIMES",
                },
                "chroma": {
                    "persist_dir": "PERSIST_DIR",
                    "collection_name": "COLLECTION_NAME",
                    "embedding_model": "EMBEDDING_MODEL",
                    "embedding_model_path": "EMBEDDING_MODEL_PATH",
                    "top_k": "TOP_K",
                },
                "process": {
                    "chunk_size": "CHUNK_SIZE",
                    "overlap": "OVERLAP",
                },
                "deep_process": {
                    "summary_length": "SUMMARY_LENGTH",
                    "summary_backend": "SUMMARY_BACKEND",
                    "summary_api_url": "SUMMARY_API_URL",
                    "summary_api_key": "SUMMARY_API_KEY",
                    "summary_model": "SUMMARY_MODEL",
                    "summary_model_path": "SUMMARY_MODEL_PATH",
                    "summary_timeout": "SUMMARY_TIMEOUT",
                    "min_content_length": "MIN_CONTENT_LENGTH",
                    "max_content_length": "MAX_CONTENT_LENGTH",
                    "min_quality_score": "MIN_QUALITY_SCORE",
                    "dedup_threshold": "DEDUP_THRESHOLD",
                    "enable_summary": "ENABLE_SUMMARY",
                    "enable_dedup": "ENABLE_DEDUP",
                    "enable_quality_check": "ENABLE_QUALITY_CHECK",
                },
                "cache": {
                    "enabled": "ENABLED",
                    "ttl": "TTL",
                    "persist_dir": "PERSIST_DIR",
                },
            }

            env_map = field_env_map.get(section, {})

            env_updates = {}
            for key, value in data.items():
                if key in env_map:
                    env_key = prefix + env_map[key]
                    env_updates[env_key] = value
                    updated.append(key)

            if updated:
                persist_env_values(env_updates)
                return {
                    "success": True,
                    "updated": updated,
                    "message": "Configuration updated. Please restart the service to apply changes.",
                }
            else:
                return {
                    "success": False,
                    "error": "No valid configuration fields provided",
                }

        except Exception as e:
            return {"success": False, "error": str(e)}

    def reload_config(self) -> Dict:
        """
        重新加载配置（注意：这只是重新读取配置，不会更新已启动的服务）

        Returns:
            重载结果
        """
        try:
            reload_config()
            return {
                "success": True,
                "message": "Configuration reloaded",
                "config": self.get_config(),
            }
        except Exception as e:
            return {"success": False, "error": str(e)}

    def get_validators(self) -> Dict:
        """
        获取配置验证规则

        Returns:
            验证规则字典
        """
        return {
            "searxng": {
                "api_url": {"type": "string", "pattern": "^https?://"},
                "timeout": {"min": 1.0, "max": 60.0, "type": "float"},
                "max_results": {"min": 1, "max": 20, "type": "int"},
            },
            "lightpanda": {
                "cdp_url": {"type": "string", "pattern": "^ws?://"},
                "timeout": {"min": 1.0, "max": 60.0, "type": "float"},
                "max_concurrent": {"min": 1, "max": 20, "type": "int"},
                "retry_times": {"min": 0, "max": 5, "type": "int"},
            },
            "chroma": {
                "persist_dir": {"type": "string"},
                "collection_name": {"type": "string"},
                "embedding_model": {"type": "string"},
                "embedding_model_path": {"type": "string"},
                "top_k": {"min": 1, "max": 10, "type": "int"},
            },
            "process": {
                "chunk_size": {"min": 128, "max": 2048, "type": "int"},
                "overlap": {"min": 0, "max": 512, "type": "int"},
            },
            "deep_process": {
                "summary_length": {"min": 50, "max": 500, "type": "int"},
                "summary_backend": {"type": "string"},
                "summary_api_url": {"type": "string", "pattern": "^https?://"},
                "summary_api_key": {"type": "string"},
                "summary_model": {"type": "string"},
                "summary_model_path": {"type": "string"},
                "summary_timeout": {"min": 1.0, "max": 120.0, "type": "float"},
                "min_content_length": {"min": 10, "max": 1000, "type": "int"},
                "max_content_length": {"min": 100, "max": 50000, "type": "int"},
                "min_quality_score": {"min": 0.0, "max": 1.0, "type": "float"},
                "dedup_threshold": {"min": 0.0, "max": 1.0, "type": "float"},
                "enable_summary": {"type": "bool"},
                "enable_dedup": {"type": "bool"},
                "enable_quality_check": {"type": "bool"},
            },
            "cache": {
                "enabled": {"type": "bool"},
                "ttl": {"min": 60, "max": 86400, "type": "int"},
                "persist_dir": {"type": "string"},
            },
        }

    def validate_config(self, section: str, data: Dict) -> Dict:
        """
        验证配置数据

        Args:
            section: 配置章节
            data: 配置数据

        Returns:
            验证结果
        """
        validators = self.get_validators()

        if section not in validators:
            return {"valid": False, "error": f"Unknown section: {section}"}

        section_validators = validators[section]
        errors = []

        for key, value in data.items():
            if key not in section_validators:
                errors.append(f"Unknown field: {key}")
                continue

            validator = section_validators[key]
            value_type = validator.get("type")

            if value_type == "int":
                if not isinstance(value, int):
                    errors.append(f"{key} must be an integer")
                    continue
                if "min" in validator and value < validator["min"]:
                    errors.append(f"{key} must be >= {validator['min']}")
                if "max" in validator and value > validator["max"]:
                    errors.append(f"{key} must be <= {validator['max']}")

            elif value_type == "float":
                try:
                    float_value = float(value)
                    if "min" in validator and float_value < validator["min"]:
                        errors.append(f"{key} must be >= {validator['min']}")
                    if "max" in validator and float_value > validator["max"]:
                        errors.append(f"{key} must be <= {validator['max']}")
                except (ValueError, TypeError):
                    errors.append(f"{key} must be a number")

            elif value_type == "bool":
                if not isinstance(value, bool):
                    errors.append(f"{key} must be a boolean")

            elif value_type == "string":
                if not isinstance(value, str):
                    errors.append(f"{key} must be a string")
                if "pattern" in validator:
                    import re

                    if not re.match(validator["pattern"], value):
                        errors.append(f"{key} format is invalid")

        if errors:
            return {"valid": False, "errors": errors}

        return {"valid": True}
