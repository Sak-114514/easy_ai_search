from typing import List, Dict, Optional
import hashlib
import re
from thefuzz import fuzz
from my_ai_search.config import get_config
from .summary_provider import summarize_with_backend
from my_ai_search.utils.logger import setup_logger
from my_ai_search.utils.exceptions import DeepProcessException

logger = setup_logger("deep_process")


def deep_process_page(
    chunks: List[Dict],
    enable_summary: bool = True,
    enable_quality_check: bool = True,
    min_quality_score: float = 0.5,
) -> List[Dict]:
    """
    Per-page deep processing: quality check + quality filter.

    注意：不再用规则摘要覆盖 text 字段。
    text 保持原始正文（用于向量化），snippet 由 process 模块生成（用于展示）。
    未来可在此处接入 LLM 摘要，写入 snippet 字段。

    Args:
        chunks: Text chunks from a single page
        enable_summary: 预留参数（未来接入 LLM 摘要）
        enable_quality_check: Whether to check quality
        min_quality_score: Minimum quality score threshold

    Returns:
        Processed chunks (after quality filtering)
    """
    if not chunks:
        return []

    final_chunks = []

    for chunk in chunks:
        chunk = chunk.copy()
        original_text = chunk.get("text", "")
        if not original_text.strip():
            continue

        if enable_quality_check:
            try:
                quality = assess_quality(original_text)
                score = quality["overall_score"]
                if score < min_quality_score:
                    logger.debug(f"Filtered low quality chunk (score: {score:.2f})")
                    continue
                chunk["quality_score"] = score
            except Exception as e:
                logger.warning(f"Failed to assess quality: {e}")
                chunk["quality_score"] = 0.0

        if enable_summary:
            try:
                summary = generate_summary(original_text)
                chunk["summary"] = summary
                if summary:
                    chunk["snippet"] = summary
                    metadata = chunk.get("metadata", {})
                    metadata["summary"] = summary
                    chunk["metadata"] = metadata
            except Exception as e:
                logger.warning(f"Failed to generate page summary: {e}")
                chunk["summary"] = ""

        chunk["is_duplicate"] = False
        final_chunks.append(chunk)

    logger.info(f"Per-page deep process: {len(chunks)} -> {len(final_chunks)} chunks")
    return final_chunks


def dedup_chunks(
    chunks: List[Dict], similarity_threshold: Optional[float] = None
) -> List[Dict]:
    """
    Dedup chunks globally (across all pages).
    Should be called after per-page deep processing.

    Args:
        chunks: All processed chunks from all pages
        similarity_threshold: Dedup threshold

    Returns:
        Chunks after dedup
    """
    if not chunks:
        return []

    duplicate_info = detect_duplicates(
        chunks, similarity_threshold=similarity_threshold
    )

    duplicate_ids = duplicate_info.get("duplicate_ids", [])
    mapping = duplicate_info.get("mapping", {})

    for chunk in chunks:
        chunk_id = f"{chunk.get('url', 'unknown')}#chunk_{chunk.get('chunk_id', 0)}"
        if chunk_id in duplicate_ids:
            chunk["is_duplicate"] = True
            chunk["is_duplicate_of"] = mapping.get(chunk_id, "")
            logger.debug(f"Marked chunk {chunk_id} as duplicate")

    final_chunks = [c for c in chunks if not c.get("is_duplicate", False)]

    logger.info(
        f"Global dedup: {len(chunks)} -> {len(final_chunks)} chunks "
        f"({len(duplicate_ids)} duplicates removed)"
    )
    return final_chunks


