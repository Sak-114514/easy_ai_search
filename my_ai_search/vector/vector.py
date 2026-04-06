import os
import time
from pathlib import Path

import chromadb
from chromadb.config import Settings
from chromadb.utils import embedding_functions

from my_ai_search.config import get_config
from my_ai_search.utils.exceptions import VectorException
from my_ai_search.utils.logger import setup_logger

logger = setup_logger("vector")

_client = None
_collection = None
_embedding_function = None

# 已知模型在 HuggingFace 本地缓存中的快照目录名（避免联网）
_HF_SNAPSHOT_IDS = {
    "sentence-transformers/all-MiniLM-L6-v2": "c9745ed1d9f207416be6d2e6f8de32d1f16199bf",
    "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2": "e8f8c211226b894fcb81acc59f3b34ba3efd5f42",
}


def _resolve_model_path(model_name: str) -> str:
    """
    优先使用本地已有的模型文件，避免联网下载。
    查找顺序：
    1. 环境变量 LOCAL_MODEL_PATH 指定的本地路径
    2. 传入值本身就是本地路径
    3. HuggingFace hub 缓存（~/.cache/huggingface/hub）
    4. 魔搭社区缓存（~/.cache/modelscope/hub）
    5. 原始 model_name（允许 sentence-transformers 自行下载）
    """
    from pathlib import Path

    def _set_offline():
        os.environ["TRANSFORMERS_OFFLINE"] = "1"
        os.environ["HF_DATASETS_OFFLINE"] = "1"

    # 1. 用户通过环境变量指定的本地路径
    env_path = os.getenv("CHROMA_EMBEDDING_MODEL_PATH") or os.getenv("LOCAL_MODEL_PATH")
    if env_path and Path(env_path).is_dir():
        _set_offline()
        return env_path

    # 2. 传入值本身就是绝对路径或相对路径
    if Path(model_name).is_dir():
        _set_offline()
        return model_name

    # 3. HuggingFace hub 缓存（自动找 snapshots 目录下任意快照）
    hf_cache = Path.home() / ".cache" / "huggingface" / "hub"
    cache_dir_name = "models--" + model_name.replace("/", "--")
    snapshots_dir = hf_cache / cache_dir_name / "snapshots"
    if snapshots_dir.is_dir():
        # 优先用已知 snapshot ID，否则取最新修改的
        known_id = _HF_SNAPSHOT_IDS.get(model_name)
        if known_id and (snapshots_dir / known_id).is_dir():
            _set_offline()
            return str(snapshots_dir / known_id)
        snapshots = sorted(snapshots_dir.iterdir(), key=lambda p: p.stat().st_mtime, reverse=True)
        if snapshots:
            _set_offline()
            return str(snapshots[0])

    # 4. 魔搭社区缓存（modelscope）
    ms_cache = Path.home() / ".cache" / "modelscope" / "hub"
    ms_path = ms_cache / model_name
    if ms_path.is_dir():
        _set_offline()
        return str(ms_path)

    # 5. fallback：让 sentence-transformers 自行处理（可能联网）
    logger.warning(f"No local model found for '{model_name}', will attempt download.")
    return model_name


