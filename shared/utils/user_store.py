"""
Simple user store for local email-based signup/login.
Stores users in /etc/comidf/users.json with bcrypt-hashed passwords.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Dict, Optional
from passlib.hash import bcrypt_sha256 as hasher


USERS_FILE = Path("/etc/comidf/users.json")


def _ensure_dir():
    USERS_FILE.parent.mkdir(parents=True, exist_ok=True)


def load_users() -> Dict[str, Dict[str, str]]:
    if not USERS_FILE.exists():
        return {}
    try:
        data = json.loads(USERS_FILE.read_text())
        if isinstance(data, dict):
            return data
        return {}
    except Exception:
        return {}


def save_users(users: Dict[str, Dict[str, str]]) -> None:
    _ensure_dir()
    USERS_FILE.write_text(json.dumps(users, indent=2))


def get_user(email: str) -> Optional[Dict[str, str]]:
    email = email.strip().lower()
    users = load_users()
    return users.get(email)


def create_user(email: str, password: str, name: Optional[str] = None) -> bool:
    email = email.strip().lower()
    users = load_users()
    if email in users:
        return False
    # bcrypt_sha256 supports arbitrary length (pre-hash + bcrypt)
    hashed = hasher.hash(password)
    users[email] = {"password": hashed, "name": name or email}
    save_users(users)
    return True


def verify_user(email: str, password: str) -> bool:
    email = email.strip().lower()
    user = get_user(email)
    if not user:
        return False
    try:
        return hasher.verify(password, user.get("password", ""))
    except Exception:
        return False


