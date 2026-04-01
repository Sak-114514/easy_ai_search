# easy_ai_search

本地优先的 AI 搜索引擎。先从本地向量数据库查找，本地结果不足时再联网搜索、抓取网页、存入向量库。

---

## 快速开始

### 方式 A：一键部署（推荐交付/演示）

```bash
bash deployment/scripts/deploy.sh
```

脚本会自动：
- 创建 `data/` 运行目录
- 首次从 `.env.example` 生成 `.env`
- 启动 `searxng`、`lightpanda`、`api`
- 检查本地健康状态

部署完成后：
- 管理台：`http://127.0.0.1:8000/admin/`
- API 文档：`http://127.0.0.1:8000/docs`
- MCP JSON-RPC：`http://127.0.0.1:8000/mcp/jsonrpc`

### 方式 B：本地开发启动

### 1. 安装依赖 & 启动外部服务

```bash
pip install -r requirements.txt
pip install -r requirements-api.txt
docker compose up -d searxng lightpanda
```

### 2. 启动服务

```bash
bash start.sh api
```

启动完成后，以下所有使用方式均可用：

| 方式 | 地址/命令 | 用途 |
|------|-----------|------|
| Web 界面 | http://localhost:8000/admin/ | 浏览器交互搜索 |
| REST API | `POST http://localhost:8000/api/v1/search` | 类 OpenAI 风格的 HTTP 调用 |
| MCP 协议 | `http://localhost:8000/mcp/` | 接入 Claude / LLM 工具调用 |
| 命令行 | `bash start.sh search "查询词"` | 终端直接搜索（不走 API） |
| API 文档 | http://localhost:8000/docs | Swagger 自动交互文档 |

### 3. 停止服务

```bash
bash start.sh stop
```

### 发布前自检

```bash
bash deployment/scripts/release_check.sh
```

详细交付说明见：
- [docs/RELEASE_GUIDE.md](/Users/lyx/Desktop/opensearch/docs/RELEASE_GUIDE.md)
- [docs/AGENT_INTEGRATION.md](/Users/lyx/Desktop/opensearch/docs/AGENT_INTEGRATION.md)

---

## 使用方式一：REST API（类 OpenAI 风格）

API 服务运行后，任何语言都可以通过 HTTP 调用搜索。跟调 OpenAI API 一样简单：

### curl 示例

```bash
curl -X POST http://localhost:8000/api/v1/search \
  -H "X-API-Key: YOUR_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{"query": "Python异步编程", "max_results": 5}'
```

### Python 示例

```python
import requests

resp = requests.post(
    "http://localhost:8000/api/v1/search",
    headers={"X-API-Key": "YOUR_API_KEY"},
    json={
        "query": "Python异步编程",
        "max_results": 5,
        "skip_local": False,      # True = 强制联网
        "engines": "bing,baidu",  # 可选，指定搜索引擎
    },
)
data = resp.json()
for r in data["results"]:
    print(f"{r['title']}: {r['url']}")
```

### 搜索请求参数

| 参数 | 类型 | 默认 | 说明 |
|------|------|------|------|
| `query` | string | **必填** | 搜索查询 |
| `max_results` | int | 5 | 最大结果数（1-20） |
| `use_cache` | bool | true | 使用网页 HTML 缓存 |
| `skip_local` | bool | false | 跳过本地向量库，强制联网 |
| `disable_deep_process` | bool | false | 禁用深度处理，直接输出原始分块 |
| `engines` | string | null | 指定引擎，逗号分隔：`bing,baidu,sogou,360search,google,mojeek,presearch,mwmbl` |

### 其他 API 端点

```
GET  /api/v1/config/                    查看配置
PUT  /api/v1/config/                    修改配置（需管理员 Key）
GET  /api/v1/algorithms/                查看算法参数
PUT  /api/v1/algorithms/                修改算法参数
GET  /api/v1/vector/stats               向量库统计
GET  /api/v1/vector/documents?page=1    向量库文档列表
GET  /api/v1/vector/documents/{id}      读取单条文档
POST /api/v1/vector/documents/manual    手动录入并向量化
PUT  /api/v1/vector/documents/{id}      更新文档
DELETE /api/v1/vector/documents         删除文档
DELETE /api/v1/vector/collection        清空向量库
GET  /api/v1/cache/stats                缓存统计
DELETE /api/v1/cache/                   清空缓存
GET  /api/v1/logs/search?page=1         搜索日志
GET  /api/v1/logs/stats                 日志统计
```

### 认证

API 密钥通过 `.env` 中的 `API_KEYS_JSON` 配置，首次部署时请在 `.env` 中设置自己的密钥：

```env
API_KEYS_JSON='{"admin":"your-secure-admin-key","default":"your-readonly-key"}'
```

| 角色 | 权限 |
|------|------|
| `default` | 只读（搜索、查看统计） |
| `admin` | 全部（修改配置、清空缓存等） |

管理控制台打开后需在页面顶部输入 API Key（浏览器会自动记忆）。

---

