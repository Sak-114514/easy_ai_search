from dataclasses import dataclass
from typing import Optional
import os


@dataclass
class SearXNGConfig:
    api_url: str = "http://127.0.0.1:8080/search"
    timeout: float = 10.0
    max_results: int = 5

    def __post_init__(self):
        if os.getenv("SEARXNG_API_URL"):
            self.api_url = os.getenv("SEARXNG_API_URL")
        if os.getenv("SEARXNG_TIMEOUT"):
            self.timeout = float(os.getenv("SEARXNG_TIMEOUT"))
        if os.getenv("SEARXNG_MAX_RESULTS"):
            self.max_results = int(os.getenv("SEARXNG_MAX_RESULTS"))


@dataclass
class LightPandaConfig:
    cdp_url: str = "ws://127.0.0.1:9222"
    timeout: float = 10.0
    max_concurrent: int = 5
    retry_times: int = 2

    def __post_init__(self):
        if os.getenv("LIGHTPANDA_CDP_URL"):
            self.cdp_url = os.getenv("LIGHTPANDA_CDP_URL")
        if os.getenv("LIGHTPANDA_TIMEOUT"):
            self.timeout = float(os.getenv("LIGHTPANDA_TIMEOUT"))
        if os.getenv("LIGHTPANDA_MAX_CONCURRENT"):
            self.max_concurrent = int(os.getenv("LIGHTPANDA_MAX_CONCURRENT"))
        if os.getenv("LIGHTPANDA_RETRY_TIMES"):
            self.retry_times = int(os.getenv("LIGHTPANDA_RETRY_TIMES"))


@dataclass
class ChromaConfig:
    persist_dir: str = "./chroma_db"
    collection_name: str = "ai_search"
    embedding_model: str = "sentence-transformers/all-MiniLM-L6-v2"
    top_k: int = 3

    def __post_init__(self):
        if os.getenv("CHROMA_PERSIST_DIR"):
            self.persist_dir = os.getenv("CHROMA_PERSIST_DIR")
        if os.getenv("CHROMA_COLLECTION_NAME"):
            self.collection_name = os.getenv("CHROMA_COLLECTION_NAME")
        if os.getenv("CHROMA_EMBEDDING_MODEL"):
            self.embedding_model = os.getenv("CHROMA_EMBEDDING_MODEL")
        if os.getenv("CHROMA_TOP_K"):
            self.top_k = int(os.getenv("CHROMA_TOP_K"))


@dataclass
class ProcessConfig:
    chunk_size: int = 512
    overlap: int = 50

    def __post_init__(self):
        if os.getenv("TEXT_CHUNK_SIZE"):
            self.chunk_size = int(os.getenv("TEXT_CHUNK_SIZE"))
        if os.getenv("TEXT_OVERLAP"):
            self.overlap = int(os.getenv("TEXT_OVERLAP"))


@dataclass
class CacheConfig:
    ttl: int = 3600
    enabled: bool = True

    def __post_init__(self):
        if os.getenv("CACHE_TTL"):
            self.ttl = int(os.getenv("CACHE_TTL"))
        if os.getenv("CACHE_ENABLED"):
            self.enabled = os.getenv("CACHE_ENABLED").lower() in ("true", "1", "yes")


@dataclass
class DeepProcessConfig:
    summary_length: int = 200
    min_content_length: int = 50
    max_content_length: int = 10000
    min_quality_score: float = 0.5
    dedup_threshold: float = 0.85
    enable_summary: bool = True
    enable_dedup: bool = True
    enable_quality_check: bool = True

    def __post_init__(self):
        if os.getenv("DEEP_SUMMARY_LENGTH"):
            self.summary_length = int(os.getenv("DEEP_SUMMARY_LENGTH"))
        if os.getenv("DEEP_MIN_CONTENT_LENGTH"):
            self.min_content_length = int(os.getenv("DEEP_MIN_CONTENT_LENGTH"))
        if os.getenv("DEEP_MAX_CONTENT_LENGTH"):
            self.max_content_length = int(os.getenv("DEEP_MAX_CONTENT_LENGTH"))
        if os.getenv("DEEP_MIN_QUALITY_SCORE"):
            self.min_quality_score = float(os.getenv("DEEP_MIN_QUALITY_SCORE"))
        if os.getenv("DEEP_DEDUP_THRESHOLD"):
            self.dedup_threshold = float(os.getenv("DEEP_DEDUP_THRESHOLD"))
        if os.getenv("DEEP_ENABLE_SUMMARY"):
            self.enable_summary = os.getenv("DEEP_ENABLE_SUMMARY").lower() in (
                "true",
                "1",
                "yes",
            )
        if os.getenv("DEEP_ENABLE_DEDUP"):
            self.enable_dedup = os.getenv("DEEP_ENABLE_DEDUP").lower() in (
                "true",
                "1",
                "yes",
            )
        if os.getenv("DEEP_ENABLE_QUALITY_CHECK"):
            self.enable_quality_check = os.getenv(
                "DEEP_ENABLE_QUALITY_CHECK"
            ).lower() in ("true", "1", "yes")


