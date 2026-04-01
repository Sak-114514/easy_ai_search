"""
日志工具
"""

from loguru import logger
import sys
from pathlib import Path


def setup_logger(name: str = "api_server", log_dir: str = "./logs"):
    """
    设置日志

    Args:
        name: 日志名称
        log_dir: 日志目录
    """
    # 创建日志目录
    Path(log_dir).mkdir(parents=True, exist_ok=True)

    # 配置 loguru
    logger.remove()  # 移除默认 handler

    # 控制台输出
    logger.add(
        sys.stdout,
        format="<green>{time:YYYY-MM-DD HH:mm:ss}</green> | <level>{level: <8}</level> | <cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> - <level>{message}</level>",
        level="INFO",
    )

    # 文件输出
    logger.add(
        f"{log_dir}/{name}.log",
        rotation="1 day",
        retention="7 days",
        compression="zip",
        format="{time:YYYY-MM-DD HH:mm:ss} | {level: <8} | {name}:{function}:{line} - {message}",
        level="DEBUG",
    )

    return logger