def deep_process_content(
    chunks: List[Dict],
    url: str = "",
    enable_summary: bool = True,
    enable_dedup: bool = True,
    enable_quality_check: bool = True,
) -> List[Dict]:
    """
    深度处理文本块

    Args:
        chunks: 文本块列表 [{text, chunk_id, url, metadata}, ...]
        url: 来源URL
        enable_summary: 是否生成摘要
        enable_dedup: 是否启用去重
        enable_quality_check: 是否进行质量检查

    Returns:
        处理后的文本块列表

    Raises:
        DeepProcessException: 深度处理失败
    """
    if not chunks:
        logger.warning("Empty chunks list, nothing to process")
        return []

    logger.info(f"Deep processing {len(chunks)} chunks from: {url or 'unknown'}")

    try:
        processed_chunks = []
        duplicate_info = {}

        if not enable_summary and not enable_quality_check and not enable_dedup:
            logger.info("All deep processing disabled, returning original chunks")
            return chunks

        if enable_summary or enable_quality_check:
            for chunk in chunks:
                processed = chunk.copy()
                original_text = chunk.get("text", "")

                if enable_summary:
                    try:
                        summary = generate_summary(original_text)
                        processed["summary"] = summary
                        if summary:
                            processed["snippet"] = summary
                            metadata = processed.get("metadata", {})
                            metadata["summary"] = summary
                            processed["metadata"] = metadata
                        logger.debug(
                            f"Generated summary for chunk {chunk.get('chunk_id')}"
                        )
                    except Exception as e:
                        logger.warning(f"Failed to generate summary: {e}")
                        processed["summary"] = ""

                if enable_quality_check:
                    try:
                        quality = assess_quality(original_text)
                        processed["quality_score"] = quality["overall_score"]
                        processed["quality_details"] = quality
                        logger.debug(
                            f"Quality score: {quality['overall_score']:.2f} for chunk {chunk.get('chunk_id')}"
                        )
                    except Exception as e:
                        logger.warning(f"Failed to assess quality: {e}")
                        processed["quality_score"] = 0.5

                processed["original_text"] = original_text
                processed["is_duplicate"] = False
                processed["is_duplicate_of"] = ""

                processed_chunks.append(processed)
        else:
            processed_chunks = chunks[:]

        if enable_dedup:
            duplicate_info = detect_duplicates(processed_chunks)

            duplicate_ids = duplicate_info.get("duplicate_ids", [])
            mapping = duplicate_info.get("mapping", {})

            for chunk in processed_chunks:
                chunk_id = (
                    f"{chunk.get('url', 'unknown')}#chunk_{chunk.get('chunk_id', 0)}"
                )
                if chunk_id in duplicate_ids:
                    chunk["is_duplicate"] = True
                    chunk["is_duplicate_of"] = mapping.get(chunk_id, "")
                    logger.debug(f"Marked chunk {chunk_id} as duplicate")

        config = get_config()
        min_quality = config.deep_process.min_quality_score

        final_chunks = []
        for chunk in processed_chunks:
            if chunk.get("is_duplicate", False):
                continue

            if enable_quality_check:
                quality = chunk.get("quality_score", 0)
                if quality < min_quality:
                    logger.debug(f"Filtered low quality chunk (score: {quality:.2f})")
                    continue

            final_chunks.append(chunk)

        logger.info(
            f"Deep processing completed: {len(chunks)} -> {len(final_chunks)} chunks"
        )
        return final_chunks

    except Exception as e:
        logger.error(f"Deep processing failed: {e}")
        raise DeepProcessException(f"Deep processing failed: {e}")


def estimate_query_relevance(query: str, chunk: Dict) -> float:
    """
    估算 chunk 与 query 的轻量相关性分数，用于挑选 deep_process 候选。
    """
    if not query or not query.strip():
        return 0.0

    text = (chunk.get("text") or "").lower()
    snippet = (chunk.get("snippet") or "").lower()
    metadata = chunk.get("metadata") or {}
    title = str(metadata.get("title") or "").lower()
    source_url = str(metadata.get("source_url") or chunk.get("url") or "").lower()

    query_lower = query.lower()
    terms = [t for t in re.split(r"\s+", query_lower) if t]
    if not terms:
        terms = [query_lower]

    haystack = "\n".join([title, snippet, text[:2000]])
    score = 0.0

    if query_lower in haystack:
        score += 6.0

    unique_terms = list(dict.fromkeys(terms))
    for term in unique_terms:
        if len(term) < 2:
            continue
        if term in title:
            score += 2.5
        if term in snippet:
            score += 1.5
        if term in text:
            score += 1.0
        if term in source_url:
            score += 0.5

    text_length = len(text)
    if 120 <= text_length <= 4000:
        score += 0.8
    elif text_length > 4000:
        score += 0.4

    if metadata.get("original_chunk_index", metadata.get("chunk_index", 0)) == 0:
        score += 0.8

    return score


def select_deep_process_candidates(
    chunks: List[Dict],
    query: str,
    max_candidates: int,
) -> List[Dict]:
    """
    从全部 chunk 中选出值得做 deep_process 的候选。
    """
    if not chunks or max_candidates <= 0:
        return []

    scored_chunks = []
    for index, chunk in enumerate(chunks):
        score = estimate_query_relevance(query, chunk)
        scored_chunks.append((score, index, chunk))

    scored_chunks.sort(key=lambda item: (item[0], -item[1]), reverse=True)
    selected = scored_chunks[:max_candidates]
    selected.sort(key=lambda item: item[1])
    return [chunk for _, _, chunk in selected]


