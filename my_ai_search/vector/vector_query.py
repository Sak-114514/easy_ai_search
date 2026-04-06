
from my_ai_search.config import get_config
from my_ai_search.utils.exceptions import VectorException
from my_ai_search.utils.logger import setup_logger

from .vector import get_collection

logger = setup_logger("vector_query")


def search(
    query: str, top_k: int | None = None, filter_metadata: dict | None = None
) -> list[dict]:
    """
    纯向量语义检索

    Args:
        query: 查询文本
        top_k: 返回结果数，None则使用配置默认值
        filter_metadata: 元数据过滤条件

    Returns:
        检索结果列表：
        [
            {
                'id': str,             # 文档ID
                'text': str,           # 文本内容
                'metadata': dict,      # 元数据
                'similarity': float,   # 相似度分数（0-1）
                'distance': float       # 距离（越小越相似）
            },
            ...
        ]
    """
    if not query or not query.strip():
        logger.warning("Empty query")
        return []

    config = get_config()
    actual_top_k = top_k or config.chroma.top_k

    logger.info(f"Semantic search: query='{query}', top_k={actual_top_k}")

    try:
        collection = get_collection()

        query_params = {"query_texts": [query], "n_results": actual_top_k}

        if filter_metadata:
            query_params["where"] = filter_metadata

        results = collection.query(**query_params)

        logger.debug(f"Raw results: {len(results.get('ids', [[]])[0])} documents")

        parsed_results = _parse_search_results(results)

        logger.info(f"Semantic search returned {len(parsed_results)} results")
        return parsed_results

    except Exception as e:
        logger.error(f"Semantic search failed: {e}")
        raise VectorException(f"Semantic search failed: {e}") from e


def hybrid_search(
    query: str,
    top_k: int | None = None,
    filter_metadata: dict | None = None,
    alpha: float = 0.7,
) -> list[dict]:
    """
    混合检索（向量+关键词）

    Args:
        query: 查询文本
        top_k: 返回结果数
        filter_metadata: 元数据过滤条件
        alpha: 向量权重（0-1），关键词权重为1-alpha

    Returns:
        检索结果列表（包含混合分数）
    """
    if not query or not query.strip():
        logger.warning("Empty query")
        return []

    config = get_config()
    actual_top_k = top_k or config.chroma.top_k

    logger.info(f"Hybrid search: query='{query}', top_k={actual_top_k}, alpha={alpha}")

    try:
        vector_results = search(
            query, top_k=actual_top_k * 2, filter_metadata=filter_metadata
        )

        candidate_ids = [r["id"] for r in vector_results]

        keyword_results = _keyword_search(
            query,
            top_k=actual_top_k * 2,
            filter_metadata=filter_metadata,
            candidate_ids=candidate_ids,
        )

        merged_results = _merge_and_rank(vector_results, keyword_results, alpha)

        final_results = merged_results[:actual_top_k]

        logger.info(f"Hybrid search returned {len(final_results)} results")
        return final_results

    except Exception as e:
        logger.error(f"Hybrid search failed: {e}")
        raise VectorException(f"Hybrid search failed: {e}") from e


def _parse_search_results(results: dict) -> list[dict]:
    """
    解析ChromaDB查询结果
    """
    parsed = []

    ids = results.get("ids", [[]])[0]
    documents = results.get("documents", [[]])[0]
    metadatas = results.get("metadatas", [[]])[0]
    distances = results.get("distances", [[]])[0]

    for i, doc_id in enumerate(ids):
        distance = distances[i] if i < len(distances) else 1.0
        similarity = 1.0 / (1.0 + distance)

        parsed.append(
            {
                "id": doc_id,
                "text": documents[i] if i < len(documents) else "",
                "metadata": metadatas[i] if i < len(metadatas) else {},
                "similarity": similarity,
                "distance": distance,
            }
        )

    return parsed


