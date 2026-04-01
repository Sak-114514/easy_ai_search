# OpenSearch 二次开发指南

本文档面向准备继续扩展 OpenSearch 的开发者，重点覆盖：

- 嵌入模型与摘要模型如何切换
- 配置、前端、REST、MCP 的对应关系
- 搜索主流程的关键扩展点

## 1. 项目分层

### 核心搜索层

路径：`my_ai_search/`

职责：

- 在线搜索
- 网页抓取
- 正文提取
- 分块
- 候选过滤
- deep process 摘要
- 向量写入 / 检索

关键入口：

- `my_ai_search/main.py`
- `my_ai_search/search/search.py`
- `my_ai_search/process/process.py`
- `my_ai_search/deep_process/deep_process.py`
- `my_ai_search/deep_process/summary_provider.py`

### API / MCP 层

路径：`api_server/`

职责：

- 提供 REST API
- 提供 MCP JSON-RPC / 工具调用
- 托管管理前端
- 提供配置 / 算法 / 向量库 / 缓存管理接口

关键入口：

- `api_server/main.py`
- `api_server/endpoints/search.py`
- `api_server/services/search_service.py`
- `api_server/services/mcp_tool_handler.py`
- `api_server/services/config_service.py`

### 管理前端

路径：`admin_ui/`

职责：

- 搜索调试
- 配置修改
- 模型切换
- Token 管理与调用审计
- 算法参数调整
- 缓存 / 向量库 / 日志管理

关键入口：

- `admin_ui/index.html`
- `admin_ui/app.js`

## 2. 模型切换说明

### 2.1 嵌入模型

嵌入模型决定：

- 向量化质量
- 检索召回风格
- 本地推理开销

当前配置位置：

- `.env`: `CHROMA_EMBEDDING_MODEL`
- `.env`: `CHROMA_EMBEDDING_MODEL_PATH`
- REST 配置接口：`PUT /api/v1/config/` 的 `chroma` section
- 管理前端：`配置 -> ChromaDB 向量库 -> 嵌入模型`

相关代码：

- `my_ai_search/config.py`
- `api_server/services/config_service.py`
- `admin_ui/app.js`

推荐切换方式：

1. 开发/测试：直接在前端配置页切换
2. 自动化部署：修改 `.env`
3. 批量脚本：调用 `PUT /api/v1/config/`

注意：

- 切换嵌入模型后，向量维度可能变化
- 向量库旧数据通常需要清空并重建

### 2.2 摘要模型

摘要模型只影响 `deep_process`，不会影响普通 `process`。

当前支持：

- `extractive`
- `lmstudio` / OpenAI 兼容接口

当前配置位置：

- `.env`: `DEEP_SUMMARY_BACKEND`
- `.env`: `DEEP_SUMMARY_API_URL`
- `.env`: `DEEP_SUMMARY_MODEL`
- `.env`: `DEEP_SUMMARY_MODEL_PATH`
- REST 配置接口：`PUT /api/v1/config/` 的 `deep_process` section
- 管理前端：`配置 -> 深度处理 -> 摘要后端 / 摘要模型`

相关代码：

- `my_ai_search/deep_process/summary_provider.py`
- `my_ai_search/deep_process/deep_process.py`
- `api_server/services/config_service.py`

推荐实践：

1. 默认工具搜索：`disable_deep_process=true`
2. 高质量摘要：`summary_backend=lmstudio`
3. 本地小模型优先：例如 `google/gemma-3-1b`
4. 大模型只建议在离线分析或手工验收时使用

## 3. 前端、REST、MCP 参数映射

### 搜索模式

- 前端字段：`mode`
- REST 字段：`mode`
- MCP 字段：`request.mode`

可选值：

- `fast`
- `balanced`
- `deep`

### 来源策略

- 前端字段：`sourceProfile`
- REST 字段：`source_profile`
- MCP 字段：`request.source_profile`

可选值：

- `general`
- `official_news`
- `social_realtime`
- `official_plus_social`
- `tech_community`

### Token 与 MCP 认证

- 管理前端：
  - `Token` 页面用于创建、撤销、查看 token 使用情况
- REST：
  - 所有受保护接口依赖 `X-API-Key`
- MCP：
  - `/mcp/jsonrpc`
  - `/mcp/tools`
  - `/mcp/tools/call`
  - `/mcp/sse`
  现在同样要求 `X-API-Key`

动态 token 的实现位置：

- `api_server/services/token_service.py`
- `api_server/endpoints/tokens.py`
- `api_server/middleware/auth.py`
- `api_server/middleware/logging.py`

日志归属字段：

- 搜索日志：`search_logs.token_name`
- API 日志：`api_logs.token_name`

### 域名控制

- 前端字段：
  - `preferredDomainsText`
  - `blockedDomainsText`
  - `domainPreferenceMode`
- REST 字段：
  - `preferred_domains`
  - `blocked_domains`
  - `domain_preference_mode`
- MCP 字段：
  - `tool_context.preferred_domains`
  - `tool_context.blocked_domains`
  - `tool_context.domain_preference_mode`

## 4. 搜索主流程

当前主流程：

1. 本地向量库预检
2. 在线搜索候选 URL
3. 抓取页面
4. 正文抽取 / 模板清洗
5. 分块
6. 请求级候选过滤 / 去重
7. fast 模式内存重排 或 balanced/deep 模式向量检索
8. deep_process 候选增强
9. 返回结果

关键扩展点：

- 搜索候选重排：`my_ai_search/search/search.py`
- 抓取策略：`my_ai_search/fetch/fetch.py`
- 正文清洗：`my_ai_search/process/process.py`
- 摘要与质量：`my_ai_search/deep_process/deep_process.py`
- 请求级模式策略：`my_ai_search/main.py`

## 5. 新增来源策略 / 新增 profile 的方法

如需增加新的 `source_profile`：

1. 在 REST 请求模型中新增枚举
   - `api_server/models/requests.py`
2. 在 MCP schema 中新增枚举
   - `api_server/services/mcp_tool_handler.py`
3. 在搜索排序逻辑中实现 profile 评分
   - `my_ai_search/search/search.py`
4. 在前端增加对应选项/预设
   - `admin_ui/app.js`
5. 补测试
   - `my_ai_search/tests/test_search.py`
   - `api_server/tests/test_api_integration.py`
   - `api_server/tests/test_mcp_tools.py`

## 6. 推荐开发流程

### 修改配置/模型相关

1. 改 `.env.example`
2. 改 `ConfigService`
3. 改前端配置页
4. 补 `README` / 本文档
5. 跑测试

### 修改搜索策略

1. 改 `my_ai_search/search/search.py`
2. 改 `my_ai_search/main.py`（如果涉及主流程）
3. 补单元测试
4. 真实查询回打

## 7. 最小回归命令

```bash
pytest -q my_ai_search/tests/test_search.py api_server/tests/test_mcp_tools.py api_server/tests/test_api_integration.py -k 'search or mcp'
```

## 8. 二次开发建议

优先建议扩展：

1. 社交源独立抓取通道
2. 产品评测专门 profile
3. 多策略保存与共享
4. deep 模式成本控制

不建议一开始就重写：

1. 整条 API 层
2. MCP 协议层
3. 整个搜索主流程为 Rust
