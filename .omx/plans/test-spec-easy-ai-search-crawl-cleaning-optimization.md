# Test Spec: easy_ai_search 数据爬取与清洗流程优化

## Scope

本测试规范覆盖 3 个实现方向的新增和回归验证，目标是为 team 执行提供统一验收标准，并确保公共函数签名和核心行为不回退。

## Test Files To Add

- [`test_main_refactor.py`](/Users/lyx/Desktop/opensearch/my_ai_search/tests/test_main_refactor.py)
- [`test_fetch_optimization.py`](/Users/lyx/Desktop/opensearch/my_ai_search/tests/test_fetch_optimization.py)
- [`test_process_optimization.py`](/Users/lyx/Desktop/opensearch/my_ai_search/tests/test_process_optimization.py)

## Unit / Integration Coverage

### Track A: main.py + vector.py

1. shared result builders
   - 验证本地命中路径和无搜索结果路径由共享 helper 构建，输出字段与现状兼容。
   - 验证无 chunks / 无 vectors / 成功路径的统计字段正确。
2. cancellation
   - mock `fetch_page()` 使多个任务挂起。
   - 取消 `_pipeline_fetch_and_process()` 外层任务。
   - 断言剩余抓取任务被取消且不再继续处理。
3. TTL metadata
   - `store_documents()` 写入请求级元数据时包含 `expires_at` 等字段。
   - `cleanup_expired_documents()` 仅删除过期且标记为临时/请求级的文档。
   - 非临时文档不受影响。

### Track B: fetch.py + search.py + config.py

1. LightPanda session pool
   - mock WebSocket/CDP 客户端，验证多个 URL 抓取复用同一连接池。
   - 断言不再调用 `subprocess.run(["docker", "exec", ...])`。
   - 断言 `close_browser()` 会幂等关闭 pool，并允许重复调用。
2. search cache
   - 同 query + engines 第二次命中缓存，不再触发 `_call_searxng_api()`。
   - TTL 过期后重新调用 API。
   - engines 变化时 cache key 不共享。
   - 域名规则热加载后，若缓存的是原始 API 响应，则 parse 结果应立即体现新规则；若缓存 parse 后结果，则必须验证 config token/version 失效键生效。
3. pre-parsed fetch payload
   - `fetch_page()` 返回兼容字典，同时包含供 `process.py` 复用的预解析信息。
   - aiohttp / LightPanda / requests 三条路径都保持返回格式稳定。
   - 预解析信息必须是 plain-data，不得要求测试或调用方持有 `BeautifulSoup` 实例。
4. domain rules hot reload
   - 修改配置源后调用 `reload_config()` 或对应 facade。
   - 新规则在后续 `_should_block_result()` / 偏好排序中生效。
   - 验证所有域名规则消费点走统一 facade，而不是各自缓存旧规则。

### Track C: process.py + deep_process.py

1. readability concurrency
   - 用 `ThreadPoolExecutor` 并发调用 `clean_html()` / `process_content()`。
   - 断言无全局锁依赖、结果稳定、无异常。
2. duplicate detection complexity path
   - exact duplicate 仍正确识别。
   - near duplicate 在相同 URL 组内被识别。
   - 明显不同文本不误判。
   - 针对较大 chunk 集合，断言实现不走 O(n^2) pairwise thefuzz 路径。
3. concurrent summaries
   - mock `summarize_with_backend()` 为慢调用。
   - 断言并发度受 `max_concurrent_summaries` 控制。
   - 断言摘要结果仍按输入 chunk 对应写回。
   - 若从同步 API 进入，断言实现不会在已运行事件循环内直接嵌套 `asyncio.run`。
4. import hygiene
   - `Counter` 顶层导入后 `assess_quality()` 行为不变。

## Regression Coverage

执行新增测试前后，以下既有测试必须持续通过：

- [`test_fetch.py`](/Users/lyx/Desktop/opensearch/my_ai_search/tests/test_fetch.py)
- [`test_search.py`](/Users/lyx/Desktop/opensearch/my_ai_search/tests/test_search.py)
- [`test_process.py`](/Users/lyx/Desktop/opensearch/my_ai_search/tests/test_process.py)
- [`test_deep_process.py`](/Users/lyx/Desktop/opensearch/my_ai_search/tests/test_deep_process.py)
- 以及 `pytest my_ai_search/tests/ -q` 全量集合

## Verification Commands

```bash
pytest my_ai_search/tests/test_main_refactor.py -q
pytest my_ai_search/tests/test_fetch_optimization.py -q
pytest my_ai_search/tests/test_process_optimization.py -q
pytest my_ai_search/tests/ -q
ruff check my_ai_search/
wc -l my_ai_search/main.py
rg "docker exec lightpanda|lightpanda fetch" my_ai_search/fetch/fetch.py
rg "_READABILITY_LOCK" my_ai_search/process/process.py
```

## Pass / Fail Rules

- 任一新增测试失败，则对应 worker 不得交付。
- 全量 `pytest` 失败，则团队任务未完成。
- `ruff check` 出现新增错误，则团队任务未完成。
- `main.py >= 900`，则 Track A 未完成。
- 若 `fetch.py` 仍存在 per-URL `docker exec lightpanda lightpanda fetch` 实现，则 Track B 未完成。
- 若 `detect_duplicates()` 仍做同组内 pairwise thefuzz 两两比较，则 Track C 未完成。
