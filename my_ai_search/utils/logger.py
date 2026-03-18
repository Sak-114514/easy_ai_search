import logging
from pathlib import Path
from config import get_config


def setup_logger(name: str = "app") -> logging.Logger:
    """
    设置并返回日志记录器

    Args:
        name: 日志记录器名称，通常为模块名

    Returns:
        配置好的Logger对象
    """
    config = get_config()

    # 创建日志目录
    log_dir = Path(config.log.file).parent
    log_dir.mkdir(parents=True, exist_ok=True)

    # 创建或获取logger
    logger = logging.getLogger(name)
    logger.setLevel(getattr(logging, config.log.level.upper()))

    # 避免重复添加handler
    if logger.handlers:
        return logger

    # 创建格式化器
    formatter = logging.Formatter(config.log.format)

    # 控制台handler
    console_handler = logging.StreamHandler()
    console_handler.setLevel(getattr(logging, config.log.level.upper()))
    console_handler.setFormatter(formatter)
    logger.addHandler(console_handler)

    # 文件handler
    file_handler = logging.FileHandler(config.log.file, encoding="utf-8")
    file_handler.setLevel(getattr(logging, config.log.level.upper()))
    file_handler.setFormatter(formatter)
    logger.addHandler(file_handler)

    return logger


def get_logger(name: str = "app") -> logging.Logger:
    """
    获取日志记录器（便捷函数）

    Args:
        name: 日志记录器名称

    Returns:
        Logger对象
    """
    return logging.getLogger(name)
