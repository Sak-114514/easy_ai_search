#!/bin/bash
# easy_ai_search 统一启动脚本
# 用法: bash start.sh [api|search|stop|status]

set -e
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

# ── 加载 .env ──
ENV_FILE="${OPENSEARCH_ENV_FILE:-$SCRIPT_DIR/.env}"
if [ -f "$ENV_FILE" ]; then
    set -a
    source "$ENV_FILE"
    set +a
fi

# ── 选择 Python ──
# 按优先级查找：当前激活的 venv → anaconda → 系统
if command -v python3 &>/dev/null && python3 -c "import chromadb" 2>/dev/null; then
    PYTHON=python3
elif [ -x "/opt/anaconda3/bin/python3" ] && /opt/anaconda3/bin/python3 -c "import chromadb" 2>/dev/null; then
    PYTHON=/opt/anaconda3/bin/python3
else
    echo "ERROR: 找不到已安装依赖的 Python，请先运行: pip install -r requirements.txt"
    exit 1
fi

echo "使用 Python: $PYTHON ($($PYTHON --version))"

case "${1:-api}" in
  api)
    echo "启动 API Server (端口 $API_PORT)..."
    exec $PYTHON -m uvicorn api_server.main:app \
        --host "${API_HOST:-127.0.0.1}" \
        --port "${API_PORT:-8000}" \
        --log-level "$(echo "${LOG_LEVEL:-info}" | tr '[:upper:]' '[:lower:]')"
    ;;
  search)
    shift
    echo "运行命令行搜索..."
    exec $PYTHON -m my_ai_search.main "$@"
    ;;
  stop)
    PID=$(lsof -ti :"${API_PORT:-8000}" 2>/dev/null || true)
    if [ -n "$PID" ]; then
        kill -9 $PID && echo "已停止 PID $PID"
    else
        echo "服务未运行"
    fi
    ;;
  status)
    PID=$(lsof -ti :"${API_PORT:-8000}" 2>/dev/null || true)
    if [ -n "$PID" ]; then
        echo "服务运行中 PID=$PID，端口=${API_PORT:-8000}"
    else
        echo "服务未运行"
    fi
    ;;
  *)
    echo "用法: bash start.sh [api|search <query>|stop|status]"
    exit 1
    ;;
esac
