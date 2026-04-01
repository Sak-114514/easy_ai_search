# Agent 接入指南

本文档说明如何把当前服务接入 `opencode`、`OpenClaw` 这类 Agent。

## 1. 推荐接入方式

优先使用 `MCP JSON-RPC`：

- 地址：`http://127.0.0.1:8000/mcp/jsonrpc`
- 认证：请求头 `X-API-Key`

原因：

- 工具发现统一
- 支持 `tools/resources/prompts`
- 比直接包装单个 REST 接口更适合 Agent 工作流

如果目标 Agent 暂时不支持 MCP，再退回 REST：

- `POST /api/v1/search`

## 2. Token 最佳实践

不要让多个 Agent 共用默认静态 key。

建议：

1. 在管理控制台 `Token` 页面为每个 Agent 单独生成 token
2. 普通搜索 Agent 使用 `default`
3. 只有需要清缓存、清向量库、改配置的后台 Agent 才使用 `admin`

这样可以：

- 分用户审计调用
- 独立撤销某个 Agent
- 后续做限流和配额更方便

## 3. opencode 接入

配置示例：

```json
{
  "mcp": {
    "opensearch-local": {
      "type": "remote",
      "url": "http://127.0.0.1:8000/mcp/jsonrpc",
      "headers": {
        "X-API-Key": "your-agent-token"
      }
    }
  }
}
```

建议：

- 工具型搜索默认走 `mode=fast`
- 查询新闻时配 `source_profile=official_plus_social`
- 需要强约束来源时传：
  - `preferred_domains`
  - `blocked_domains`
  - `domain_preference_mode`

## 4. OpenClaw 接入

如果 OpenClaw 支持远程 MCP：

- 直接配置到 `http://127.0.0.1:8000/mcp/jsonrpc`
- 同样带 `X-API-Key`

如果 OpenClaw 当前只支持 HTTP tools：

- 用 `POST /api/v1/search` 包装成一个工具
- 请求体直接传结构化参数

示例：

```json
{
  "query": "Redis 持久化机制对比",
  "max_results": 3,
  "mode": "fast",
  "skip_local": true,
  "disable_deep_process": true,
  "source_profile": "tech_community",
  "preferred_domains": ["redis.io", "docs.python.org"],
  "blocked_domains": ["help.openai.com"],
  "domain_preference_mode": "prefer"
}
```

## 5. 推荐搜索参数

### 通用 Agent

```json
{
  "mode": "fast",
  "max_results": 3,
  "disable_deep_process": true
}
```

### 新闻 / 时效性

```json
{
  "mode": "fast",
  "source_profile": "official_plus_social",
  "disable_deep_process": true
}
```

### 技术问答

```json
{
  "mode": "fast",
  "source_profile": "tech_community",
  "disable_deep_process": true
}
```

### 深度分析

```json
{
  "mode": "deep",
  "disable_deep_process": false
}
```

注意：

- `deep` 模式质量上限更高，但明显更慢
- 给 Agent 当工具时，建议默认用 `fast`

## 6. 常见问题

### 1. MCP 为什么返回 401/403？

通常是：

- 没带 `X-API-Key`
- token 已撤销
- 普通 token 去访问管理员接口

### 2. Agent 为什么能搜但看不到统计？

`/api/v1/tokens` 和其他管理员能力需要 `admin` token。

### 3. 为什么 GLM / 云端模型没跑到工具调用？

如果日志里是模型供应商连接失败，那是模型侧网络问题，不是本地 MCP token 验证失败。

## 7. 相关文件

- [README](../README.md)
- [二次开发指南](DEVELOPER_GUIDE.md)
- `api_server/endpoints/mcp.py`
- `api_server/endpoints/tokens.py`
- `api_server/services/token_service.py`