## 使用方式二：MCP 协议（接入 Claude/LLM）

API 服务运行后，MCP 端点自动可用。可以让 Claude 等 LLM 直接调用搜索。

注意：
- MCP 端点现在也需要 `X-API-Key`
- 推荐为不同调用方单独生成动态 token，而不是长期共享默认静态 key
- `MCP`、`REST`、管理控制台的调用都会记到对应 token 名下，便于后续审计和限流

### MCP 工具列表

| 工具名 | 功能 |
|--------|------|
| `search` | AI 搜索（本地优先 + 联网） |
| `vector_query` | 向量库语义查询 |
| `cache_stats` | 缓存统计 |
| `vector_stats` | 向量库统计 |
| `clear_cache` | 清空缓存 |
| `clear_vector_db` | 清空向量库 |

### MCP 端点

```
GET  /mcp/capabilities      能力声明
GET  /mcp/tools             列出所有工具
POST /mcp/tools/call        调用工具
POST /mcp/jsonrpc           JSON-RPC 2.0 端点
POST /mcp/sse               Server-Sent Events 流式
GET  /mcp/resources          列出资源
GET  /mcp/prompts            列出提示词
```

### 在 Claude Desktop 中配置

在 Claude Desktop 的 `claude_desktop_config.json` 中添加：

```json
{
  "mcpServers": {
    "opensearch": {
      "url": "http://localhost:8000/mcp/jsonrpc"
    }
  }
}
```

说明：
- `opencode`/通用 JSON-RPC 客户端优先推荐 `POST /mcp/jsonrpc`
- 如需兼容旧式流式客户端，再考虑 `SSE`
- `opencode`、`OpenClaw` 这类 Agent 的完整接入方式见：
  [docs/AGENT_INTEGRATION.md](/Users/lyx/Desktop/opensearch/docs/AGENT_INTEGRATION.md)

### 手动调用示例

```bash
# 列出可用工具
curl http://localhost:8000/mcp/tools \
  -H "X-API-Key: YOUR_API_KEY"

# 调用搜索工具
curl -X POST http://localhost:8000/mcp/tools/call \
  -H "X-API-Key: YOUR_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{"name": "search", "arguments": {"query": "transformer是什么", "max_results": 3}}'
```

---

## 使用方式三：命令行

不经过 API Server，直接调用核心搜索库（需要外部服务 SearXNG/LightPanda 在运行）：

```bash
bash start.sh search "Python异步编程"
bash start.sh search "transformer是什么" --max-results 3
bash start.sh search "深度学习" --format json
```

---

## 使用方式四：Web 界面

访问 http://localhost:8000/admin/，首次使用需在页面顶部输入你的 API Key。

| 页面 | 功能 |
|------|------|
| 搜索 | 输入查询词，选择搜索引擎，查看结果 |
| 配置 | 修改参数，选择嵌入模型，保存后重启生效 |
| 算法配置 | 调整文本切分、质量过滤、去重参数 |
| 缓存 | 查看命中率，清空网页缓存 |
| 向量库 | 查看、搜索、手动录入、编辑、删除文档 |
| 日志 | 查看历史搜索记录和统计 |

---

## 配置

所有配置在 `.env` 文件中，修改后重启生效。首次部署可直接从 `.env.example` 复制：

```bash
cp .env.example .env
```

### 关键配置项

| 配置项 | 默认值 | 说明 |
|--------|--------|------|
| `API_KEYS_JSON` | 自动生成随机 admin key | API 密钥（JSON 格式，如 `{"admin":"xxx"}`） |
| `JWT_SECRET` | 自动生成随机值 | JWT 签名密钥 |
| `CORS_ORIGINS` | `http://localhost:8000` | 允许的跨域来源，逗号分隔 |
| `TRANSFORMERS_OFFLINE` | `1` | 禁止联网下载模型（推荐保持 1） |
| `SEARXNG_API_URL` | `http://127.0.0.1:8080/search` | SearXNG 地址 |
| `SEARXNG_TIMEOUT` | `15.0` | SearXNG 搜索超时（秒） |
| `SEARXNG_MAX_RESULTS` | `5` | 每次联网搜索返回的网页数 |
| `CHROMA_EMBEDDING_MODEL` | `sentence-transformers/all-MiniLM-L6-v2` | 嵌入模型名或本地路径 |
| `CHROMA_EMBEDDING_MODEL_PATH` | 空 | 本地嵌入模型目录（可选，优先于模型名） |
| `CHROMA_PERSIST_DIR` | `data/chroma_db` | 向量库数据目录 |
| `CACHE_PERSIST_DIR` | `data/chroma_db_cache` | 网页缓存向量库目录 |
| `DEEP_SUMMARY_BACKEND` | `lmstudio`/`extractive` | 深度摘要后端 |
| `DEEP_SUMMARY_API_URL` | `http://127.0.0.1:1234` | 本地摘要服务地址 |
| `DEEP_SUMMARY_MODEL` | `google/gemma-3-1b` | 本地摘要模型标识 |
| `OPENSEARCH_DATA_DIR` | `./data` | 统一运行数据目录 |
| `API_PORT` | `8000` | 服务端口 |

