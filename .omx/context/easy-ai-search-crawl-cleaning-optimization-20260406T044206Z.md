## Task Statement

优化 `easy_ai_search` 的数据爬取和清洗流程，覆盖 3 个独立方向：
- A: 重构 `my_ai_search/main.py` 主搜索主管线，消除 sync/async 重复、增加取消响应、为请求级向量写入 TTL 清理能力。
- B: 优化 `my_ai_search/fetch/fetch.py` 和 `my_ai_search/search/search.py`，去掉 LightPanda 每次 `docker exec` 的高开销、为 SearXNG 增加缓存、避免重复 HTML 解析、把域名偏好从源码迁出并支持热加载。
- C: 优化 `my_ai_search/process/process.py` 和 `my_ai_search/deep_process/deep_process.py`，移除 readability 串行锁、将去重复杂度从 O(n^2) 降到 O(n log n) 或更低、并行化 LLM 摘要、修复顶层导入位置。

## Desired Outcome

- 规划出可交付的 team 执行方案，按 3 个 executor worker 并行拆分方向 A/B/C。
- 保持公共函数签名不变：
  - `search_ai()`
  - `search_ai_async()`
  - `fetch_page()`
  - `assess_quality()`
  - `detect_duplicates()`
  - `dedup_chunks()`
  - `deep_process_page()`
- 最终实现阶段需要满足：
  - `pytest my_ai_search/tests/ -q` 全绿
  - `ruff check my_ai_search/` 无新增错误
  - `my_ai_search/main.py` 少于 900 行
  - LightPanda 路径不再对每个 URL spawn 子进程
  - `deep_process.py` 去重复杂度下降到 O(n log n) 或更低

## Known Facts / Evidence

- 目标文件当前行数：
  - `my_ai_search/main.py`: 1339 行
  - `my_ai_search/fetch/fetch.py`: 571 行
  - `my_ai_search/search/search.py`: 811 行
  - `my_ai_search/process/process.py`: 535 行
  - `my_ai_search/deep_process/deep_process.py`: 613 行
  - `my_ai_search/vector/vector.py`: 376 行

- 方向 A 事实：
  - `_pipeline_fetch_and_process()` 位于 `my_ai_search/main.py:49`
  - `_search_ai_impl()` 位于 `my_ai_search/main.py:790`
  - `search_ai()` 位于 `my_ai_search/main.py:1016`
  - `search_ai_async()` 位于 `my_ai_search/main.py:1233`
  - `store_documents()` 位于 `my_ai_search/vector/vector.py:150`
  - `search_request_id` 请求级向量写入逻辑位于 `my_ai_search/main.py:601-638` 和 `my_ai_search/main.py:751-786`
  - sync/async 搜索路径在本地命中、无搜索结果、无 chunks、无 vectors、成功路径上有明显重复结果构建逻辑。

- 方向 B 事实：
  - `fetch_page()` 位于 `my_ai_search/fetch/fetch.py:60`
  - LightPanda 当前使用 `_fetch_with_lightpanda_cli()`，通过 `docker exec lightpanda lightpanda fetch ...` 启动子进程，位于 `my_ai_search/fetch/fetch.py:360-470`
  - `BeautifulSoup` 至少在抓取层被调用于 `my_ai_search/fetch/fetch.py:204,269,310,418,505`
  - 域名偏好和屏蔽列表硬编码于 `my_ai_search/search/search.py:13-66`
  - `search()` 位于 `my_ai_search/search/search.py:67`
  - 当前没有 SearXNG 查询缓存层，`_call_searxng_api()` 每次直接请求 `requests.post()`，位于 `my_ai_search/search/search.py:154-196`
  - `config.py` 已有 `get_config()` / `reload_config()` 缓存与刷新机制，可作为热加载切入点。

- 方向 C 事实：
  - `_READABILITY_LOCK = threading.Lock()` 位于 `my_ai_search/process/process.py:56`
  - `clean_html()` 中用 `with _READABILITY_LOCK:` 包裹 `_extract_with_readability()`，位于 `my_ai_search/process/process.py:247-255`
  - `deep_process_page()` 位于 `my_ai_search/deep_process/deep_process.py:13`
  - `dedup_chunks()` 位于 `my_ai_search/deep_process/deep_process.py:78`
  - `deep_process_content()` 位于 `my_ai_search/deep_process/deep_process.py:104`
  - `assess_quality()` 位于 `my_ai_search/deep_process/deep_process.py:384`
  - `detect_duplicates()` 位于 `my_ai_search/deep_process/deep_process.py:471`
  - `deep_process.py` 当前依赖 `thefuzz.fuzz`，在同 URL 分组后做 pairwise 两两比较，仍是 O(n^2) 级。
  - `assess_quality()` 里存在 `from collections import Counter` 的函数内导入，位于 `my_ai_search/deep_process/deep_process.py:418`

## Constraints

- 当前用户明确要求使用 team 模式执行，3 个 executor worker，A/B/C 三条线互不冲突。
- 这是 `$ralplan` 规划回合，不应直接进入业务代码实现。
- 不能改变公共 API 签名。
- 需要给出测试补充策略，并规划新增测试文件：
  - `my_ai_search/tests/test_main_refactor.py`
  - `my_ai_search/tests/test_fetch_optimization.py`
  - `my_ai_search/tests/test_process_optimization.py`
- 不引入新依赖，除非后续执行阶段确认已有依赖可复用或用户重新授权。

## Unknowns / Open Questions

- 现有环境是否已包含可直接使用的 CDP/WebSocket 客户端依赖；如果没有，方向 B 需要优先探索“零新增依赖”的实现路径。
- `process.py` 与 `fetch.py` 之间共享“已解析 HTML 表示”的最小改动点，需要在执行阶段做接口兼容设计，避免破坏 `fetch_page()` 返回结构。
- simhash / MinHash 方案若不引入新依赖，需确认可接受的自实现复杂度与精度折中。
- 现有 pytest 套件中是否存在隐式网络依赖，团队执行时需要决定先跑定向测试还是全量回归。

## Likely Code Touchpoints

- `my_ai_search/main.py`
- `my_ai_search/vector/vector.py`
- `my_ai_search/fetch/fetch.py`
- `my_ai_search/search/search.py`
- `my_ai_search/config.py`
- `my_ai_search/process/process.py`
- `my_ai_search/deep_process/deep_process.py`
- `my_ai_search/tests/test_main_refactor.py`
- `my_ai_search/tests/test_fetch_optimization.py`
- `my_ai_search/tests/test_process_optimization.py`
- Existing regression suites under `my_ai_search/tests/`
