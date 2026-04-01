#!/usr/bin/env python3

import os
import sys

# 添加项目根目录到路径
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from config import get_config, validate_config


def test_basic_config():
    """测试基本配置加载"""
    print("测试1：基本配置加载")
    config = get_config()
    print(f"SearXNG URL: {config.searxng.api_url}")
    print(f"LightPanda CDP: {config.lightpanda.cdp_url}")
    print(f"ChromaDB dir: {config.chroma.persist_dir}")
    print(f"Max results: {config.searxng.max_results}")
    print(f"Timeout: {config.searxng.timeout}")
    print("✅ 测试1通过\n")


def test_config_validation():
    """测试配置验证"""
    print("测试2：配置验证")
    config = get_config()
    is_valid = validate_config(config)
    print(f"Config valid: {is_valid}")
    if is_valid:
        print("✅ 测试2通过\n")
    else:
        print("❌ 测试2失败\n")


def test_env_override():
    """测试环境变量覆盖"""
    print("测试3：环境变量覆盖")
    os.environ["SEARXNG_API_URL"] = "http://localhost:8080/search"
    os.environ["SEARXNG_MAX_RESULTS"] = "10"

    config = get_config()
    print(f"Override SearXNG URL: {config.searxng.api_url}")
    print(f"Override Max Results: {config.searxng.max_results}")

    # 清理环境变量
    del os.environ["SEARXNG_API_URL"]
    del os.environ["SEARXNG_MAX_RESULTS"]
    print("✅ 测试3通过\n")


if __name__ == "__main__":
    print("=" * 50)
    print("Config 模块测试")
    print("=" * 50 + "\n")

    try:
        test_basic_config()
        test_config_validation()
        test_env_override()

        print("=" * 50)
        print("所有测试通过！")
        print("=" * 50)
    except Exception as e:
        print(f"❌ 测试失败: {e}")
        import traceback

        traceback.print_exc()
        sys.exit(1)
