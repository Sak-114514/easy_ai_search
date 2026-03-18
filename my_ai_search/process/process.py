from bs4 import BeautifulSoup
from typing import List, Dict
from config import get_config
from utils.logger import setup_logger
from utils.exceptions import ProcessException

_tokenizer = None

logger = setup_logger("process")


def process_content(html: str, url: str = "") -> List[Dict]:
    """
    完整处理流程

    Args:
        html: 原始HTML
        url: 页面URL（用于元数据）

    Returns:
        文本块列表
    """
    if not html or not html.strip():
        logger.warning("Empty HTML input")
        return []

    logger.info(f"Processing content from: {url or 'unknown'}")

    try:
        clean_text = clean_html(html)
        logger.debug(f"Cleaned text length: {len(clean_text)} characters")

        if len(clean_text.strip()) == 0:
            logger.warning(f"No content after cleaning: {url}")
            return []

        normalized_text = normalize_text(clean_text)
        logger.debug(f"Normalized text length: {len(normalized_text)} characters")

        config = get_config()
        chunks = chunk_text(
            normalized_text, config.process.chunk_size, config.process.overlap
        )

        logger.info(f"Generated {len(chunks)} chunks")

        results = []
        for i, chunk_str in enumerate(chunks):
            results.append(
                {
                    "text": chunk_str,
                    "chunk_id": i,
                    "url": url,
                    "metadata": {
                        "source_url": url,
                        "chunk_index": i,
                        "total_chunks": len(chunks),
                    },
                }
            )

        return results

    except Exception as e:
        logger.error(f"Failed to process content from {url}: {e}")
        raise ProcessException(f"Content processing failed: {e}")


def clean_html(html: str) -> str:
    """
    清洗HTML，提取核心内容

    Args:
        html: 原始HTML

    Returns:
        清洗后的纯文本

    Raises:
        ProcessException: HTML解析失败
    """
    try:
        soup = BeautifulSoup(html, "lxml")

        tags_to_remove = [
            "script",
            "style",
            "nav",
            "footer",
            "header",
            "aside",
            "iframe",
            "noscript",
            "svg",
            "form",
        ]

        for tag in soup.find_all(tags_to_remove):
            tag.decompose()

        ad_classes = [
            "ad",
            "advertisement",
            "banner",
            "popup",
            "modal",
            "sidebar",
            "social",
            "comments",
            "related",
        ]

        for class_name in ad_classes:
            for element in soup.find_all(
                class_=lambda x: x and class_name in x.lower().split()
            ):
                element.decompose()

        main_content = (
            soup.find("article")
            or soup.find("main")
            or soup.find(
                "div",
                class_=lambda x: x and ("content" in x.lower() or "post" in x.lower()),
            )
            or soup.body
        )

        if not main_content:
            logger.warning("No main content found, using entire body")
            main_content = soup.body

        text = main_content.get_text(separator=" ", strip=True)

        text = " ".join(text.split())

        logger.debug(f"Extracted {len(text)} characters from HTML")
        return text

    except Exception as e:
        logger.error(f"Failed to clean HTML: {e}")
        raise ProcessException(f"HTML cleaning failed: {e}")


def chunk_text(text: str, chunk_size: int = None, overlap: int = None) -> List[str]:
    """
    文本分块（基于字符，避免tiktoken性能问题）

    Args:
        text: 输入文本
        chunk_size: 每块字符数（相当于token数）
        overlap: 分块重叠字符数

    Returns:
        文本块列表

    Raises:
        ProcessException: 分块失败
    """
    if not text or not text.strip():
        return []

    config = get_config()
    actual_chunk_size = chunk_size or config.process.chunk_size
    actual_overlap = overlap or config.process.overlap

    logger.debug(
        f"Chunking text: size={actual_chunk_size} chars, overlap={actual_overlap} chars"
    )

    try:
        text_length = len(text)

        logger.debug(f"Total characters: {text_length}")

        if text_length <= actual_chunk_size:
            return [text]

        logger.debug(f"Splitting into chunks...")
        chunks = []
        start = 0

        while start < text_length:
            end = min(start + actual_chunk_size, text_length)
            chunk_str = text[start:end]
            chunks.append(chunk_str)

            if end >= text_length:
                break

            start = end - actual_overlap
            if start < 0:
                start = 0

        logger.debug(f"Generated {len(chunks)} chunks")
        return chunks

    except Exception as e:
        logger.error(f"Failed to chunk text: {e}")
        raise ProcessException(f"Text chunking failed: {e}")


def normalize_text(text: str) -> str:
    """
    文本规范化

    Args:
        text: 输入文本

    Returns:
        规范化后的文本
    """
    if not text:
        return ""

    text = " ".join(text.split())

    import re

    text = re.sub(r'[^\w\s\u4e00-\u9fff\.,!?;:()\-\[\]\'"]', " ", text)

    text = re.sub(r"\s+", " ", text).strip()

    return text


def get_token_count(text: str) -> int:
    """
    估算文本的token数量（基于字符数的简单估算）

    Args:
        text: 输入文本

    Returns:
        估算的token数量
    """
    try:
        import tiktoken

        global _tokenizer
        if _tokenizer is None:
            logger.debug("Initializing tokenizer for token count...")
            _tokenizer = tiktoken.get_encoding("cl100k_base")

        tokens = _tokenizer.encode(text)
        return len(tokens)

    except Exception as e:
        logger.warning(
            f"Failed to count tokens with tiktoken: {e}, using character count"
        )
        return len(text)
