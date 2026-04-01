#!/bin/bash
# 发布前自检：文档、环境模板、测试、容器配置、健康检查提示

set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$ROOT_DIR"

echo "[1/6] 检查关键文件..."
for file in README.md .env.example .gitignore docker-compose.yml start.sh deployment/docker/Dockerfile.api deployment/scripts/deploy.sh; do
  if [ ! -f "$file" ]; then
    echo "ERROR: 缺少文件 $file"
    exit 1
  fi
done

echo "[2/6] 检查敏感配置是否被忽略..."
if ! grep -q '^\.env$' .gitignore; then
  echo "ERROR: .gitignore 未忽略 .env"
  exit 1
fi

echo "[3/7] 检查是否已有运行产物被 Git 跟踪..."
TRACKED_RUNTIME="$(git ls-files | rg '(^data/|^logs/|^chroma_db/|^chroma_db_cache/|__pycache__/|\.pyc$|^\.env$)' || true)"
if [ -n "$TRACKED_RUNTIME" ]; then
  echo "ERROR: 以下运行文件仍被 Git 跟踪，不建议直接发布："
  echo "$TRACKED_RUNTIME"
  exit 1
fi

echo "[4/7] 运行核心测试..."
pytest -q my_ai_search/tests/test_search.py api_server/tests/test_mcp_tools.py api_server/tests/test_api_integration.py -k 'search or mcp'

echo "[5/7] 检查 Docker Compose 语法..."
docker compose config >/dev/null

echo "[6/7] 提示工作树状态..."
git status --short

echo "[7/7] 发布建议"
echo "- 确认 .env 未加入 git"
echo "- 确认 data/ logs/ chroma_db/ chroma_db_cache/ 未加入 git"
echo "- 如需正式部署，执行: bash deployment/scripts/deploy.sh"
echo "- 如需边缘反向代理，执行: docker compose --profile edge up -d nginx"
