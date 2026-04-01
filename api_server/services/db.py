import sqlite3


class SQLiteDatabase:
    def __init__(self, database_url: str):
        self.db_path = database_url.replace("sqlite:///", "", 1)

    def connect(self) -> sqlite3.Connection:
        return sqlite3.connect(self.db_path)
