#!/bin/bash
# 备份脚本

BACKUP_DIR="./backups"
TIMESTAMP=$(date +"%Y%m%d_%H%M%S")

echo "Creating backup..."

# 创建备份目录
mkdir -p "$BACKUP_DIR"

# 备份数据库
if [ -f "./data/logs.db" ]; then
    cp "./data/logs.db" "$BACKUP_DIR/logs_$TIMESTAMP.db"
    echo "Backed up logs.db"
fi

# 备份配置
if [ -f "./.env" ]; then
    cp "./.env" "$BACKUP_DIR/env_$TIMESTAMP"
    echo "Backed up .env"
fi

# 备份 ChromaDB（如果存在）
if [ -d "./chroma_db" ]; then
    tar -czf "$BACKUP_DIR/chroma_db_$TIMESTAMP.tar.gz" ./chroma_db
    echo "Backed up chroma_db"
fi

# 清理旧备份（保留最近7天）
find "$BACKUP_DIR" -name "*.tar.gz" -mtime +7 -delete
find "$BACKUP_DIR" -name "*.db" -mtime +7 -delete

echo "Backup completed: $TIMESTAMP"