def generate_summary(text: str, max_length: Optional[int] = None) -> str:
    """
    生成文本摘要（抽取式摘要）

    Args:
        text: 输入文本
        max_length: 摘要最大长度

    Returns:
        摘要文本

    Raises:
        DeepProcessException: 摘要生成失败
    """
    if not text or not text.strip():
        return ""

    config = get_config()
    actual_max_length = max_length or config.deep_process.summary_length

    try:
        backend = (config.deep_process.summary_backend or "extractive").lower()
        if backend != "extractive":
            llm_summary = summarize_with_backend(
                text=text,
                backend=backend,
                api_url=config.deep_process.summary_api_url,
                model=config.deep_process.summary_model,
                timeout=config.deep_process.summary_timeout,
                max_length=actual_max_length,
                api_key=config.deep_process.summary_api_key,
            )
            if llm_summary:
                logger.debug(
                    f"Generated summary via {backend}: {len(llm_summary)} chars from {len(text)} chars"
                )
                return llm_summary

        sentences = text.split("。")
        sentences = [s.strip() for s in sentences if s.strip()]

        if len(sentences) <= 3:
            return text[:actual_max_length]

        scored_sentences = []

        for i, sentence in enumerate(sentences):
            position_weight = 1.0 - (i / len(sentences)) * 0.5

            length = len(sentence)
            if length < 10:
                length_weight = 0.3
            elif length < 50:
                length_weight = 1.0
            else:
                length_weight = 0.7

            score = position_weight * length_weight
            scored_sentences.append((sentence, score))

        scored_sentences.sort(key=lambda x: x[1], reverse=True)
        summary_sentences = [s[0] for s in scored_sentences[:3]]

        summary = "。".join(summary_sentences)

        if len(summary) > actual_max_length:
            summary = summary[:actual_max_length].rstrip("。") + "。"

        logger.debug(f"Generated summary: {len(summary)} chars from {len(text)} chars")
        return summary

    except Exception as e:
        logger.error(f"Failed to generate summary: {e}")
        raise DeepProcessException(f"Summary generation failed: {e}")


def assess_quality(text: str) -> Dict:
    """
    评估文本质量

    Args:
        text: 输入文本

    Returns:
        质量评估结果

    Raises:
        DeepProcessException: 质量评估失败
    """
    if not text or not text.strip():
        return {
            "overall_score": 0.0,
            "readability": 0.0,
            "length_score": 0.0,
            "content_score": 0.0,
            "is_valid": False,
        }

    try:
        config = get_config()

        length = len(text)
        min_length = config.deep_process.min_content_length
        max_length = config.deep_process.max_content_length

        words = text.split()
        unique_chars = set(text)
        char_diversity = len(unique_chars) / max(len(text), 1)
        word_diversity = len(set(words)) / max(len(words), 1) if words else 0

        from collections import Counter

        char_freq = Counter(text)
        most_common_char_ratio = char_freq.most_common(1)[0][1] / len(text)

        if most_common_char_ratio > 0.15:
            char_diversity = char_diversity * 0.1

        if length < min_length:
            content_score = char_diversity * 15
        else:
            content_score = char_diversity * 0.8 + word_diversity * 0.2
            content_score = min(content_score * 10, 1.0)

        content_score = min(content_score, 1.0)

        if length < min_length:
            length_score = 0.4
        elif length > max_length:
            length_score = 0.7
        else:
            length_score = 1.0

        sentences = text.split("。")
        avg_sentence_length = sum(len(s) for s in sentences) / max(len(sentences), 1)

        if 20 <= avg_sentence_length <= 100:
            readability = 1.0
        elif avg_sentence_length < 20:
            readability = 0.3
        else:
            readability = 0.6

        overall_score = length_score * 0.4 + readability * 0.3 + content_score * 0.3
        is_valid = overall_score >= config.deep_process.min_quality_score

        logger.debug(
            f"Quality assessment: overall={overall_score:.2f}, valid={is_valid}"
        )

        return {
            "overall_score": overall_score,
            "readability": readability,
            "length_score": length_score,
            "content_score": content_score,
            "is_valid": is_valid,
        }

    except Exception as e:
        logger.error(f"Failed to assess quality: {e}")
        raise DeepProcessException(f"Quality assessment failed: {e}")


