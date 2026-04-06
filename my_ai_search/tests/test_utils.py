#!/usr/bin/env python3

import os
import sys

# 添加项目根目录到路径
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from my_ai_search.utils.exceptions import FetchException, SearchException
from my_ai_search.utils.logger import get_logger, setup_logger


def test_logger():
    """测试日志系统"""
    print("测试1：日志系统")
    logger = setup_logger("test")
    logger.debug("This is a debug message")
    logger.info("This is an info message")
    logger.warning("This is a warning message")
    logger.error("This is an error message")
    print("✅ 测试1通过\n")


def test_logger_file():
    """测试日志文件创建"""
    print("测试2：日志文件创建")

    # 检查日志目录是否存在
    if os.path.exists("logs/app.log"):
        with open("logs/app.log", encoding="utf-8") as f:
            content = f.read()
            if "test - INFO - This is an info message" in content:
                print("✅ 日志文件创建成功并包含日志记录")
            else:
                print("❌ 日志文件内容不正确")
    else:
        print("❌ 日志文件不存在")

    print()


def test_exceptions():
    """测试异常类"""
    print("测试3：异常类")

    try:
        raise SearchException("Test search error")
    except SearchException as e:
        print(f"Caught: {e}")
        assert str(e).startswith("Search Error:")
        print("✅ SearchException 正常工作")

    try:
        raise FetchException("https://test.com", "Connection failed")
    except FetchException as e:
        print(f"Caught: {e}")
        assert "https://test.com" in str(e)
        print("✅ FetchException 正常工作")

    print()


def test_get_logger():
    """测试get_logger函数"""
    print("测试4：get_logger函数")
    logger = get_logger("fetch")
    logger.info("Using get_logger")
    print("✅ 测试4通过\n")


if __name__ == "__main__":
    print("=" * 50)
    print("Utils 模块测试")
    print("=" * 50 + "\n")

    try:
        test_logger()
        test_logger_file()
        test_exceptions()
        test_get_logger()

        print("=" * 50)
        print("所有测试通过！")
        print("=" * 50)
    except Exception as e:
        print(f"❌ 测试失败: {e}")
        import traceback

        traceback.print_exc()
        sys.exit(1)
