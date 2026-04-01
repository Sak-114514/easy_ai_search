import hashlib
import time
from datetime import datetime
from typing import Optional, Dict

import chromadb
from chromadb.utils import embedding_functions

from my_ai_search.config import get_config
from my_ai_search.utils.logger import setup_logger
from my_ai_search.utils.exceptions import CacheException
from my_ai_search.vector.vector import _resolve_model_path

logger = setup_logger("cache")

_cache_hits = 0
_cache_misses = 0
_cache_client = None
_cache_embedding_function = None


def _get_url_hash(url: str) -> str:
    """
    生成URL的MD5哈希作为缓存键

    Args:
        url: 目标URL

    Returns:
        URL的MD5哈希
    """
    return hashlib.md5(url.encode("utf-8")).hexdigest()


def _get_cache_collection():
    """
    获取缓存专用集合

    Returns:
        ChromaDB集合对象或None
    """
    global _cache_client, _cache_embedding_function

    try:
        if _cache_client is None:
            config = get_config()
            _cache_client = chromadb.PersistentClient(path=config.cache.persist_dir)
            _cache_embedding_function = (
                embedding_functions.SentenceTransformerEmbeddingFunction(
                    model_name=config.chroma.embedding_model_path
                    or _resolve_model_path(config.chroma.embedding_model)
                )
            )

        collection_name = "web_cache"

        try:
            collection = _cache_client.get_collection(name=collection_name)
            return collection
        except Exception as e:
            logger.debug(f"Collection does not exist, creating: {e}")
            collection = _cache_client.create_collection(
                name=collection_name,
                embedding_function=_cache_embedding_function,
                metadata={"description": "Web Page Cache"},
            )
            return collection

    except Exception as e:
        logger.error(f"Failed to get cache collection: {e}")
        return None


def is_cached(url: str) -> bool:
    """
    检查URL是否已缓存且未过期

    Args:
        url: 目标URL

    Returns:
        True if cached and not expired
    """
    if not url or not url.strip():
        return False

    try:
        collection = _get_cache_collection()
        if collection is None:
            return False

        cache_key = _get_url_hash(url)

        result = collection.get(ids=[cache_key])

        if not result["ids"]:
            return False

        metadata = result["metadatas"][0] if result["metadatas"] else {}
        cached_time = metadata.get("timestamp", 0)
        ttl = metadata.get("ttl", get_config().cache.ttl)

        current_time = time.time()
        is_expired = (current_time - cached_time) > ttl

        if is_expired:
            logger.debug(f"Cache expired for: {url}")
            collection.delete(ids=[cache_key])
            return False

        logger.debug(f"Cache hit for: {url}")
        return True

    except Exception as e:
        logger.error(f"Failed to check cache: {e}")
        return False


def get_cached(url: str) -> Optional[Dict]:
    """
    获取缓存内容

    Args:
        url: 目标URL

    Returns:
        缓存数据字典：
        {
            'url': str,
            'html': str,
            'title': str,
            'timestamp': float,
            'cached_at': str
        }
        or None if not found or expired
    """
    global _cache_hits, _cache_misses

    if not url or not url.strip():
        _cache_misses += 1
        return None

    try:
        collection = _get_cache_collection()
        if collection is None:
            _cache_misses += 1
            return None

        cache_key = _get_url_hash(url)

        result = collection.get(ids=[cache_key])

        if not result["ids"]:
            logger.debug(f"Cache miss for: {url}")
            _cache_misses += 1
            return None

        metadata = result["metadatas"][0] if result["metadatas"] else {}
        cached_time = metadata.get("timestamp", 0)
        ttl = metadata.get("ttl", get_config().cache.ttl)

        current_time = time.time()
        is_expired = (current_time - cached_time) > ttl

        if is_expired:
            logger.debug(f"Cache expired for: {url}")
            collection.delete(ids=[cache_key])
            _cache_misses += 1
            return None

        document = result["documents"][0] if result["documents"] else ""
        cached_at = metadata.get("cached_at", "")

        logger.info(f"Cache hit for: {url}")
        _cache_hits += 1

        return {
            "url": url,
            "html": document,
            "title": metadata.get("title", ""),
            "timestamp": cached_time,
            "cached_at": cached_at,
        }

    except Exception as e:
        logger.error(f"Failed to get cached: {e}")
        _cache_misses += 1
        return None


