import os
from dataclasses import dataclass
from functools import lru_cache
from typing import Optional
from my_ai_search.utils.paths import (
    ensure_runtime_dirs,
    get_cache_db_dir,
    get_logs_dir,
    get_vector_db_dir,
    resolve_runtime_path,
)


@dataclass
class SearXNGConfig:
    api_url: str = "http://127.0.0.1:8080/search"
    timeout: float = 15.0
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
    persist_dir: str = str(get_vector_db_dir())
    collection_name: str = "ai_search"
    embedding_model: str = "sentence-transformers/all-MiniLM-L6-v2"
    embedding_model_path: str = ""
    top_k: int = 3

    def __post_init__(self):
        if os.getenv("CHROMA_PERSIST_DIR"):
            self.persist_dir = os.getenv("CHROMA_PERSIST_DIR")
        if os.getenv("CHROMA_COLLECTION_NAME"):
            self.collection_name = os.getenv("CHROMA_COLLECTION_NAME")
        if os.getenv("CHROMA_EMBEDDING_MODEL"):
            self.embedding_model = os.getenv("CHROMA_EMBEDDING_MODEL")
        if os.getenv("CHROMA_EMBEDDING_MODEL_PATH"):
            self.embedding_model_path = os.getenv("CHROMA_EMBEDDING_MODEL_PATH")
        if os.getenv("CHROMA_TOP_K"):
            self.top_k = int(os.getenv("CHROMA_TOP_K"))
        self.persist_dir = resolve_runtime_path(self.persist_dir, get_vector_db_dir().parent)
        if self.embedding_model_path:
            self.embedding_model_path = resolve_runtime_path(
                self.embedding_model_path, get_vector_db_dir().parent
            )


@dataclass
class ProcessConfig:
    chunk_size: int = 8000
    overlap: int = 200
    max_chunks_per_page: int = 24
    head_chunks_per_page: int = 8
    tail_chunks_per_page: int = 4

    def __post_init__(self):
        if os.getenv("TEXT_CHUNK_SIZE"):
            self.chunk_size = int(os.getenv("TEXT_CHUNK_SIZE"))
        if os.getenv("TEXT_OVERLAP"):
            self.overlap = int(os.getenv("TEXT_OVERLAP"))
        if os.getenv("TEXT_MAX_CHUNKS_PER_PAGE"):
            self.max_chunks_per_page = int(os.getenv("TEXT_MAX_CHUNKS_PER_PAGE"))
        if os.getenv("TEXT_HEAD_CHUNKS_PER_PAGE"):
            self.head_chunks_per_page = int(os.getenv("TEXT_HEAD_CHUNKS_PER_PAGE"))
        if os.getenv("TEXT_TAIL_CHUNKS_PER_PAGE"):
            self.tail_chunks_per_page = int(os.getenv("TEXT_TAIL_CHUNKS_PER_PAGE"))


@dataclass
class CacheConfig:
    ttl: int = 3600
    enabled: bool = True
    persist_dir: str = str(get_cache_db_dir())

    def __post_init__(self):
        if os.getenv("CACHE_TTL"):
            self.ttl = int(os.getenv("CACHE_TTL"))
        if os.getenv("CACHE_ENABLED"):
            self.enabled = os.getenv("CACHE_ENABLED").lower() in ("true", "1", "yes")
        if os.getenv("CACHE_PERSIST_DIR"):
            self.persist_dir = os.getenv("CACHE_PERSIST_DIR")
        self.persist_dir = resolve_runtime_path(self.persist_dir, get_cache_db_dir().parent)


