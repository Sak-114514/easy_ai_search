"""
向量库统计适配函数
提供MCP API期望的标准化统计接口
"""


from ..config import get_config
from ..utils.logger import setup_logger
from .vector import _client, get_collection_stats, init_vector_db

logger = setup_logger("vector_db_stats")


def get_vector_db_stats() -> dict:
    """
    获取向量数据库统计信息（MCP API适配格式）

    Returns:
        标准化的统计信息：
        {
            'document_count': int,      # 文档总数
            'collection_count': int,    # 集合数量
            'dimension': int,           # 向量维度
            'model': str                # 使用的嵌入模型
        }
    """
    try:
        # 确保向量库已初始化
        init_vector_db()

        # 获取基础统计
        base_stats = get_collection_stats()

        # 获取集合数量
        collection_count = 1
        if _client is not None:
            try:
                collections = _client.list_collections()
                collection_count = len(collections)
            except Exception as e:
                logger.warning(f"Failed to get collection count: {e}")

        # 获取向量维度
        dimension = 384  # all-MiniLM-L6-v2 的默认维度
        config = get_config()
        model_name = config.chroma.embedding_model

        logger.info(
            f"Vector DB stats: documents={base_stats.get('count', 0)}, "
            f"collections={collection_count}, model={model_name}"
        )

        return {
            "document_count": base_stats.get("count", 0),
            "collection_count": collection_count,
            "dimension": dimension,
            "model": model_name,
        }

    except Exception as e:
        logger.error(f"Failed to get vector DB stats: {e}")
        # 返回默认值，避免API调用失败
        return {
            "document_count": 0,
            "collection_count": 0,
            "dimension": 384,
            "model": "unknown",
        }