def set_cache(url: str, html: str, title: str = "", ttl: Optional[int] = None):
    """
    设置缓存

    Args:
        url: 目标URL
        html: 页面HTML
        title: 页面标题
        ttl: 过期时间（秒），None则使用配置默认值

    Raises:
        CacheException: 缓存失败
    """
    if not url or not url.strip():
        logger.warning("Empty URL, skipping cache")
        return

    if not html or not html.strip():
        logger.warning(f"Empty HTML for {url}, skipping cache")
        return

    try:
        config = get_config()
        if not config.cache.enabled:
            logger.debug("Cache is disabled")
            return

        collection = _get_cache_collection()
        if collection is None:
            logger.warning("Failed to get cache collection")
            return

        cache_key = _get_url_hash(url)

        current_time = time.time()
        actual_ttl = ttl if ttl is not None else config.cache.ttl
        metadata = {
            "url": url,
            "title": title,
            "timestamp": current_time,
            "ttl": actual_ttl,
            "cached_at": datetime.fromtimestamp(current_time).strftime(
                "%Y-%m-%d %H:%M:%S"
            ),
            "is_cache": True,
        }

        try:
            count_before = collection.count()
            collection.update(ids=[cache_key], documents=[html], metadatas=[metadata])
            count_after = collection.count()

            if count_after == count_before:
                logger.debug(f"Update did not add new document, trying add: {url}")
                collection.add(
                    ids=[cache_key],
                    documents=[html],
                    metadatas=[metadata],
                )
                logger.info(
                    f"Added cache for: {url}, count after add: {collection.count()}"
                )
            else:
                logger.info(
                    f"Updated cache for: {url}, count after update: {count_after}"
                )
        except Exception as e:
            logger.info(f"Update failed, trying add: {e}")
            try:
                collection.add(
                    ids=[cache_key],
                    documents=[html],
                    metadatas=[metadata],
                )
                logger.info(
                    f"Added cache for: {url}, count after add: {collection.count()}"
                )
            except Exception as add_error:
                logger.error(f"Failed to add cache: {add_error}")
                raise

    except Exception as e:
        logger.error(f"Failed to set cache: {e}")
        raise CacheException(f"Cache setting failed: {e}")


def get_cache_stats() -> Dict:
    """
    获取缓存统计信息（MCP API适配格式）

    Returns:
        统计信息：
        {
            'total': int,           # 总缓存条目数
            'hits': int,            # 缓存命中次数
            'misses': int,          # 缓存未命中次数
            'hit_rate': float,       # 命中率
            'size_bytes': int,       # 缓存大小（字节）
            'size_mb': float        # 缓存大小（MB）
        }
    """
    global _cache_hits, _cache_misses

    try:
        collection = _get_cache_collection()
        total_entries = collection.count() if collection else 0

        total_requests = _cache_hits + _cache_misses
        hit_rate = _cache_hits / total_requests if total_requests > 0 else 0.0

        # 计算缓存大小（ChromaDB不直接提供，设置为0）
        size_bytes = 0
        size_mb = 0.0

        stats = {
            "total": total_entries,
            "hits": _cache_hits,
            "misses": _cache_misses,
            "hit_rate": hit_rate,
            "size_bytes": size_bytes,
            "size_mb": size_mb,
        }

        logger.info(f"Cache stats: {stats}")
        return stats

    except Exception as e:
        logger.error(f"Failed to get cache stats: {e}")
        return {
            "total": 0,
            "hits": _cache_hits,
            "misses": _cache_misses,
            "hit_rate": 0.0,
            "size_bytes": 0,
            "size_mb": 0.0,
        }


def clear_cache():
    """
    清空所有缓存

    Raises:
        CacheException: 清空失败
    """
    global _cache_hits, _cache_misses

    try:
        collection = _get_cache_collection()
        if collection is None:
            logger.warning("No cache collection to clear")
            return

        collection.delete(where={"is_cache": True})

        _cache_hits = 0
        _cache_misses = 0

        logger.info("Cache cleared successfully")

    except Exception as e:
        logger.error(f"Failed to clear cache: {e}")
        raise CacheException(f"Cache clearing failed: {e}")
