"""
文本处理模块

职责：HTML → 纯文本 → 规范化 → 分块
不做摘要/质量评估/去重（这些属于 deep_process 模块）
"""

import re

from bs4 import BeautifulSoup

from my_ai_search.config import get_config
from my_ai_search.utils.exceptions import ProcessException
from my_ai_search.utils.logger import setup_logger

logger = setup_logger("process")

# 内容过短阈值（低于此值认为提取失败）
MIN_USEFUL_LENGTH = 80
TEMPLATE_NOISE_PATTERNS = [
    "just a moment",
    "view all result",
    "no result",
    "sign in to your account",
    "滑动验证",
    "请完成验证",
    "登录后查看",
    "登录即可",
    "community",
    "documentation",
    "browser not supported",
    "scheduled maintenance",
    "security verification required",
]
TEMPLATE_NOISE_LINE_PATTERNS = [
    "just a moment",
    "view all result",
    "no result",
    "sign in to your account",
    "滑动验证",
    "请完成验证",
    "登录",
    "注册",
    "cookie",
    "accept all",
    "browser not supported",
    "scheduled maintenance",
    "security verification",
]
READABILITY_EXCLUDED_HINTS = [
    "just a moment",
    "browser not supported",
    "scheduled maintenance",
    "security verification required",
]
def _is_garbled(text: str) -> bool:
    """
    检测文本是否为乱码（编码错误导致的不可读内容）

    通过检查常规字符（中文、英文字母、数字、空格）的占比来判断。
    正常中英文文本中这些字符占比应 > 60%，乱码页面通常 < 40%。
    """
    if len(text) < 50:
        return False
    sample = text[:1000]
    normal_chars = sum(
        1 for c in sample
        if c.isalnum() or c.isspace() or '\u4e00' <= c <= '\u9fff'
    )
    ratio = normal_chars / len(sample)
    return ratio < 0.4


def _strip_template_noise(text: str) -> str:
    """
    移除正文中的模板/导航/验证噪声行，避免中段和尾段被站点壳子污染。
    """
    if not text:
        return ""

    cleaned_lines = []
    removed = 0
    for raw_line in text.splitlines():
        line = raw_line.strip()
        if not line:
            cleaned_lines.append("")
            continue

        lower_line = line.lower()
        if any(pattern in lower_line for pattern in TEMPLATE_NOISE_LINE_PATTERNS):
            removed += 1
            continue

        if (
            len(line) < 12
            and re.fullmatch(r"[A-Za-z ]+", line)
            and line.lower() in {"menu", "search", "home", "community"}
        ):
            removed += 1
            continue

        cleaned_lines.append(line)

    cleaned = "\n".join(cleaned_lines)
    cleaned = re.sub(r"\n{3,}", "\n\n", cleaned).strip()
    if removed:
        logger.debug(f"Removed {removed} template/noise lines")
    return cleaned