def init_vector_db():
    """
    初始化向量数据库

    Returns:
        ChromaDB集合对象

    Raises:
        VectorException: 初始化失败
    """
    global _client, _collection, _embedding_function

    if _collection is not None and _collection_exists(_collection):
        logger.info("Vector DB already initialized")
        return _collection

    try:
        config = get_config()

        logger.info(
            f"Initializing ChromaDB with directory: {config.chroma.persist_dir}"
        )

        persist_dir = Path(config.chroma.persist_dir)
        persist_dir.mkdir(parents=True, exist_ok=True)

        _client = chromadb.PersistentClient(
            path=str(persist_dir),
            settings=Settings(anonymized_telemetry=False, allow_reset=True),
        )

        logger.info(f"Loading embedding model: {config.chroma.embedding_model}")
        model_path = config.chroma.embedding_model_path or _resolve_model_path(
            config.chroma.embedding_model
        )
        logger.info(f"Using model path: {model_path}")
        _embedding_function = embedding_functions.SentenceTransformerEmbeddingFunction(
            model_name=model_path
        )

        try:
            _collection = _client.get_collection(
                name=config.chroma.collection_name,
                embedding_function=_embedding_function,
            )
            logger.info(f"Loaded existing collection: {config.chroma.collection_name}")
        except Exception:
            _collection = _client.create_collection(
                name=config.chroma.collection_name,
                embedding_function=_embedding_function,
                metadata={"description": "AI Search Vector Store"},
            )
            logger.info(f"Created new collection: {config.chroma.collection_name}")

        logger.info("Vector DB initialized successfully")
        return _collection

    except Exception as e:
        logger.error(f"Failed to initialize vector DB: {e}")
        raise VectorException(f"Vector DB initialization failed: {e}") from e


def get_collection():
    """
    获取当前集合对象

    Returns:
        ChromaDB集合对象
    """
    global _collection

    if _collection is None:
        logger.warning("Collection not initialized, initializing...")
        return init_vector_db()
    if not _collection_exists(_collection):
        _collection = None
        return init_vector_db()
    return _collection


def _collection_exists(collection) -> bool:
    """检查当前 collection 句柄是否仍然有效。"""
    try:
        collection.count()
        return True
    except Exception as e:
        logger.warning(f"Collection handle is stale, reinitializing: {e}")
        return False


def store_documents(chunks: list[dict], metadata: dict | None = None) -> list[str]:
    """
    存储文档块到向量数据库

    Args:
        chunks: 文本块列表 [{text, chunk_id, url, metadata}, ...]
        metadata: 额外的全局元数据

    Returns:
        文档ID列表

    Raises:
        VectorException: 存储失败
    """
    if not chunks:
        logger.warning("Empty chunks list, nothing to store")
        return []

    logger.info(f"Storing {len(chunks)} documents to vector DB")

    try:
        collection = get_collection()

        ids = []
        documents = []
        metadatas = []

        for chunk in chunks:
            chunk_id = chunk.get("chunk_id", 0)
            url = chunk.get("url", "unknown")
            doc_id = f"{url}#chunk_{chunk_id}"
            ids.append(doc_id)

            documents.append(chunk.get("text", ""))

            chunk_metadata = {
                "source_url": url,
                "chunk_id": chunk_id,
                "text_length": len(chunk.get("text", "")),
                "snippet": chunk.get("snippet", "")[:200],
            }

            if metadata:
                chunk_metadata.update(metadata)

            if "metadata" in chunk:
                chunk_metadata.update(chunk["metadata"])

            if chunk_metadata.get("search_request_id"):
                ttl_seconds = int(
                    chunk_metadata.get("ttl_seconds") or get_config().search.cache_ttl
                )
                chunk_metadata.setdefault("ephemeral", True)
                chunk_metadata.setdefault("ttl_seconds", ttl_seconds)
                chunk_metadata.setdefault("expires_at", time.time() + ttl_seconds)

            metadatas.append(chunk_metadata)

        logger.debug(f"Prepared {len(ids)} documents for storage")

        try:
            collection.add(ids=ids, documents=documents, metadatas=metadatas)
        except Exception as add_error:
            logger.warning(f"Collection add failed, retrying after reinit: {add_error}")
            global _collection
            _collection = None
            collection = init_vector_db()
            collection.add(ids=ids, documents=documents, metadatas=metadatas)

        logger.info(f"Successfully stored {len(ids)} documents")
        return ids

    except Exception as e:
        logger.error(f"Failed to store documents: {e}")
        raise VectorException(f"Document storage failed: {e}") from e


