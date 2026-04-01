from datetime import datetime
from typing import Dict, Optional

from ..config import get_api_config
from .db import SQLiteDatabase


class LogService:
    """日志服务类"""

    def __init__(self):
        self.config = get_api_config()
        self.db = SQLiteDatabase(self.config.database_url)
        self._init_db()

    def _connect(self):
        return self.db.connect()

    def _init_db(self) -> None:
        """初始化日志数据库"""
        conn = self._connect()
        cursor = conn.cursor()

        # 搜索日志表
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS search_logs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
                query TEXT NOT NULL,
                max_results INTEGER,
                source TEXT,
                total_time REAL,
                results_count INTEGER,
                client_type TEXT,
                ip TEXT,
                token_name TEXT
            )
        """)

        # API 日志表
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS api_logs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
                endpoint TEXT NOT NULL,
                method TEXT NOT NULL,
                status_code INTEGER,
                response_time REAL,
                client_type TEXT,
                ip TEXT,
                token_name TEXT
            )
        """)

        self._ensure_column(cursor, "search_logs", "token_name", "TEXT")
        self._ensure_column(cursor, "api_logs", "token_name", "TEXT")

        conn.commit()
        conn.close()

    def _ensure_column(self, cursor, table: str, column: str, definition: str) -> None:
        cursor.execute(f"PRAGMA table_info({table})")
        existing = {row[1] for row in cursor.fetchall()}
        if column not in existing:
            cursor.execute(f"ALTER TABLE {table} ADD COLUMN {column} {definition}")

    async def log_search(
        self,
        query: str,
        max_results: int,
        source: str,
        total_time: float,
        results_count: int,
        client_type: str,
        ip: str = None,
        token_name: str = None,
    ) -> None:
        """记录搜索日志"""
        conn = self._connect()
        cursor = conn.cursor()

        cursor.execute(
            """
            INSERT INTO search_logs
            (query, max_results, source, total_time, results_count, client_type, ip, token_name)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (query, max_results, source, total_time, results_count, client_type, ip, token_name),
        )

        conn.commit()
        conn.close()

    async def log_api(
        self,
        endpoint: str,
        method: str,
        status_code: int,
        response_time: float,
        client_type: str,
        ip: str = None,
        token_name: str = None,
    ) -> None:
        """记录 API 日志"""
        conn = self._connect()
        cursor = conn.cursor()

        cursor.execute(
            """
            INSERT INTO api_logs
            (endpoint, method, status_code, response_time, client_type, ip, token_name)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (endpoint, method, status_code, response_time, client_type, ip, token_name),
        )

        conn.commit()
        conn.close()

    def list_search_logs(
        self,
        start_time: Optional[datetime] = None,
        end_time: Optional[datetime] = None,
        query: Optional[str] = None,
        token_name: Optional[str] = None,
        page: int = 1,
        size: int = 20,
    ) -> Dict:
        """查询搜索日志"""
        conn = self._connect()
        cursor = conn.cursor()

        try:
            where_conditions = []
            params = []

            if start_time:
                where_conditions.append("timestamp >= ?")
                params.append(start_time.strftime("%Y-%m-%d %H:%M:%S"))

            if end_time:
                where_conditions.append("timestamp <= ?")
                params.append(end_time.strftime("%Y-%m-%d %H:%M:%S"))

            if query:
                where_conditions.append("query LIKE ?")
                params.append(f"%{query}%")
            if token_name:
                where_conditions.append("token_name = ?")
                params.append(token_name)

            where_clause = " AND ".join(where_conditions) if where_conditions else "1=1"

            cursor.execute(
                f"""
                SELECT COUNT(*) FROM search_logs WHERE {where_clause}
            """,
                params,
            )
            total = cursor.fetchone()[0]

            offset = (page - 1) * size
            cursor.execute(
                f"""
                SELECT * FROM search_logs 
                WHERE {where_clause}
                ORDER BY timestamp DESC
                LIMIT ? OFFSET ?
            """,
                params + [size, offset],
            )

            columns = [desc[0] for desc in cursor.description]
            logs = [dict(zip(columns, row)) for row in cursor.fetchall()]

            return {"total": total, "page": page, "size": size, "logs": logs}
        finally:
            conn.close()

    def list_api_logs(
        self,
        start_time: Optional[datetime] = None,
        end_time: Optional[datetime] = None,
        endpoint: Optional[str] = None,
        token_name: Optional[str] = None,
        page: int = 1,
        size: int = 20,
    ) -> Dict:
        """查询 API 日志"""
        conn = self._connect()
        cursor = conn.cursor()

        try:
            where_conditions = []
            params = []

            if start_time:
                where_conditions.append("timestamp >= ?")
                params.append(start_time.strftime("%Y-%m-%d %H:%M:%S"))

            if end_time:
                where_conditions.append("timestamp <= ?")
                params.append(end_time.strftime("%Y-%m-%d %H:%M:%S"))

            if endpoint:
                where_conditions.append("endpoint LIKE ?")
                params.append(f"%{endpoint}%")
            if token_name:
                where_conditions.append("token_name = ?")
                params.append(token_name)

            where_clause = " AND ".join(where_conditions) if where_conditions else "1=1"

            cursor.execute(
                f"""
                SELECT COUNT(*) FROM api_logs WHERE {where_clause}
            """,
                params,
            )
            total = cursor.fetchone()[0]

            offset = (page - 1) * size
            cursor.execute(
                f"""
                SELECT * FROM api_logs 
                WHERE {where_clause}
                ORDER BY timestamp DESC
                LIMIT ? OFFSET ?
            """,
                params + [size, offset],
            )

            columns = [desc[0] for desc in cursor.description]
            logs = [dict(zip(columns, row)) for row in cursor.fetchall()]

            return {"total": total, "page": page, "size": size, "logs": logs}
        finally:
            conn.close()

    def get_stats(self) -> Dict:
        """获取日志统计"""
        conn = self._connect()
        cursor = conn.cursor()

        try:
            cursor.execute("SELECT COUNT(*) FROM search_logs")
            total_search_logs = cursor.fetchone()[0]

            cursor.execute("SELECT COUNT(*) FROM api_logs")
            total_api_logs = cursor.fetchone()[0]

            cursor.execute("""
                SELECT source, COUNT(*) as count 
                FROM search_logs 
                GROUP BY source
            """)
            source_stats = dict(cursor.fetchall())

            cursor.execute("""
                SELECT AVG(total_time) as avg_time 
                FROM search_logs 
                WHERE total_time > 0
            """)
            avg_time = cursor.fetchone()[0] or 0

            cursor.execute("""
                SELECT COUNT(*) FROM search_logs 
                WHERE timestamp >= datetime('now', '-24 hours')
            """)
            last_24h_searches = cursor.fetchone()[0]

            return {
                "total_search_logs": total_search_logs,
                "total_api_logs": total_api_logs,
                "source_stats": source_stats,
                "avg_search_time": round(avg_time, 2),
                "last_24h_searches": last_24h_searches,
            }
        finally:
            conn.close()