def _keyword_search(
    query: str,
    top_k: int,
    filter_metadata: dict | None = None,
    candidate_ids: list[str] | None = None,
) -> list[dict]:
    """
    关键词搜索（基于文本匹配）

    注意：ChromaDB的全文本搜索功能有限，这里使用简单的文本匹配

    Args:
        query: 查询文本
        top_k: 返回结果数
        filter_metadata: 元数据过滤条件
        candidate_ids: 候选文档ID列表（仅在这些文档中做关键词匹配，避免全量加载）
    """
    try:
        collection = get_collection()

        all_docs = collection.get(ids=candidate_ids) if candidate_ids else collection.get()

        if not all_docs["ids"]:
            return []

        query_lower = query.lower()
        scored_results = []

        for i, doc_id in enumerate(all_docs["ids"]):
            document = all_docs["documents"][i]
            metadata = all_docs["metadatas"][i]

            if filter_metadata:
                match = True
                for key, value in filter_metadata.items():
                    if metadata.get(key) != value:
                        match = False
                        break
                if not match:
                    continue

            score = _calculate_keyword_score(query_lower, document.lower())
            if score > 0:
                scored_results.append(
                    {
                        "id": doc_id,
                        "text": document,
                        "metadata": metadata,
                        "similarity": score,
                        "distance": 1.0 - score,
                    }
                )

        scored_results.sort(key=lambda x: x["similarity"], reverse=True)

        return scored_results[:top_k]

    except Exception as e:
        logger.error(f"Keyword search failed: {e}")
        return []


def _calculate_keyword_score(query: str, document: str) -> float:
    """
    计算关键词匹配分数

    Args:
        query: 查询词（小写）
        document: 文档（小写）

    Returns:
        匹配分数（0-1）
    """
    query_words = set(query.split())
    doc_words = set(document.split())

    if not query_words:
        return 0.0

    intersection = query_words & doc_words

    exact_match_score = 0.0
    if query in document:
        exact_match_score = 1.0

    partial_match_score = len(intersection) / len(query_words) if query_words else 0.0

    return max(exact_match_score, partial_match_score * 0.5)


def _merge_and_rank(
    vector_results: list[dict], keyword_results: list[dict], alpha: float = 0.7
) -> list[dict]:
    """
    合并向量搜索和关键词搜索结果，并重排序

    Args:
        vector_results: 向量搜索结果
        keyword_results: 关键词搜索结果
        alpha: 向量权重（0-1）

    Returns:
        合并后的结果列表
    """
    result_map = {}

    for result in vector_results:
        doc_id = result["id"]
        result_map[doc_id] = result.copy()
        result_map[doc_id]["vector_score"] = result["similarity"]
        result_map[doc_id]["keyword_score"] = 0.0

    for result in keyword_results:
        doc_id = result["id"]
        if doc_id in result_map:
            result_map[doc_id]["keyword_score"] = result["similarity"]
        else:
            result_map[doc_id] = result.copy()
            result_map[doc_id]["vector_score"] = 0.0
            result_map[doc_id]["keyword_score"] = result["similarity"]

    for result in result_map.values():
        result["score"] = (
            alpha * result["vector_score"] + (1 - alpha) * result["keyword_score"]
        )

    merged = sorted(result_map.values(), key=lambda x: x["score"], reverse=True)

    return merged


def search_by_ids(ids: list[str]) -> list[dict]:
    """
    根据文档ID列表检索

    Args:
        ids: 文档ID列表

    Returns:
        文档列表
    """
    try:
        collection = get_collection()
        results = collection.get(ids=ids)

        parsed = []
        for i, doc_id in enumerate(ids):
            parsed.append(
                {
                    "id": doc_id,
                    "text": results["documents"][i]
                    if i < len(results["documents"])
                    else "",
                    "metadata": results["metadatas"][i]
                    if i < len(results["metadatas"])
                    else {},
                }
            )

        return parsed

    except Exception as e:
        logger.error(f"Search by IDs failed: {e}")
        raise VectorException(f"Search by IDs failed: {e}") from e