def cleanup_expired_documents(now: float | None = None) -> list[str]:
    current_time = now if now is not None else time.time()
    try:
        collection = get_collection()
        try:
            payload = collection.get()
        except TypeError:
            payload = collection.get(include=["metadatas"])

        ids = payload.get("ids", [])
        metadatas = payload.get("metadatas", [])
        expired_ids = [
            doc_id
            for doc_id, metadata in zip(ids, metadatas, strict=False)
            if metadata
            and metadata.get("ephemeral")
            and metadata.get("expires_at") is not None
            and float(metadata["expires_at"]) <= current_time
        ]
        if expired_ids:
            collection.delete(ids=expired_ids)
            logger.info("Cleaned up %s expired ephemeral documents", len(expired_ids))
        return expired_ids
    except Exception as e:
        logger.error(f"Failed to clean up expired documents: {e}")
        raise VectorException(f"Expired document cleanup failed: {e}") from e


def upsert_documents(chunks: list[dict], metadata: dict | None = None) -> list[str]:
    """
    覆盖写入文档块到向量数据库。

    Args:
        chunks: 文本块列表 [{text, chunk_id, url, metadata, id?}, ...]
        metadata: 额外的全局元数据

    Returns:
        文档ID列表
    """
    if not chunks:
        logger.warning("Empty chunks list, nothing to upsert")
        return []

    logger.info(f"Upserting {len(chunks)} documents to vector DB")

    try:
        collection = init_vector_db()

        ids = []
        documents = []
        metadatas = []

        for chunk in chunks:
            chunk_id = chunk.get("chunk_id", 0)
            url = chunk.get("url", "unknown")
            doc_id = chunk.get("id") or f"{url}#chunk_{chunk_id}"
            ids.append(doc_id)

            text = chunk.get("text", "")
            documents.append(text)

            chunk_metadata = {
                "source_url": url,
                "chunk_id": chunk_id,
                "text_length": len(text),
                "snippet": chunk.get("snippet", "")[:200],
            }

            if metadata:
                chunk_metadata.update(metadata)

            if "metadata" in chunk:
                chunk_metadata.update(chunk["metadata"])

            metadatas.append(chunk_metadata)

        collection.upsert(ids=ids, documents=documents, metadatas=metadatas)

        logger.info(f"Successfully upserted {len(ids)} documents")
        return ids

    except Exception as e:
        logger.error(f"Failed to upsert documents: {e}")
        raise VectorException(f"Document upsert failed: {e}") from e


def clear_collection():
    """
    清空集合

    Returns:
        None

    Raises:
        VectorException: 清空失败
    """
    try:
        collection = get_collection()

        try:
            count = collection.count()
        except Exception as stale_error:
            logger.warning(f"Collection became stale during clear, reinitializing: {stale_error}")
            global _collection
            _collection = None
            collection = init_vector_db()
            count = collection.count()

        logger.info(f"Clearing collection with {count} documents")

        if count > 0:
            result = collection.get()
            if result and result["ids"]:
                collection.delete(ids=result["ids"])
                logger.info("Collection cleared successfully")

    except Exception as e:
        logger.error(f"Failed to clear collection: {e}")
        raise VectorException(f"Collection clearing failed: {e}") from e


def get_collection_stats() -> dict:
    """
    获取集合统计信息

    Returns:
        统计信息字典：
        {
            'count': int,
            'name': str,
            'metadata': dict
        }
    """
    try:
        collection = get_collection()
        stats = {
            "count": collection.count(),
            "name": collection.name,
            "metadata": collection.metadata,
        }
        return stats

    except Exception as e:
        logger.error(f"Failed to get collection stats: {e}")
        raise VectorException(f"Stats retrieval failed: {e}") from e


def reset_vector_db():
    """
    重置向量数据库（删除并重新创建）

    Returns:
        None

    Raises:
        VectorException: 重置失败
    """
    try:
        global _collection, _client

        logger.warning("Resetting vector DB...")

        config = get_config()

        if _client and _collection:
            _client.delete_collection(config.chroma.collection_name)

        _collection = None
        init_vector_db()

        logger.info("Vector DB reset successfully")

    except Exception as e:
        logger.error(f"Failed to reset vector DB: {e}")
        raise VectorException(f"Vector DB reset failed: {e}") from e
