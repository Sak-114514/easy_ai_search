# OpenSearch 交付指南

本文档面向第一次部署或准备发布到 GitHub 的维护者。

## 1. 交付前目标

发布前至少确认以下四点：

1. 仓库不包含本地敏感配置和运行数据
2. 新环境可以用一条命令拉起核心服务
3. 用户知道如何配置 `.env`
4. 有一条固定的发布前自检命令

## 2. 仓库中不应提交的内容

这些文件或目录应保持本地存在、但不进入 Git：

- `.env`
- `data/`
- `logs/`
- `chroma_db/`
- `chroma_db_cache/`
- `.venv/`
- `.pytest_cache/`
- `.ruff_cache/`

## 3. 新机器部署

### 推荐方式：Docker Compose

```bash
bash deployment/scripts/deploy.sh
```

脚本会自动：

- 创建 `data/` 与 `data/logs/`
- 如果 `.env` 不存在，则从 `.env.example` 生成
- 启动 `searxng`、`lightpanda`、`api`
- 检查 `http://127.0.0.1:8000/health`

部署成功后可访问：

- 管理台：`http://127.0.0.1:8000/admin/`
- Swagger：`http://127.0.0.1:8000/docs`
- REST：`http://127.0.0.1:8000/api/v1/search`
- MCP JSON-RPC：`http://127.0.0.1:8000/mcp/jsonrpc`

### 安全配置（必须）

部署后务必在 `.env` 中设置以下安全配置项：

```env
# API 密钥（JSON 格式）
API_KEYS_JSON='{"admin":"your-secure-admin-key","default":"your-readonly-key"}'

# JWT 签名密钥
JWT_SECRET=your-secure-jwt-secret

# 允许的跨域来源
CORS_ORIGINS=http://localhost:8000
```

不设置时系统会自动生成随机密钥并打印到控制台，但重启后密钥会变化。

### 可选：反向代理

```bash
docker compose --profile edge up -d nginx
```

## 4. 本地开发环境

```bash
pip install -r requirements.txt
pip install -r requirements-api.txt
bash start.sh api
```

如果要接 MCP / Agent：

```bash
pip install -r requirements-mcp.txt
```

## 5. 发布前自检

```bash
bash deployment/scripts/release_check.sh
```

它会检查：

- 关键文件是否存在
- `.env` 是否被 `.gitignore` 忽略
- 核心搜索/MCP 测试是否通过
- `docker compose config` 是否可解析
- 当前工作树状态

## 6. 推荐发布顺序

1. 清理本地 `.env` 中的个人配置
2. 确认运行数据目录没有被加入 Git
3. 跑一遍 `bash deployment/scripts/release_check.sh`
4. 补一次 `README.md` 中的示例与当前代码一致
5. 再推送到 GitHub