def detect_duplicates(
    chunks: List[Dict], similarity_threshold: Optional[float] = None
) -> Dict:
    """
    检测重复内容

    Args:
        chunks: 文本块列表
        similarity_threshold: 相似度阈值

    Returns:
        去重映射

    Raises:
        DeepProcessException: 重复检测失败
    """
    if not chunks:
        return {"duplicate_ids": [], "keep_ids": [], "mapping": {}}

    try:
        config = get_config()
        threshold = similarity_threshold or config.deep_process.dedup_threshold

        logger.debug(f"Detecting duplicates with threshold: {threshold}")

        text_hashes = {}
        for chunk in chunks:
            chunk_id = f"{chunk.get('url', 'unknown')}#chunk_{chunk.get('chunk_id', 0)}"
            text = chunk.get("text", "")
            text_hash = hashlib.md5(text.encode("utf-8")).hexdigest()
            text_hashes[chunk_id] = text_hash

        hash_to_ids = {}
        for chunk_id, text_hash in text_hashes.items():
            if text_hash not in hash_to_ids:
                hash_to_ids[text_hash] = []
            hash_to_ids[text_hash].append(chunk_id)

        duplicate_ids = []
        keep_ids = []
        mapping = {}

        for text_hash, ids in hash_to_ids.items():
            if len(ids) > 1:
                keep_ids.append(ids[0])
                for dup_id in ids[1:]:
                    duplicate_ids.append(dup_id)
                    mapping[dup_id] = ids[0]
            else:
                keep_ids.append(ids[0])

        if threshold < 1.0:
            from collections import defaultdict

            url_groups = defaultdict(list)
            for chunk in chunks:
                chunk_id = (
                    f"{chunk.get('url', 'unknown')}#chunk_{chunk.get('chunk_id', 0)}"
                )
                if chunk_id not in duplicate_ids:
                    url_groups[chunk.get("url", "unknown")].append(chunk)

            for url, group_chunks in url_groups.items():
                for i, chunk1 in enumerate(group_chunks):
                    id1 = f"{chunk1.get('url', 'unknown')}#chunk_{chunk1.get('chunk_id', 0)}"
                    if id1 in duplicate_ids:
                        continue

                    text1 = chunk1.get("text", "")

                    for chunk2 in group_chunks[i + 1 :]:
                        id2 = f"{chunk2.get('url', 'unknown')}#chunk_{chunk2.get('chunk_id', 0)}"
                        if id2 in duplicate_ids:
                            continue

                        text2 = chunk2.get("text", "")

                        similarity = fuzz.ratio(text1, text2) / 100.0

                        if similarity >= threshold:
                            duplicate_ids.append(id2)
                            mapping[id2] = id1
                            if id2 in keep_ids:
                                keep_ids.remove(id2)

                            logger.debug(
                                f"Found near-duplicate: {id1} vs {id2} (similarity: {similarity:.2f})"
                            )

        logger.info(f"Duplicate detection: {len(duplicate_ids)} duplicates found")

        return {
            "duplicate_ids": duplicate_ids,
            "keep_ids": keep_ids,
            "mapping": mapping,
        }

    except Exception as e:
        logger.error(f"Failed to detect duplicates: {e}")
        raise DeepProcessException(f"Duplicate detection failed: {e}")


def extract_key_info(text: str) -> Dict:
    """
    提取关键信息

    Args:
        text: 输入文本

    Returns:
        关键信息字典

    Raises:
        DeepProcessException: 关键信息提取失败
    """
    if not text or not text.strip():
        return {"keywords": [], "entities": [], "sentences_count": 0, "word_count": 0}

    try:
        words = text.split()
        word_count = len(words)

        word_freq = {}
        for word in words:
            if len(word) > 2:
                word_freq[word] = word_freq.get(word, 0) + 1

        sorted_words = sorted(word_freq.items(), key=lambda x: x[1], reverse=True)
        keywords = [w[0] for w in sorted_words[:5]]

        sentences = text.split("。")
        sentences_count = len([s for s in sentences if s.strip()])

        return {
            "keywords": keywords,
            "entities": [],
            "sentences_count": sentences_count,
            "word_count": word_count,
        }

    except Exception as e:
        logger.error(f"Failed to extract key info: {e}")
        raise DeepProcessException(f"Key info extraction failed: {e}")
