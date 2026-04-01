#!/bin/bash
# 一键部署脚本：准备数据目录、生成 .env、启动核心依赖并检查健康状态

set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$ROOT_DIR"

ENV_FILE="${OPENSEARCH_ENV_FILE:-$ROOT_DIR/.env}"
EXAMPLE_FILE="$ROOT_DIR/.env.example"

if ! command -v docker >/dev/null 2>&1; then
  echo "ERROR: Docker 未安装，请先安装 Docker Desktop 或 Docker Engine。"
  exit 1
fi

if ! docker compose version >/dev/null 2>&1; then
  echo "ERROR: 当前环境不支持 docker compose，请先安装 Compose 插件。"
  exit 1
fi

mkdir -p data data/logs

if [ ! -f "$ENV_FILE" ]; then
  cp "$EXAMPLE_FILE" "$ENV_FILE"
  echo "已生成默认配置: $ENV_FILE"
  echo "如需自定义摘要模型、API Key 或外部服务地址，请先编辑该文件后再重新执行。"
fi

echo "启动核心服务: searxng, lightpanda, api"
docker compose up -d searxng lightpanda api

echo "等待 API 健康检查..."
for i in $(seq 1 30); do
  if curl -fsS "http://127.0.0.1:8000/health" >/dev/null 2>&1; then
    echo "OpenSearch API 已可用: http://127.0.0.1:8000"
    echo "管理台: http://127.0.0.1:8000/admin/"
    echo "Swagger: http://127.0.0.1:8000/docs"
    exit 0
  fi
  sleep 2
done

echo "ERROR: API 在预期时间内未就绪，请执行 'docker compose logs api --tail=200' 排查。"
exit 1
