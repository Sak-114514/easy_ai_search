# easy_ai_search 抓取 / 清洗优化实施说明

本文档是 `.omx/plans/prd-easy-ai-search-crawl-cleaning-optimization.md` 的开发侧落地说明，目标是把多 worker 并行改造时必须保持一致的契约写清楚，避免实现漂移。

## 1. 不变约束

以下约束在 Track A / B / C 中都成立：

- 不修改公共 API 签名：
  - `search_ai()`
  - `search_ai_async()`
  - `fetch_page()`
  - `process_content()`
  - `deep_process_page()`
  - `deep_process_content()`
- 不新增第三方依赖，优先复用标准库、`aiohttp` 和现有配置刷新机制。
- `fetch_page()` 只能新增 **可选字段**，不能移除既有返回字段。
- `fetch -> process` 共享数据必须是 plain-data，不能把 `BeautifulSoup`、连接对象或其他带生命周期状态的实例跨层传递。
- 所有优化都必须保留现有回退链路，不能因为性能改造牺牲兜底可用性。

## 2. 并行分工边界

### Track A: `main.py` + `vector.py`

关注点：

- sync / async 搜索主线的重复结果组装收敛
- 抓取 / 处理阶段取消传播
- 请求级向量 TTL 元数据与过期清理

边界规则：

- builder helper 可以抽出，但调用侧返回结构必须与现有路径兼容。
- 在线请求级写入向量时，临时文档必须显式标注 `ephemeral`、`search_request_id`、`ttl_seconds`、`expires_at` 等元数据。
- 清理逻辑必须是 best-effort，不能阻塞主搜索路径。

### Track B: `fetch.py` + `search.py` + `config.py`

关注点：

- LightPanda CDP 会话池
- SearXNG TTL / LRU 缓存
- 域名规则配置化与热加载
- 抓取层向处理层暴露可复用的预解析信息

边界规则：

- `fetch_page()` 必须继续返回 `url/html/title/success/error/duration`。
- 预解析字段建议限制为：
  - `parsed_title`
  - `preview_text`
  - `main_text_candidate`
  - 其他等价的纯文本 / 纯字典字段
- 搜索缓存优先缓存原始 SearXNG 响应；如果缓存 parse 后结果，则 key 必须包含域名规则版本或配置 token。
- 域名偏好、屏蔽列表和 preference mode 必须通过单一配置 facade 读取，不能在多个函数里各自持有副本。

### Track C: `process.py` + `deep_process.py`

关注点：

- 移除 readability 全局串行锁
- 降低近似去重复杂度
- 摘要调用并发化
- 清理导入副作用

边界规则：

- 先做精确 hash 去重，再做近似重复候选筛选。
- `dedup_threshold` 语义保持兼容，不新增用户侧配置心智负担。
- 摘要并发 helper 必须受 `max_concurrent_summaries` 限流。
- 同步入口不能在已运行事件循环里直接嵌套 `asyncio.run()`。

## 3. fetch -> process 共享契约

抓取层和处理层之间只共享“轻量、可序列化、可测试”的辅助数据。

推荐契约：

```python
{
    "url": str,
    "html": str,
    "title": str,
    "success": bool,
    "error": str | None,
    "duration": float,
    # optional plain-data hints
    "parsed_title": str | None,
    "preview_text": str | None,
    "main_text_candidate": str | None,
}
```

约束说明：

- `process_content()` 对这些字段的消费必须是 best-effort；缺字段时仍能退回现有 HTML 解析路径。
- 不要把“预解析字段存在”变成处理层的强依赖。
- 单元测试必须覆盖 aiohttp、LightPanda、requests 三条抓取路径下的返回结构兼容性。

## 4. 搜索缓存与域名规则

### 4.1 缓存 key

建议至少包含：

- 归一化后的 query
- engines
- 与域名规则相关的配置版本信息（若缓存 parse 后结果）

### 4.2 热加载要求

- 修改配置源后，通过既有 `reload_config()` 或等价 facade 立即生效。
- `_should_block_result()`、偏好加分逻辑、source profile 域名约束必须共用同一规则来源。

### 4.3 不应出现的实现

- 每个调用点自己缓存一份 preferred / blocked domains
- 缓存 parse 后结果但不带配置失效键
- 把规则写死在多个 helper 中

## 5. 代码质量关注点

本轮优化的主要质量风险如下：

1. **隐式共享状态过多**
   - 会话池、缓存、配置热加载都引入状态，必须明确生命周期和失效策略。
2. **兼容性被性能优化破坏**
   - 外部签名、返回字段、fallback 顺序都属于兼容面。
3. **跨 worker 契约漂移**
   - Track B 只能追加 plain-data 字段，Track C 只能可选消费这些字段。
4. **同步 / 异步桥接失控**
   - 摘要并发与抓取取消都依赖正确的事件循环边界，不能在 sync 包装中偷用不安全桥接。

建议 reviewer 重点看：

- 新增 helper 是否真正减少重复，而不是换个位置保留重复逻辑
- 缓存 / pool 是否有明确 close / cleanup 路径
- 并发优化是否补了失败路径和取消路径测试
- 文档描述的契约是否与测试断言一致

## 6. 验证清单

实现合并前至少执行：

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

额外人工核对：

- `main.py` 行数 `< 900`
- `fetch_page()` 仍包含兼容返回字段
- `close_browser()` 可重复调用且不会泄漏会话池资源
- `cleanup_expired_documents()` 只清理请求级临时文档

## 7. 交接建议

如果后续继续扩展该流水线，优先遵循：

1. 先补测试，再动性能热点。
2. 先抽共享边界，再增加状态对象。
3. 先把配置读取集中，再做热加载。
4. 先保留 fallback，再尝试裁剪旧路径。