@dataclass
class LogConfig:
    level: str = "INFO"
    format: str = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    file: str = "./logs/app.log"

    def __post_init__(self):
        if os.getenv("LOG_LEVEL"):
            self.level = os.getenv("LOG_LEVEL")
        if os.getenv("LOG_FORMAT"):
            self.format = os.getenv("LOG_FORMAT")
        if os.getenv("LOG_FILE"):
            self.file = os.getenv("LOG_FILE")


@dataclass
class AppConfig:
    searxng: SearXNGConfig
    lightpanda: LightPandaConfig
    chroma: ChromaConfig
    process: ProcessConfig
    deep_process: DeepProcessConfig
    cache: CacheConfig
    log: LogConfig


def get_config() -> AppConfig:
    """
    获取应用配置
    支持环境变量覆盖
    """
    return AppConfig(
        searxng=SearXNGConfig(),
        lightpanda=LightPandaConfig(),
        chroma=ChromaConfig(),
        process=ProcessConfig(),
        deep_process=DeepProcessConfig(),
        cache=CacheConfig(),
        log=LogConfig(),
    )


def validate_config(config: AppConfig) -> bool:
    """
    验证配置有效性

    Returns:
        True if config is valid
    """
    errors = []

    # 验证端口和URL
    if not config.searxng.api_url.startswith("http"):
        errors.append("SearXNG API URL must start with http:// or https://")

    if not config.lightpanda.cdp_url.startswith(
        "ws://"
    ) and not config.lightpanda.cdp_url.startswith("wss://"):
        errors.append("LightPanda CDP URL must start with ws:// or wss://")

    # 验证数值范围
    if config.searxng.timeout <= 0:
        errors.append("SearXNG timeout must be positive")

    if config.lightpanda.timeout <= 0:
        errors.append("LightPanda timeout must be positive")

    if config.lightpanda.max_concurrent < 1 or config.lightpanda.max_concurrent > 20:
        errors.append("LightPanda max_concurrent must be between 1 and 20")

    if config.process.chunk_size < 100 or config.process.chunk_size > 2048:
        errors.append("Text chunk size must be between 100 and 2048")

    if (
        config.deep_process.min_content_length < 10
        or config.deep_process.min_content_length > 500
    ):
        errors.append("Deep process min content length must be between 10 and 500")

    if (
        config.deep_process.max_content_length < 500
        or config.deep_process.max_content_length > 50000
    ):
        errors.append("Deep process max content length must be between 500 and 50000")

    if (
        config.deep_process.min_quality_score < 0
        or config.deep_process.min_quality_score > 1
    ):
        errors.append("Deep process min quality score must be between 0 and 1")

    if (
        config.deep_process.dedup_threshold < 0
        or config.deep_process.dedup_threshold > 1
    ):
        errors.append("Deep process dedup threshold must be between 0 and 1")

    if config.chroma.top_k < 1 or config.chroma.top_k > 10:
        errors.append("Chroma top_k must be between 1 and 10")

    # 验证日志级别
    valid_levels = ["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]
    if config.log.level.upper() not in valid_levels:
        errors.append(f"Log level must be one of: {valid_levels}")

    if errors:
        for error in errors:
            print(f"Config validation error: {error}")
        return False

    return True
