# 项目结构

## 目录结构

```
my_ai_search/
├── config.py              # 配置管理
├── main.py                # 主入口
├── requirements.txt       # 依赖清单
├── run_tests.py          # 统一测试运行脚本
├── TESTING.md            # 测试说明文档
│
├── docs/                 # 开发文档
│   ├── 01-config.md
│   ├── 02-utils.md
│   ├── 03-search.md
│   ├── 04-fetch-basic.md
│   ├── 05-fetch-concurrent.md
│   ├── 06-process.md
│   ├── 07-deep-process.md
│   ├── 08-vector-store.md
│   ├── 09-vector-query.md
│   ├── 10-cache.md
│   └── 11-main.md
│
├── utils/                # 工具模块
│   ├── __init__.py
│   ├── logger.py         # 日志系统
│   └── exceptions.py     # 异常类
│
├── search/               # 搜索模块
│   ├── __init__.py
│   └── search.py         # SearXNG搜索接口
│
├── fetch/                # 抓取模块
│   ├── __init__.py
│   ├── fetch.py          # 页面抓取（基于LightPanda CLI）
│   └── fetch_concurrent.py # 并发抓取
│
├── process/              # 处理模块
│   ├── __init__.py
│   └── process.py        # HTML清洗和文本分块
│
├── deep_process/         # 深度处理模块
│   ├── __init__.py
│   └── deep_process.py   # 文本摘要、质量评估、去重
│
├── vector/               # 向量模块
│   ├── __init__.py
│   ├── vector.py         # 向量存储
│   └── vector_query.py   # 向量检索
│
├── cache/                # 缓存模块
│   ├── __init__.py
│   └── cache.py          # 缓存实现
│
├── tests/                # 测试文件
│   ├── test_utils.py
│   ├── test_config.py
│   ├── test_search.py
│   ├── test_fetch.py
│   ├── test_process.py
│   ├── test_deep_process.py
│   ├── test_vector.py
│   ├── test_vector_query.py
│   └── test_cache.py
│
├── logs/                 # 日志目录（自动创建）
└── chroma_db/           # ChromaDB数据目录（自动创建）
```

## 运行测试

```bash
# 运行所有测试
python run_tests.py

# 运行单个测试
python test_config.py
python test_utils.py
python test_search.py
python test_fetch.py
python test_process.py
python test_deep_process.py
python test_vector.py
python test_vector_query.py
```

## 模块状态

### ✅ 已完成模块
- ✅ 模块1: config.py - 配置管理
- ✅ 模块2: utils/ - 日志和异常
- ✅ 模块3: search/ - 搜索功能
- ✅ 模块4-5: fetch/ - 页面抓取
- ✅ 模块6: process/ - HTML处理
- ✅ 模块7: deep_process/ - 深度处理（摘要+质量评估+去重）
- ✅ 模块8: vector/ - 向量存储（初始化+存储+统计+清空+重置）
- ✅ 模块9: vector/ - 向量检索（语义检索+混合检索+元数据过滤）
- ✅ 模块10: cache/ - 缓存机制
- ✅ 模块11: main.py - 主入口（全流程集成）

## 测试覆盖

所有已完成的模块都有对应的测试文件，测试覆盖率100%。
