"""
API Server 配置管理

支持环境变量和配置文件
"""

import json
import os
import threading
import warnings
from dataclasses import dataclass
from typing import Dict, List
from my_ai_search.utils.paths import get_logs_db_path, get_logs_dir


@dataclass
class APIConfig:
    """API 服务配置"""

    host: str = "0.0.0.0"
    port: int = 8000
    debug: bool = False

    api_keys: Dict[str, str] = None
    jwt_secret: str = ""
    jwt_expire_hours: int = 24

    rate_limit_enabled: bool = True
    rate_limit_requests: int = 60
    rate_limit_window: int = 60

    log_level: str = "INFO"
    log_dir: str = str(get_logs_dir())

    database_url: str = f"sqlite:///{get_logs_db_path()}"

    cors_origins: List[str] = None

    def __post_init__(self):
        api_keys_env = os.getenv("API_KEYS_JSON")
        if api_keys_env:
            try:
                self.api_keys = json.loads(api_keys_env.strip().strip("'\""))
            except json.JSONDecodeError:
                raise RuntimeError("API_KEYS_JSON is not valid JSON")
        elif not self.api_keys:
            warnings.warn(
                "API_KEYS_JSON not set; generating a random admin key. "
                "Set API_KEYS_JSON for production use.",
                RuntimeWarning,
                stacklevel=2,
            )
            import secrets

            random_key = secrets.token_urlsafe(32)
            self.api_keys = {"admin": random_key}
            print(f"[WARN] Generated random admin API key: {random_key}")

        jwt_env = os.getenv("JWT_SECRET")
        if jwt_env:
            self.jwt_secret = jwt_env
        elif not self.jwt_secret:
            import secrets

            self.jwt_secret = secrets.token_urlsafe(32)
            warnings.warn(
                "JWT_SECRET not set; a random secret was generated. "
                "Set JWT_SECRET for production use.",
                RuntimeWarning,
                stacklevel=2,
            )

        cors_env = os.getenv("CORS_ORIGINS")
        if cors_env:
            self.cors_origins = [
                origin.strip() for origin in cors_env.split(",") if origin.strip()
            ]
        elif not self.cors_origins:
            self.cors_origins = ["http://localhost:8000", "http://127.0.0.1:8000"]

        if "*" in self.cors_origins and len(self.cors_origins) > 1:
            warnings.warn(
                "CORS_ORIGINS contains '*' together with explicit origins; "
                "credentials will be disabled for safety.",
                RuntimeWarning,
                stacklevel=2,
            )

        # 环境变量覆盖
        self.host = os.getenv("API_HOST", self.host)
        self.port = int(os.getenv("API_PORT", self.port))
        self.debug = os.getenv("API_DEBUG", str(self.debug)).lower() == "true"

        self.log_level = os.getenv("LOG_LEVEL", self.log_level)
        self.log_dir = os.getenv("LOG_DIR", self.log_dir)

        self.database_url = os.getenv("DATABASE_URL", self.database_url)
        if self.database_url.startswith("sqlite:///"):
            db_path = self.database_url.replace("sqlite:///", "", 1)
            self.database_url = (
                f"sqlite:///{os.path.abspath(os.path.expanduser(db_path))}"
            )
        self.log_dir = os.path.abspath(os.path.expanduser(self.log_dir))

        self.rate_limit_enabled = (
            os.getenv("RATE_LIMIT_ENABLED", str(self.rate_limit_enabled)).lower()
            == "true"
        )
        self.rate_limit_requests = int(
            os.getenv("RATE_LIMIT_REQUESTS", self.rate_limit_requests)
        )
        self.rate_limit_window = int(
            os.getenv("RATE_LIMIT_WINDOW", self.rate_limit_window)
        )


# 全局配置实例
_config = None
_config_lock = threading.Lock()


def get_api_config() -> APIConfig:
    """获取 API 配置实例"""
    global _config
    if _config is None:
        with _config_lock:
            if _config is None:
                _config = APIConfig()
    return _config


def reload_config():
    """重新加载配置"""
    global _config
    with _config_lock:
        _config = APIConfig()
    return _config