### 嵌入模型

系统自动从以下位置查找本地模型，无需手动配置路径：
- `~/.cache/huggingface/hub/`（HuggingFace 缓存）
- `~/.cache/modelscope/hub/`（魔搭缓存）

**通过魔搭下载新模型**（无需 VPN）：
```bash
pip install modelscope
python3 -c "from modelscope import snapshot_download; snapshot_download('sentence-transformers/all-MiniLM-L6-v2')"
```

也可以直接在 `.env` 中指定本地路径：
```
CHROMA_EMBEDDING_MODEL=/Users/xxx/.cache/modelscope/hub/sentence-transformers/all-MiniLM-L6-v2
```

或在 Web 界面 → **配置** → **ChromaDB 向量库** → **嵌入模型** 中选择预设或填写路径。

### 摘要模型与后端切换

摘要只作用于 `deep_process`，不会影响普通全文输出。

可选后端：

- `extractive`
- `lmstudio`

常用配置项：

```env
DEEP_SUMMARY_BACKEND=lmstudio
DEEP_SUMMARY_API_URL=http://127.0.0.1:1234
DEEP_SUMMARY_MODEL=google/gemma-3-1b
```

切换方式：

1. `.env` 修改后重启
2. Web 界面 → **配置** → **深度处理**
3. `PUT /api/v1/config/` 更新 `deep_process` section

建议：

- 工具模式默认关闭深摘要：`disable_deep_process=true`
- 日常本地摘要优先用小模型
- 切大模型前先确认超时和吞吐

---

## 常见问题

**Q: 页面一直显示"加载中"**
→ 确保用 `bash start.sh api` 启动（自动设置 `TRANSFORMERS_OFFLINE=1` 禁止联网下载模型）

**Q: 联网搜索总是返回本地结果**
→ 本地有高相似度结果（≥75%）时跳过联网。勾选"跳过本地搜索"可强制联网

**Q: 搜索超时**
→ 调大 `.env` 中的 `SEARXNG_TIMEOUT`，或在 SearXNG 容器中减少启用引擎数量

**Q: 更换嵌入模型后报错**
→ 更换模型后向量维度不兼容，需在向量库页面清空后重新搜索建库

---

## 架构

```
my_ai_search/   核心搜索库（搜索→抓取→处理→向量存储→检索）
api_server/     FastAPI 服务（REST API + MCP 协议 + 静态文件托管）
admin_ui/       Web 管理界面（3 个静态文件，无需构建）
```

## 二次开发

推荐先看：

- [docs/DEVELOPER_GUIDE.md](/Users/lyx/Desktop/opensearch/docs/DEVELOPER_GUIDE.md)
- [docs/AGENT_INTEGRATION.md](/Users/lyx/Desktop/opensearch/docs/AGENT_INTEGRATION.md)
- [docs/RELEASE_GUIDE.md](/Users/lyx/Desktop/opensearch/docs/RELEASE_GUIDE.md)

覆盖内容包括：

- 嵌入模型 / 摘要模型如何切换
- 前端、REST、MCP 参数映射
- 搜索主流程扩展点
- 新增 `source_profile` / 新增搜索策略的接入步骤

## 交付建议

推送 GitHub 前建议确认：

1. `.env` 未被提交
2. `data/`、`logs/`、`chroma_db/`、`chroma_db_cache/` 未被提交
3. `bash deployment/scripts/release_check.sh` 已通过
4. `.env.example` 可以覆盖新用户首次启动所需的默认配置

外部服务依赖（Docker）：
- **SearXNG**（端口 8080）：元搜索引擎
- **LightPanda**（端口 9222）：无头浏览器

```
opensearch/
├── .env                    # 环境配置
├── start.sh                # 统一启动脚本
├── requirements.txt        # Python 依赖
├── docker-compose.yml      # Docker 服务编排
├── my_ai_search/           # 核心搜索库
│   ├── main.py             #   search_ai() 主入口
│   ├── config.py           #   配置管理
│   ├── search/             #   SearXNG 搜索
│   ├── fetch/              #   网页抓取（aiohttp + LightPanda）
│   ├── process/            #   文本切分
│   ├── deep_process/       #   质量过滤 / 去重 / 摘要
│   ├── vector/             #   ChromaDB 向量操作
│   └── cache/              #   网页缓存
├── api_server/             # API 服务
│   ├── main.py             #   FastAPI 入口
│   ├── endpoints/          #   路由（search, config, vector, cache, logs, mcp）
│   ├── services/           #   业务逻辑
│   ├── models/             #   请求/响应模型
│   └── middleware/         #   认证 / 日志 / 限流
├── admin_ui/               # Web 界面（纯静态）
│   ├── index.html
│   ├── style.css
│   └── app.js
├── chroma_db/              # 向量库数据（自动生成）
├── logs/                   # 日志（自动生成）
└── data/                   # SQLite 日志库（自动生成）
```
