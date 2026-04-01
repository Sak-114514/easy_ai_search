"""
API Token 管理服务
"""

import hmac
from typing import Dict, List, Optional

from ..config import get_api_config
from ..utils.auth import generate_api_key
from .db import SQLiteDatabase


class TokenService:
    """动态 API Token 管理"""

    def __init__(self):
        self.config = get_api_config()
        self.db = SQLiteDatabase(self.config.database_url)
        self._init_db()

    def _connect(self):
        return self.db.connect()

    def _init_db(self):
        conn = self._connect()
        cursor = conn.cursor()
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS api_tokens (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL UNIQUE,
                api_key TEXT NOT NULL UNIQUE,
                role TEXT NOT NULL DEFAULT 'default',
                status TEXT NOT NULL DEFAULT 'active',
                notes TEXT,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                last_used_at DATETIME
            )
            """
        )
        conn.commit()
        conn.close()

    def resolve_api_key(self, api_key: str) -> Optional[Dict]:
        if not api_key:
            return None

        for name, value in (self.config.api_keys or {}).items():
            if hmac.compare_digest(api_key, value):
                return {
                    "name": name,
                    "role": "admin" if name == "admin" else "default",
                    "source": "static",
                    "api_key": api_key,
                    "api_key_prefix": api_key[:8],
                }

        conn = self._connect()
        cursor = conn.cursor()
        try:
            cursor.execute(
                """
                SELECT id, name, api_key, role, status, notes, created_at, last_used_at
                FROM api_tokens
                WHERE status = 'active'
                """
            )
            columns = [desc[0] for desc in cursor.description]
            for row in cursor.fetchall():
                data = dict(zip(columns, row))
                if hmac.compare_digest(api_key, data["api_key"]):
                    data["source"] = "dynamic"
                    data["api_key_prefix"] = api_key[:8]
                    return data
            return None
        finally:
            conn.close()

    def touch_usage(self, api_key: str):
        conn = self._connect()
        cursor = conn.cursor()
        try:
            cursor.execute(
                """
                UPDATE api_tokens
                SET last_used_at = CURRENT_TIMESTAMP
                WHERE api_key = ? AND status = 'active'
                """,
                (api_key,),
            )
            conn.commit()
        finally:
            conn.close()

    def list_tokens(self) -> List[Dict]:
        conn = self._connect()
        cursor = conn.cursor()
        try:
            cursor.execute(
                """
                SELECT id, name, role, status, notes, created_at, last_used_at
                FROM api_tokens
                ORDER BY created_at DESC
                """
            )
            tokens = []
            for row in cursor.fetchall():
                token = {
                    "id": row[0],
                    "name": row[1],
                    "role": row[2],
                    "status": row[3],
                    "notes": row[4] or "",
                    "created_at": row[5],
                    "last_used_at": row[6],
                }
                cursor.execute(
                    "SELECT COUNT(*) FROM search_logs WHERE token_name = ?",
                    (token["name"],),
                )
                token["search_calls"] = cursor.fetchone()[0]
                cursor.execute(
                    "SELECT COUNT(*) FROM api_logs WHERE token_name = ?",
                    (token["name"],),
                )
                token["api_calls"] = cursor.fetchone()[0]
                tokens.append(token)
            return tokens
        finally:
            conn.close()

    def create_token(self, name: str, role: str = "default", notes: str = "") -> Dict:
        api_key = generate_api_key(24)
        conn = self._connect()
        cursor = conn.cursor()
        try:
            cursor.execute(
                """
                INSERT INTO api_tokens (name, api_key, role, status, notes)
                VALUES (?, ?, ?, 'active', ?)
                """,
                (
                    name.strip(),
                    api_key,
                    role if role in {"default", "admin"} else "default",
                    notes.strip(),
                ),
            )
            conn.commit()
            token_id = cursor.lastrowid
            return {
                "id": token_id,
                "name": name.strip(),
                "role": role if role in {"default", "admin"} else "default",
                "status": "active",
                "notes": notes.strip(),
                "api_key": api_key,
            }
        finally:
            conn.close()

    def revoke_token(self, token_id: int) -> Dict:
        conn = self._connect()
        cursor = conn.cursor()
        try:
            cursor.execute(
                "UPDATE api_tokens SET status = 'revoked' WHERE id = ?",
                (token_id,),
            )
            conn.commit()
            if cursor.rowcount == 0:
                return {"success": False, "error": "Token not found"}
            return {"success": True}
        finally:
            conn.close()

    def get_token_usage(self, token_id: int) -> Dict:
        conn = self._connect()
        cursor = conn.cursor()
        try:
            cursor.execute("SELECT name FROM api_tokens WHERE id = ?", (token_id,))
            row = cursor.fetchone()
            if not row:
                return {"success": False, "error": "Token not found"}
            token_name = row[0]

            cursor.execute(
                """
                SELECT timestamp, query, source, total_time, results_count, client_type, ip
                FROM search_logs
                WHERE token_name = ?
                ORDER BY timestamp DESC
                LIMIT 20
                """,
                (token_name,),
            )
            search_logs = [
                {
                    "timestamp": item[0],
                    "query": item[1],
                    "source": item[2],
                    "total_time": item[3],
                    "results_count": item[4],
                    "client_type": item[5],
                    "ip": item[6],
                }
                for item in cursor.fetchall()
            ]

            cursor.execute(
                """
                SELECT timestamp, endpoint, method, status_code, response_time, client_type, ip
                FROM api_logs
                WHERE token_name = ?
                ORDER BY timestamp DESC
                LIMIT 20
                """,
                (token_name,),
            )
            api_logs = [
                {
                    "timestamp": item[0],
                    "endpoint": item[1],
                    "method": item[2],
                    "status_code": item[3],
                    "response_time": item[4],
                    "client_type": item[5],
                    "ip": item[6],
                }
                for item in cursor.fetchall()
            ]

            return {
                "success": True,
                "token_name": token_name,
                "search_logs": search_logs,
                "api_logs": api_logs,
            }
        finally:
            conn.close()
