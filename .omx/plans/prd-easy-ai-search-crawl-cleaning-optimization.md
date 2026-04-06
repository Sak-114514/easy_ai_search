# PRD: easy_ai_search 数据爬取与清洗流程优化

## Requirements Summary

目标是在不改变公共 API 签名的前提下，优化本地 AI 搜索引擎的抓取、清洗和深度处理流水线，拆分为 3 条可并行执行的独立工作流：

- A. 重构 [`main.py`](/Users/lyx/Desktop/opensearch/my_ai_search/main.py) 的同步/异步搜索主线，抽取复用结果构建逻辑，补充取消响应和请求级向量 TTL 清理。
- B. 优化 [`fetch.py`](/Users/lyx/Desktop/opensearch/my_ai_search/fetch/fetch.py) 与 [`search.py`](/Users/lyx/Desktop/opensearch/my_ai_search/search/search.py)，用 LightPanda CDP 会话池替代逐次 `docker exec`，为 SearXNG 增加 TTL/LRU 缓存，避免重复 BeautifulSoup 解析，并将域名偏好配置外置且可热加载。
- C. 优化 [`process.py`](/Users/lyx/Desktop/opensearch/my_ai_search/process/process.py) 与 [`deep_process.py`](/Users/lyx/Desktop/opensearch/my_ai_search/deep_process/deep_process.py)，移除 readability 串行锁，降低去重复杂度，支持并行摘要调用，并清理导入副作用。

## RALPLAN-DR Summary

### Principles

1. 先保兼容，再做提速：所有公共函数签名和返回结构保持不变。
2. 优先抽共享边界，不做横向大重写：每个方向只引入解决当前问题所需的最小新抽象。
3. 先让性能热点可验证，再谈“优化完成”：每个方向都要落到可测试的行为指标或结构性证据。
4. 复用现有配置与刷新机制：优先用 [`config.py`](/Users/lyx/Desktop/opensearch/my_ai_search/config.py) 的 `get_config()` / `reload_config()`，避免平行配置系统。
5. 无新增依赖默认成立：除非执行阶段证明无法用标准库或现有依赖完成，否则不引入新包。

### Decision Drivers

1. 最大化收益来自消除已确认的结构性重复和 per-request/per-URL 启动开销。
2. 变更面虽跨 7 个核心模块，但三条工作流边界清晰，适合 team 并行。
3. 用户验收是硬门槛，不是建议：`pytest`, `ruff`, `main.py < 900`, 无签名变更。

### Viable Options

#### Option 1: 最小侵入的模块内重构 + 局部辅助类型/工具函数

Approach:
在现有模块内抽取共用 helper、缓存对象和轻量会话池，尽量不改变调用方结构。

Pros:
- 最符合当前代码组织，回归风险低。
- 最容易保持现有签名和返回格式。
- 便于 3 个 worker 并行，冲突少。

Cons:
- `main.py` 仍会保留一定 orchestration 复杂度。
- `fetch.py` 内部会增加会话池状态管理，需严格测试关闭/异常路径。
- B/C 共享“预解析结果”边界若定义含糊，容易让两个 worker 在同一契约上冲突。

#### Option 2: 引入新的 pipeline/service 子模块做完整分层重组

Approach:
把 main/fetch/search/process 的核心逻辑拆到新模块，再让现有入口调用新 service。

Pros:
- 架构更整齐，长期可维护性更高。
- 更容易继续拆分更多策略层与 provider 层。

Cons:
- 当前任务不是架构升级，而是定向优化；拆分范围过大。
- 与 `main.py < 900` 目标相符，但对现有测试和 import 路径扰动更大。
- 会放大并行协作的整合成本。

#### Option 3: 仅做性能补丁，不处理主线重复与配置外置

Approach:
只替换 LightPanda 调用、加搜索缓存、改去重算法，不整理主线重复代码。

Pros:
- 单次改动更快。
- 早期性能收益立刻可见。

Cons:
- 无法满足用户对 `main.py` 行数和重复消除的明确验收。
- 继续保留 sync/async 分叉，后续维护成本高。

