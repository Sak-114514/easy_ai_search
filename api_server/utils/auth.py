"""
认证工具
"""

import bcrypt
import secrets


def generate_api_key(length: int = 32) -> str:
    return secrets.token_urlsafe(length)


def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()


def verify_password(password: str, hashed: str) -> bool:
    return bcrypt.checkpw(password.encode(), hashed.encode())
