"""
pytest配置文件
"""

import pytest
import sys
import os
from pathlib import Path

# 添加项目根目录到Python路径
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

os.environ.setdefault(
    "API_KEYS_JSON",
    '{"default":"default-api-key-123","admin":"admin-api-key-456"}',
)
os.environ.setdefault("JWT_SECRET", "test-jwt-secret")
os.environ.setdefault("DATABASE_URL", "sqlite:///test_logs.db")
os.environ.setdefault("LOG_LEVEL", "DEBUG")
os.environ.setdefault("API_DEBUG", "true")


@pytest.fixture(scope="session")
def test_config():
    """测试配置"""
    return {
        "database_url": "sqlite:///test_logs.db",
        "log_level": "DEBUG",
    }


def pytest_configure(config):
    """pytest配置钩子"""
    config.addinivalue_line("markers", "asyncio: mark test as async")
    config.addinivalue_line("markers", "integration: mark test as integration test")
    config.addinivalue_line("markers", "unit: mark test as unit test")


def pytest_collection_modifyitems(config, items):
    """修改测试项"""
    # 自动添加asyncio标记给所有async测试函数
    for item in items:
        if asyncio.iscoroutinefunction(item.obj):
            item.add_marker(pytest.mark.asyncio)


# 导入asyncio
import asyncio