### Chosen Direction

采用 Option 1，并吸收 Option 2 的少量结构化手法：
- 在原模块内抽 helper / state holder / config facade。
- 仅在必要处新增轻量内部对象或新配置文件。
- 不做跨层大搬迁。

## Acceptance Criteria

1. [`search_ai()`](/Users/lyx/Desktop/opensearch/my_ai_search/main.py#L1016) 与 [`search_ai_async()`](/Users/lyx/Desktop/opensearch/my_ai_search/main.py#L1233) 签名不变，sync/async 重复结果构建逻辑被提取为共享 helper。
2. [`my_ai_search/main.py`](/Users/lyx/Desktop/opensearch/my_ai_search/main.py) 行数降到 900 以下。
3. [`_pipeline_fetch_and_process()`](/Users/lyx/Desktop/opensearch/my_ai_search/main.py#L49) 能在任务取消时传播 `asyncio.CancelledError`，停止剩余抓取/处理任务并清理执行器。
4. [`store_documents()`](/Users/lyx/Desktop/opensearch/my_ai_search/vector/vector.py#L150) 能为请求级在线搜索写入过期元数据；新增 `cleanup_expired_documents()` 可删除过期文档且不影响长期向量数据。
5. [`fetch_page()`](/Users/lyx/Desktop/opensearch/my_ai_search/fetch/fetch.py#L60) 仍保持原有返回字段，但内部不再为每个 URL 调用 `docker exec lightpanda lightpanda fetch`。
6. SearXNG 查询结果在 [`search.py`](/Users/lyx/Desktop/opensearch/my_ai_search/search/search.py) 中有基于 `query + engines` 的 TTL/LRU 缓存，默认 TTL 300 秒，可通过配置修改。
7. 抓取层向处理层传递可复用的解析结果或预处理文本，避免同一 HTML 在 `fetch.py` 与 `process.py` 中重复完整解析。
8. 域名偏好/屏蔽列表从 [`search.py`](/Users/lyx/Desktop/opensearch/my_ai_search/search/search.py#L13) 迁出到配置侧，支持热加载。
9. [`process.py`](/Users/lyx/Desktop/opensearch/my_ai_search/process/process.py#L56) 的全局 readability 锁被移除，并有并发回归测试证明稳定。
10. [`detect_duplicates()`](/Users/lyx/Desktop/opensearch/my_ai_search/deep_process/deep_process.py#L471) 对近似重复判定不再做 O(n^2) pairwise thefuzz 比较；`dedup_threshold` 接口保持不变。
11. LLM 摘要调用改为受 `max_concurrent_summaries` 控制的并发执行，默认值为 3。
12. `pytest my_ai_search/tests/ -q` 通过，`ruff check my_ai_search/` 无新增错误。

## Implementation Steps

### Track A: main.py 主线去重 + 取消 + TTL

1. 在 [`main.py`](/Users/lyx/Desktop/opensearch/my_ai_search/main.py) 内抽取共享结果装配函数：
   - `_build_result_from_local()`
   - `_build_result_empty()`
   - `_build_result_from_pipeline()`
   目标是覆盖当前 async 路径 [`main.py:790-1013`](/Users/lyx/Desktop/opensearch/my_ai_search/main.py#L790) 与 sync 路径 [`main.py:1016-1231`](/Users/lyx/Desktop/opensearch/my_ai_search/main.py#L1016) 中本地命中、无搜索结果、无 chunks、无 vectors、成功路径的重复 builder 赋值。
2. 将 sync/async 分歧压缩到“阶段执行方式”而非“结果构造方式”：
   - 保留 `_run_local_search_phase` / `_run_local_search_phase_sync`
   - 保留 `_run_online_search_phase` / `_run_online_search_phase_sync`
   - 统一后续 builder 组装。
3. 在 [`_pipeline_fetch_and_process()`](/Users/lyx/Desktop/opensearch/my_ai_search/main.py#L49) 中：
   - 对 `asyncio.gather(*tasks)` 和 `_fetch_and_process()` 内部增加 `CancelledError` 捕获。
   - 取消剩余子任务，设置 `stop_fetching`，关闭 `ThreadPoolExecutor`。
4. 在 [`vector.py`](/Users/lyx/Desktop/opensearch/my_ai_search/vector/vector.py#L150) 中为请求级向量加 TTL 元数据：
   - 统一元数据键，例如 `expires_at`, `ttl_seconds`, `search_request_id`, `ephemeral`.
   - 新增 `cleanup_expired_documents(now: Optional[float] = None)`，按 metadata 删除过期文档。
5. 在 [`main.py`](/Users/lyx/Desktop/opensearch/my_ai_search/main.py#L601) 与 [`main.py`](/Users/lyx/Desktop/opensearch/my_ai_search/main.py#L751) 的在线请求级存储路径写入 TTL 元数据，并在合适入口触发轻量、限额的 best-effort 清理，避免每次搜索全量扫描向量库。

### Track B: 抓取与搜索性能

1. 在 [`fetch.py`](/Users/lyx/Desktop/opensearch/my_ai_search/fetch/fetch.py#L360) 用 CDP WebSocket 会话池替换 `_fetch_with_lightpanda_cli()`：
   - 优先新增内部 `LightPandaSessionPool`，基于 `config.lightpanda.cdp_url`。
   - 优先复用现有 `aiohttp` 的 WebSocket 客户端能力实现 CDP 连接，避免新增依赖。
   - 复用浏览器上下文和连接，不再逐 URL `docker exec`。
   - 保留现有三级回退顺序：aiohttp → LightPanda → requests。
   - `close_browser()` 需要从兼容空实现升级为幂等的 pool shutdown 钩子。
   - 会话池限定为抓取层内部 async 资源，避免把连接对象泄漏到 sync 包装层或测试调用方。
2. 将抓取阶段的解析副产品结构化：
   - 在 `fetch_page()` 返回 dict 中附加兼容性的可选字段，例如 `parsed_title`, `preview_text`, `main_text_candidate` 或 `parsed_document`.
   - 不移除现有 `url/html/title/success/error/duration`。
   - 明确跨 worker 契约：优先传递“轻量可复用文本/结构化摘要字段”，不要在返回值中暴露 `BeautifulSoup` 实例本体，避免缓存、线程和测试替身复杂度。
   - 让 [`process_content()`](/Users/lyx/Desktop/opensearch/my_ai_search/process/process.py#L125) 通过新增可选内部参数或消费 fetch result 中的结构化字段直接复用，避免重复 soup 全解析。
3. 在 [`search.py`](/Users/lyx/Desktop/opensearch/my_ai_search/search/search.py#L154) 之前增加查询缓存层：
   - key: `normalized(query) + engines`
   - value: 优先缓存原始 SearXNG JSON，而不是已按域名规则过滤后的 parse 结果
   - eviction: LRU
   - expiry: TTL 300 秒，配置可调。
   - 若缓存层必须缓存 parse 后结果，则 key 必须包含域名规则版本 / config token，避免热加载后命中陈旧结果。
4. 把 [`search.py:13-66`](/Users/lyx/Desktop/opensearch/my_ai_search/search/search.py#L13) 的域名列表迁移到配置层：
   - 首选在 [`config.py`](/Users/lyx/Desktop/opensearch/my_ai_search/config.py) 新增 `SearchConfig`，并由 JSON sidecar 承载域名规则；不选 YAML，避免引入新依赖或双配置源。
   - 热加载复用 [`reload_config()`](/Users/lyx/Desktop/opensearch/my_ai_search/config.py#L234) 或配置文件 mtime 检查，避免常驻进程重启。
   - 规则读取需要集中到单一 facade，禁止 `_should_block_result()`、优先域名打分和 source-profile 逻辑各自持有私有副本。

### Track C: 文本清洗与深度处理

1. 从 [`process.py`](/Users/lyx/Desktop/opensearch/my_ai_search/process/process.py#L56) 删除 `_READABILITY_LOCK`，直接调用 `_extract_with_readability()`。
2. 补并发回归测试，证明多线程场景下 `clean_html()` / `process_content()` 不会因 readability 崩溃或串行化。
3. 在 [`deep_process.py`](/Users/lyx/Desktop/opensearch/my_ai_search/deep_process/deep_process.py#L471) 用 simhash 风格签名 + 分桶近邻比较替代 `thefuzz` 的 pairwise 比较：
   - 先保留精确 hash 去重。
   - 对近似重复，按 URL 分组后计算指纹，基于桶或排序窗口筛候选。
   - `dedup_threshold` 仍作为相似度门槛，对外不改接口。
4. 把摘要并行化：
   - 保持 [`deep_process_page()`](/Users/lyx/Desktop/opensearch/my_ai_search/deep_process/deep_process.py#L13) 与 [`deep_process_content()`](/Users/lyx/Desktop/opensearch/my_ai_search/deep_process/deep_process.py#L104) 签名不变。
   - 内部新增 async batch helper，配合 `asyncio.gather` 和 `max_concurrent_summaries` 限流。
   - 对同步调用点保留兼容包装，但不得在已运行事件循环内直接嵌套 `asyncio.run`；需要定义安全的 sync bridge。
5. 把 [`Counter`](/Users/lyx/Desktop/opensearch/my_ai_search/deep_process/deep_process.py#L418) 提升到文件顶部导入，消除函数内 side effect。

## Risks And Mitigations

### Risk 1: CDP 会话池与 LightPanda 实际协议细节不一致

Mitigation:
- 先围绕 `ws://127.0.0.1:9222` 做最小可用适配层。
- 单元测试中 mock WebSocket 层，不依赖真实浏览器。
- 保留 `requests` 兜底，不让抓取路径被新实现卡死。

### Risk 2: `main.py` 抽 helper 后仍无法降到 900 行

Mitigation:
- 优先删除重复 builder 逻辑和重复日志/统计赋值块。
- 若仍超标，只允许把纯内部 helper 搬到邻近模块，不做跨层 service 化。

### Risk 3: 并行摘要引入事件循环/同步入口兼容问题

Mitigation:
- 明确把“并行摘要执行器”封装在内部 helper。
- 对同步入口使用安全的 sync bridge，避免在已有 loop 内再起 loop。
- 为“在运行中的 loop 调用同步 deep_process API”增加单元测试或明确保护分支。

### Risk 4: 近似去重替换后结果语义发生偏差

Mitigation:
- 保留精确 hash 去重作为第一层。
- 近似去重新增对照测试，覆盖 exact duplicate、near duplicate、non-duplicate。
- 在阈值语义上做向后兼容映射，避免用户已有配置失效。

### Risk 5: 配置热加载带来缓存一致性问题

Mitigation:
- 把域名规则读取集中到单一 facade。
- 使用 cache token / 文件 mtime 作为失效键，禁止多处各自缓存。

### Risk 6: B/C 两个 worker 围绕预解析字段发生接口漂移

Mitigation:
- 在实施前先锁定 fetch→process 的共享契约，只允许追加轻量、可选、plain-data 字段。
- 将该契约写入测试规范，并由 Worker 1 / Worker 2 共用同一组断言。

## Verification Steps

1. 定向测试：
   - `pytest my_ai_search/tests/test_main_refactor.py -q`
   - `pytest my_ai_search/tests/test_fetch_optimization.py -q`
   - `pytest my_ai_search/tests/test_process_optimization.py -q`
2. 全量回归：
   - `pytest my_ai_search/tests/ -q`
3. 静态检查：
   - `ruff check my_ai_search/`
4. 结构性验收：
   - `wc -l my_ai_search/main.py` 应小于 900。
   - `rg "docker exec lightpanda|lightpanda fetch" my_ai_search/fetch/fetch.py` 不应再命中逐 URL 子进程实现。
   - `rg "_READABILITY_LOCK|from collections import Counter" my_ai_search/process/process.py my_ai_search/deep_process/deep_process.py` 应只剩顶层导入且无锁定义。
5. 行为性验收：
   - 请求取消时，`_pipeline_fetch_and_process()` 能停止未完成任务。
   - 在线请求级向量文档过期后，`cleanup_expired_documents()` 能删除。
   - 重复 HTML 解析减少，处理层可复用抓取层提供的预解析信息。

## Architect Review

### Strongest Antithesis

最强反对意见是：当前任务把“性能优化”和“结构重构”绑在一起，容易把 3 条独立线又重新耦合起来，尤其 Track B 的“fetch 返回预解析对象”如果设计过重，会反向侵入 Track C；同时，CDP 会话池、搜索缓存和同步包装三者都引入状态管理，若缓存的是 parse 后结果、或池资源与 event loop 绑定不清，会让所谓的“最小侵入”退化成多个隐性生命周期 bug。

### Tradeoff Tension

- 更强的结构化抽象 vs 更低的回归风险。
- 共享预解析结果 vs 保持 `fetch_page()` 返回格式稳定。
- 在不加依赖前提下实现 simhash/CDP 池 vs 开发复杂度上升。
- 缓存 parse 后结果的简单实现 vs 域名规则热加载后的正确性。
- `asyncio.gather` 并发摘要的吞吐收益 vs sync API 对运行中事件循环的兼容成本。

### Synthesis

按“内部增强、外部兼容”收敛：
- `fetch_page()` 只增加可选字段，不改变既有字段。
- Track C 消费这些字段时做 best-effort，不建立强耦合。
- 预解析字段限定为 plain-data 契约，不传 `BeautifulSoup` 实例。
- 搜索缓存默认缓存原始 API 响应，让域名规则热加载在 parse 阶段立即生效。
- `close_browser()` 负责幂等关闭 CDP pool；摘要并发通过内部 async helper + 安全 sync bridge 落地，不扩散 API。

## Critic Evaluation

Verdict: APPROVE

Reasons:
- 方案覆盖了全部显式验收项。
- 每条工作流都有明确文件边界和验证出口。
- 风险和缓解与当前代码现状对应，不是泛化表述。

Required Improvements Applied:
- 明确了 `main.py < 900` 的结构性验收步骤。
- 明确了 `fetch_page()` 只能新增可选字段，不能破坏返回格式。
- 明确要求去重先做 exact-hash，再做近似候选筛选。
- 明确搜索缓存优先缓存原始 API 响应，避免热加载规则被缓存冻结。
- 明确 `close_browser()` 要接管 session pool 生命周期，且预解析载荷只能是 plain-data。

## ADR

### Decision

采用“最小侵入的模块内重构 + 定向性能优化 + 可验证回归测试”的方案，由 3 个 executor worker 按 A/B/C 并行实现。

### Drivers

- 用户给出的 3 个方向天然可并行，且修改边界明确。
- 现有代码存在真实热点和重复，优先修这些比做大规模重构更稳。
- 验收标准以兼容性和测试通过为主，不鼓励架构翻新。

### Alternatives Considered

- 完整 service 化重构：长期更整洁，但当前风险过高。
- 只做性能补丁不清理主线：无法满足 `main.py` 降行数和重复消除要求。

### Why Chosen

该方案在满足用户全部硬约束的同时，把冲突面压到最低，适合 team 模式的 3 worker 独立推进并最终整合。

### Consequences

- 会产生少量新的内部 helper / state holder。
- `fetch.py` 和 `search.py` 的内部状态管理会变复杂，需要测试兜住。
- 将来若继续演进，可在此基础上再抽 service 层，而不是一步到位。

### Follow-ups

- 若 CDP 池稳定，可后续再扩展为常驻 browser manager。
- 若域名规则继续增长，再考虑独立 schema / 校验器。
- 若摘要并行引入更多 provider，再评估统一 async provider 接口。

## Available-Agent-Types Roster

- `executor`: 负责实现与重构，适合 A/B/C 三条主线。
- `test-engineer`: 负责补测试、验证边界和回归风险。
- `verifier`: 负责最终汇总验证、运行全量测试和结构性验收。
- `architect`: 仅在某条线出现边界争议时做只读诊断。
- `debugger`: 仅在新实现导致回归或并发问题时介入。

## Follow-up Staffing Guidance

### Team Path

- Preflight contract:
  - Worker 1 与 Worker 2 先锁定 `fetch -> process` 共享字段名与 plain-data 结构，再并行编码，避免接口漂移。
- Worker 0: `executor`, reasoning `high`
  - Ownership: [`main.py`](/Users/lyx/Desktop/opensearch/my_ai_search/main.py), [`vector.py`](/Users/lyx/Desktop/opensearch/my_ai_search/vector/vector.py), [`test_main_refactor.py`](/Users/lyx/Desktop/opensearch/my_ai_search/tests/test_main_refactor.py)
  - Focus: 结果构建 helper、取消传播、TTL 元数据与清理。
- Worker 1: `executor`, reasoning `high`
  - Ownership: [`fetch.py`](/Users/lyx/Desktop/opensearch/my_ai_search/fetch/fetch.py), [`search.py`](/Users/lyx/Desktop/opensearch/my_ai_search/search/search.py), [`config.py`](/Users/lyx/Desktop/opensearch/my_ai_search/config.py), [`test_fetch_optimization.py`](/Users/lyx/Desktop/opensearch/my_ai_search/tests/test_fetch_optimization.py)
  - Focus: CDP 会话池、搜索缓存、域名规则热加载、抓取层预解析复用。
- Worker 2: `executor`, reasoning `high`
  - Ownership: [`process.py`](/Users/lyx/Desktop/opensearch/my_ai_search/process/process.py), [`deep_process.py`](/Users/lyx/Desktop/opensearch/my_ai_search/deep_process/deep_process.py), [`test_process_optimization.py`](/Users/lyx/Desktop/opensearch/my_ai_search/tests/test_process_optimization.py)
  - Focus: 移除 readability 锁、近似去重降复杂度、并行摘要。
- Shared closeout:
  - `test-engineer`, reasoning `medium`: 整理新增测试与全量回归。
  - `verifier`, reasoning `high`: 运行最终 `pytest`, `ruff`, `wc -l`, `rg` 结构检查。

### Ralph Path

- 单 owner `executor` 先按 A → B → C 顺序推进。
- 在完成每个方向后插入 `test-engineer` 验证，再进入下一方向。
- 最终交给 `verifier` 做全量收口。

## Launch Hints

### `$team` Hint

```text
$team "Implement .omx/plans/prd-easy-ai-search-crawl-cleaning-optimization.md with 3 executor lanes:
Worker 0 owns main.py + vector.py + test_main_refactor.py (Track A),
Worker 1 owns fetch.py + search.py + config.py + test_fetch_optimization.py (Track B),
Worker 2 owns process.py + deep_process.py + test_process_optimization.py (Track C).
Preserve public signatures. Finish with pytest my_ai_search/tests/ -q, ruff check my_ai_search/, wc -l my_ai_search/main.py, and structural grep checks." 
```

### `omx team` Hint

```text
omx team run --plan .omx/plans/prd-easy-ai-search-crawl-cleaning-optimization.md
```

## Team Verification Path

1. Each worker proves its own targeted tests pass.
2. Team lead integrates all lanes without reverting unrelated changes.
3. Shared verification lane runs:
   - `pytest my_ai_search/tests/ -q`
   - `ruff check my_ai_search/`
   - `wc -l my_ai_search/main.py`
   - structural `rg` checks for removed CLI spawning / removed readability lock.
4. If any gate fails, return to the owning lane only; do not reopen all three lanes.

## Applied Improvements Changelog

- Added explicit constraint that `fetch_page()` may only grow optional fields.
- Added structural acceptance proof for `main.py < 900` and LightPanda CLI removal.
- Added exact-hash-first rule before approximate dedup buckets.