@dataclass
class DeepProcessConfig:
    summary_length: int = 200
    summary_backend: str = "extractive"  # extractive | lmstudio | openai_compatible | ollama | none
    summary_api_url: str = "http://127.0.0.1:1234/v1/chat/completions"
    summary_api_key: str = ""
    summary_model: str = "qwen2.5-7b-instruct"
    summary_model_path: str = ""
    summary_timeout: float = 15.0
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
        if os.getenv("DEEP_SUMMARY_BACKEND"):
            self.summary_backend = os.getenv("DEEP_SUMMARY_BACKEND")
        if os.getenv("DEEP_SUMMARY_API_URL"):
            self.summary_api_url = os.getenv("DEEP_SUMMARY_API_URL")
        if os.getenv("DEEP_SUMMARY_API_KEY"):
            self.summary_api_key = os.getenv("DEEP_SUMMARY_API_KEY")
        if os.getenv("DEEP_SUMMARY_MODEL"):
            self.summary_model = os.getenv("DEEP_SUMMARY_MODEL")
        if os.getenv("DEEP_SUMMARY_MODEL_PATH"):
            self.summary_model_path = os.getenv("DEEP_SUMMARY_MODEL_PATH")
        if os.getenv("DEEP_SUMMARY_TIMEOUT"):
            self.summary_timeout = float(os.getenv("DEEP_SUMMARY_TIMEOUT"))
        if os.getenv("DEEP_MIN_CONTENT_LENGTH"):
            self.min_content_length = int(os.getenv("DEEP_MIN_CONTENT_LENGTH"))
        if os.getenv("DEEP_MAX_CONTENT_LENGTH"):
            self.max_content_length = int(os.getenv("DEEP_MAX_CONTENT_LENGTH"))
        if os.getenv("DEEP_MIN_QUALITY_SCORE"):
            self.min_quality_score = float(os.getenv("DEEP_MIN_QUALITY_SCORE"))
        if os.getenv("DEEP_DEDUP_THRESHOLD"):
            self.dedup_threshold = float(os.getenv("DEEP_DEDUP_THRESHOLD"))
        env_summary = os.getenv("DEEP_ENABLE_SUMMARY")
        if env_summary is not None:
            self.enable_summary = env_summary.lower() in ("true", "1", "yes")
        env_dedup = os.getenv("DEEP_ENABLE_DEDUP")
        if env_dedup is not None:
            self.enable_dedup = env_dedup.lower() in ("true", "1", "yes")
        env_quality = os.getenv("DEEP_ENABLE_QUALITY_CHECK")
        if env_quality is not None:
            self.enable_quality_check = env_quality.lower() in ("true", "1", "yes")
        if self.summary_model_path:
            self.summary_model_path = resolve_runtime_path(
                self.summary_model_path, get_vector_db_dir().parent
            )


@dataclass
class LogConfig:
    level: str = "INFO"
    format: str = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    file: str = str(get_logs_dir() / "app.log")

    def __post_init__(self):
        if os.getenv("LOG_LEVEL"):
            self.level = os.getenv("LOG_LEVEL")
        if os.getenv("LOG_FORMAT"):
            self.format = os.getenv("LOG_FORMAT")
        if os.getenv("LOG_FILE"):
            self.file = os.getenv("LOG_FILE")
        self.file = resolve_runtime_path(self.file, get_logs_dir())


@dataclass
class AppConfig:
    searxng: SearXNGConfig
    lightpanda: LightPandaConfig
    chroma: ChromaConfig
    process: ProcessConfig
    deep_process: DeepProcessConfig
    cache: CacheConfig
    log: LogConfig


def _config_cache_token() -> tuple[str, ...]:
    prefixes = (
        "SEARXNG_",
        "LIGHTPANDA_",
        "CHROMA_",
        "TEXT_",
        "DEEP_",
        "CACHE_",
        "LOG_",
        "OPENSEARCH_",
    )
    return tuple(
        f"{key}={os.environ.get(key, '')}"
        for key in sorted(os.environ)
        if key.startswith(prefixes)
    )


def _build_config(_: tuple[str, ...]) -> AppConfig:
    """
    获取应用配置
    支持环境变量覆盖
    """
    ensure_runtime_dirs()
    return AppConfig(
        searxng=SearXNGConfig(),
        lightpanda=LightPandaConfig(),
        chroma=ChromaConfig(),
        process=ProcessConfig(),
        deep_process=DeepProcessConfig(),
        cache=CacheConfig(),
        log=LogConfig(),
    )


_build_config = lru_cache(maxsize=4)(_build_config)


def get_config() -> AppConfig:
    return _build_config(_config_cache_token())


def reload_config() -> AppConfig:
    _build_config.cache_clear()
    return get_config()


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

    if config.process.chunk_size < 100 or config.process.chunk_size > 50000:
        errors.append("Text chunk size must be between 100 and 50000")
    if config.process.max_chunks_per_page < 1 or config.process.max_chunks_per_page > 200:
        errors.append("Text max chunks per page must be between 1 and 200")
    if config.process.head_chunks_per_page < 0 or config.process.head_chunks_per_page > 100:
        errors.append("Text head chunks per page must be between 0 and 100")
    if config.process.tail_chunks_per_page < 0 or config.process.tail_chunks_per_page > 100:
        errors.append("Text tail chunks per page must be between 0 and 100")
    if (
        config.process.head_chunks_per_page + config.process.tail_chunks_per_page
        > config.process.max_chunks_per_page
    ):
        errors.append("Text head/tail chunks per page cannot exceed max chunks per page")

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

    valid_summary_backends = [
        "none",
        "extractive",
        "lmstudio",
        "openai_compatible",
        "ollama",
    ]
    if config.deep_process.summary_backend not in valid_summary_backends:
        errors.append(
            f"Deep process summary backend must be one of: {valid_summary_backends}"
        )

    if config.deep_process.summary_timeout <= 0:
        errors.append("Deep process summary timeout must be positive")

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
