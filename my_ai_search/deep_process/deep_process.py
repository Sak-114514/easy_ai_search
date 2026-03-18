from typing import List, Dict, Optional
import hashlib
from thefuzz import fuzz
from config import get_config
from utils.logger import setup_logger
from utils.exceptions import DeepProcessException

logger = setup_logger("deep_process")


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

        if enable_summary or enable_quality_check:
            for chunk in chunks:
                processed = chunk.copy()
                original_text = chunk.get("text", "")

                if enable_summary:
                    try:
                        summary = generate_summary(original_text)
                        processed["summary"] = summary
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

            if enable_summary and chunk.get("summary"):
                summary = chunk["summary"]
                original = chunk.get("original_text", "")
                if len(summary) > 0.1 * len(original):
                    chunk["text"] = summary
                    logger.debug(f"Using summary for chunk {chunk.get('chunk_id')}")

            final_chunks.append(chunk)

        logger.info(
            f"Deep processing completed: {len(chunks)} -> {len(final_chunks)} chunks"
        )
        return final_chunks

    except Exception as e:
        logger.error(f"Deep processing failed: {e}")
        raise DeepProcessException(f"Deep processing failed: {e}")


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
            for i, chunk1 in enumerate(chunks):
                id1 = (
                    f"{chunk1.get('url', 'unknown')}#chunk_{chunk1.get('chunk_id', 0)}"
                )
                if id1 in duplicate_ids:
                    continue

                text1 = chunk1.get("text", "")

                for chunk2 in chunks[i + 1 :]:
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