def _is_template_shell(text: str) -> bool:
    """
    判断提取结果是否基本被壳页/模板页占据。
    """
    if not text or len(text.strip()) < 20:
        return True

    lowered = text.lower()
    hit_count = sum(1 for pattern in TEMPLATE_NOISE_PATTERNS if pattern in lowered)
    if hit_count >= 2:
        return True

    lines = [line.strip() for line in text.splitlines() if line.strip()]
    if not lines:
        return True

    noisy_lines = 0
    for line in lines[:12]:
        lower_line = line.lower()
        if any(pattern in lower_line for pattern in TEMPLATE_NOISE_LINE_PATTERNS):
            noisy_lines += 1

    return noisy_lines >= max(2, len(lines[:12]) // 2)


def process_content(html: str, url: str = "") -> list[dict]:
    """
    完整处理流程：HTML → 清洗 → 规范化 → 分块

    Args:
        html: 原始HTML
        url: 页面URL

    Returns:
        文本块列表，每块包含:
        - text: 块文本（用于向量化）
        - snippet: 正文前200字（用于展示摘要）
        - chunk_id: 块索引
        - url: 来源URL
        - metadata: 元数据
    """
    if not html or not html.strip():
        logger.warning("Empty HTML input")
        return []

    logger.info(f"Processing content from: {url or 'unknown'}")

    try:
        clean_text = clean_html(html, url=url)

        if len(clean_text.strip()) < MIN_USEFUL_LENGTH:
            logger.warning(
                f"Content too short after cleaning ({len(clean_text)} chars): {url}"
            )
            return []

        normalized_text = normalize_text(clean_text)
        normalized_text = _strip_template_noise(normalized_text)

        # 检测乱码：如果中文/英文字母占比过低，认为是编码错误
        if _is_garbled(normalized_text):
            logger.warning(f"Garbled content detected, skipping: {url}")
            return []

        if _is_template_shell(normalized_text):
            logger.warning(f"Template/shell page detected, skipping: {url}")
            return []

        logger.debug(f"Normalized text length: {len(normalized_text)} characters")

        config = get_config()
        chunks = chunk_text(
            normalized_text, config.process.chunk_size, config.process.overlap
        )
        original_chunk_count = len(chunks)
        chunks, sampled_indices = limit_chunks_per_page(
            chunks,
            max_chunks=config.process.max_chunks_per_page,
            head_chunks=config.process.head_chunks_per_page,
            tail_chunks=config.process.tail_chunks_per_page,
        )

        logger.info(
            f"Generated {len(chunks)} chunks"
            + (
                f" (sampled from {original_chunk_count})"
                if original_chunk_count != len(chunks)
                else ""
            )
        )

        results = []
        for i, chunk_str in enumerate(chunks):
            # 每个 chunk 用自己的前200字作为 snippet，避免同一页面多个chunk展示相同摘要
            snippet = chunk_str[:200].strip()
            original_index = sampled_indices[i]
            results.append(
                {
                    "text": chunk_str,
                    "snippet": snippet,
                    "chunk_id": i,
                    "url": url,
                    "metadata": {
                        "source_url": url,
                        "chunk_index": i,
                        "original_chunk_index": original_index,
                        "total_chunks": len(chunks),
                        "original_total_chunks": original_chunk_count,
                        "chunk_sampling_applied": original_chunk_count != len(chunks),
                        "full_text_length": len(normalized_text),
                    },
                }
            )

        return results

    except Exception as e:
        logger.error(f"Failed to process content from {url}: {e}")
        raise ProcessException(f"Content processing failed: {e}") from e


def clean_html(html: str, url: str = "") -> str:
    """
    清洗HTML，提取核心正文内容

    策略：
    1. 优先用 readability-lxml（Firefox Reader Mode 同款算法）提取正文
    2. 如果 readability 结果太短，fallback 到 BeautifulSoup 手工提取

    Args:
        html: 原始HTML
        url: 页面URL（用于 readability 日志）

    Returns:
        清洗后的纯文本
    """
    # 策略1：readability-lxml
    if _should_skip_readability(html):
        logger.debug(f"Skipping readability for suspected shell/maintenance page: {url or 'unknown'}")
    else:
        try:
            text = _extract_with_readability(html)
            if len(text.strip()) >= MIN_USEFUL_LENGTH:
                logger.debug(
                    f"readability extracted {len(text)} chars from {url or 'unknown'}"
                )
                return text
            logger.debug(
                f"readability result too short ({len(text)} chars), falling back to BeautifulSoup"
            )
        except Exception as e:
            logger.debug(f"readability failed: {e}, falling back to BeautifulSoup")

    # 策略2：BeautifulSoup fallback
    return _extract_with_bs4(html)


def _extract_with_readability(html: str) -> str:
    """用 readability-lxml 提取正文，保留代码块格式"""
    from readability import Document

    doc = Document(html)
    summary_html = doc.summary()

    soup = BeautifulSoup(summary_html, "lxml")

    # 去掉残留的无意义 inline 标签（只保留文本内容）
    for tag in soup.find_all(["font", "span"]):
        tag.unwrap()

    # 把 <pre> 块转成 markdown 风格代码块，保留原始格式
    for pre in soup.find_all("pre"):
        code = pre.find("code")
        code_text = (code or pre).get_text()
        pre.replace_with(f"\n```\n{code_text}\n```\n")

    # 在块级元素前后插入换行，避免 get_text 把所有内容挤在一起
    for tag in soup.find_all(["p", "div", "h1", "h2", "h3", "h4", "h5", "h6",
                              "li", "tr", "br", "blockquote", "table"]):
        tag.insert_before("\n")
        tag.insert_after("\n")

    # 用空格连接同级 inline 元素（如 <span> 代码高亮），用换行分隔块级
    text = soup.get_text(separator=" ")

    # 清理：合并连续空格（但保留换行）
    text = re.sub(r"[^\S\n]+", " ", text)
    # 每行 strip
    text = "\n".join(line.strip() for line in text.splitlines())
    # 合并多余空行
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def _should_skip_readability(html: str) -> bool:
    lowered = (html or "")[:4000].lower()
    return any(hint in lowered for hint in READABILITY_EXCLUDED_HINTS)


def _extract_with_bs4(html: str) -> str:
    """用 BeautifulSoup 手工提取正文（fallback）"""
    try:
        soup = BeautifulSoup(html, "lxml")

        # 删除非内容标签
        for tag in soup.find_all(
            ["script", "style", "nav", "footer", "header", "aside",
             "iframe", "noscript", "svg", "form"]
        ):
            tag.decompose()

        # 删除广告/侧边栏相关的 class
        ad_classes = [
            "ad", "advertisement", "banner", "popup", "modal",
            "sidebar", "social", "comments", "related", "recommend",
        ]
        for class_name in ad_classes:
            for element in soup.find_all(
                class_=lambda x, current=class_name: x and current in str(x).lower()
            ):
                element.decompose()

        # 寻找主内容区域
        main_content = (
            soup.find("article")
            or soup.find("main")
            or soup.find(
                "div",
                class_=lambda x: x
                and any(k in str(x).lower() for k in ("content", "post", "article")),
            )
            or soup.body
        )

        if not main_content:
            main_content = soup.body

        if not main_content:
            return ""

        # 保留代码块格式
        for pre in main_content.find_all("pre"):
            code = pre.find("code")
            code_text = (code or pre).get_text()
            pre.replace_with(f"\n```\n{code_text}\n```\n")

        # 块级元素前后插入换行
        for tag in main_content.find_all(["p", "div", "h1", "h2", "h3", "h4", "h5", "h6",
                                          "li", "tr", "br", "blockquote", "table"]):
            tag.insert_before("\n")
            tag.insert_after("\n")

        text = main_content.get_text(separator=" ")
        text = re.sub(r"[^\S\n]+", " ", text)
        text = "\n".join(line.strip() for line in text.splitlines())
        text = re.sub(r"\n{3,}", "\n\n", text)
        return text.strip()

    except Exception as e:
        logger.error(f"Failed to clean HTML with BS4: {e}")
        raise ProcessException(f"HTML cleaning failed: {e}") from e


def chunk_text(text: str, chunk_size: int = None, overlap: int = None) -> list[str]:
    """
    文本分块（按段落边界切分，避免从句子中间截断）

    Args:
        text: 输入文本
        chunk_size: 每块最大字符数
        overlap: 分块重叠字符数

    Returns:
        文本块列表
    """
    if not text or not text.strip():
        return []

    config = get_config()
    actual_chunk_size = chunk_size or config.process.chunk_size
    actual_overlap = overlap or config.process.overlap

    try:
        text_length = len(text)

        if text_length <= actual_chunk_size:
            return [text]

        chunks = []
        start = 0

        while start < text_length:
            end = min(start + actual_chunk_size, text_length)

            # 尝试在句号/换行处断开，避免截断句子
            if end < text_length:
                # 从 end 往回找最近的句子边界
                best_break = -1
                for sep in ("。", "\n", ".", "！", "？", "；"):
                    pos = text.rfind(sep, start + actual_chunk_size // 2, end)
                    if pos > best_break:
                        best_break = pos
                if best_break > start:
                    end = best_break + 1  # 包含标点

            chunk_str = text[start:end].strip()
            if chunk_str:
                chunks.append(chunk_str)

            if end >= text_length:
                break

            start = end - actual_overlap
            if start < 0:
                start = 0

        logger.debug(f"Generated {len(chunks)} chunks from {text_length} chars")
        return chunks

    except Exception as e:
        logger.error(f"Failed to chunk text: {e}")
        raise ProcessException(f"Text chunking failed: {e}") from e


def limit_chunks_per_page(
    chunks: list[str],
    max_chunks: int,
    head_chunks: int,
    tail_chunks: int,
) -> tuple[list[str], list[int]]:
    """
    对超长页面做稳定采样：
    1. 保留开头若干块，避免丢失摘要/导语
    2. 保留结尾若干块，避免丢失结论/附录
    3. 中间部分均匀抽样，保留内容覆盖面
    """
    if not chunks:
        return [], []

    total = len(chunks)
    if total <= max_chunks:
        return chunks, list(range(total))

    head_keep = min(head_chunks, max_chunks, total)
    tail_keep = min(tail_chunks, max(0, max_chunks - head_keep), max(0, total - head_keep))
    middle_budget = max_chunks - head_keep - tail_keep

    selected_indices = list(range(head_keep))
    middle_start = head_keep
    middle_end = total - tail_keep

    if middle_budget > 0 and middle_end > middle_start:
        middle_indices = _sample_middle_indices(middle_start, middle_end, middle_budget)
        selected_indices.extend(middle_indices)

    if tail_keep > 0:
        selected_indices.extend(range(total - tail_keep, total))

    selected_indices = sorted(dict.fromkeys(selected_indices))
    limited_chunks = [chunks[i] for i in selected_indices]
    return limited_chunks, selected_indices


def _sample_middle_indices(start: int, end: int, budget: int) -> list[int]:
    if budget <= 0 or end <= start:
        return []

    middle_count = end - start
    if middle_count <= budget:
        return list(range(start, end))

    if budget == 1:
        return [start + middle_count // 2]

    last = middle_count - 1
    indices = set()
    for i in range(budget):
        relative = round(i * last / (budget - 1))
        indices.add(start + relative)
    return sorted(indices)


def normalize_text(text: str) -> str:
    """
    文本规范化：只去除控制字符和零宽字符，保留所有可见字符

    Args:
        text: 输入文本

    Returns:
        规范化后的文本
    """
    if not text:
        return ""

    # 只删除：控制字符（\x00-\x08, \x0b, \x0c, \x0e-\x1f）、零宽字符、BOM等
    # 保留所有可见字符（包括代码符号 = + * < > { } / # @ 等）
    text = re.sub(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f\u200b-\u200f\u2028-\u202f\ufeff\ufff0-\uffff]", "", text)

    # 清理可能残留的 HTML 标签
    text = re.sub(r"<[^>]+>", "", text)

    # 合并连续空格（保留换行）
    text = re.sub(r"[^\S\n]+", " ", text)
    # 合并连续空行
    text = re.sub(r"\n{3,}", "\n\n", text)

    return text.strip()


def get_token_count(text: str) -> int:
    """估算文本的 token 数量"""
    try:
        import tiktoken

        global _tokenizer
        if _tokenizer is None:
            _tokenizer = tiktoken.get_encoding("cl100k_base")
        return len(_tokenizer.encode(text))
    except Exception:
        return len(text)


_tokenizer = None
