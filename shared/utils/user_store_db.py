"""
DB-backed user store with password policy validation
"""
from __future__ import annotations

import re
from typing import Optional
from sqlalchemy.orm import Session
from passlib.hash import bcrypt_sha256 as hasher

from shared.utils.db import engine, Base
from shared.models.auth_models import User


def init_db() -> None:
    Base.metadata.create_all(bind=engine)


def get_user(db: Session, email: str) -> Optional[User]:
    return db.query(User).filter(User.email == email.strip().lower()).one_or_none()


def password_is_strong(password: str) -> bool:
    if len(password) < 12:
        return False
    # Require at least 3 of the 4 classes: lower, upper, digit, special
    classes = 0
    classes += 1 if re.search(r"[a-z]", password) else 0
    classes += 1 if re.search(r"[A-Z]", password) else 0
    classes += 1 if re.search(r"\d", password) else 0
    classes += 1 if re.search(r"[^A-Za-z0-9]", password) else 0
    return classes >= 3


def create_user(db: Session, email: str, password: str, name: Optional[str] = None) -> bool:
    email_norm = email.strip().lower()
    if get_user(db, email_norm):
        return False
    if not password_is_strong(password):
        raise ValueError("Password does not meet strength policy")
    pwd_hash = hasher.hash(password)
    user = User(email=email_norm, name=name or email_norm, password_hash=pwd_hash, provider="local")
    db.add(user)
    db.commit()
    return True


def verify_user(db: Session, email: str, password: str) -> bool:
    user = get_user(db, email)
    if not user:
        return False
    try:
        return hasher.verify(password, user.password_hash)
    except Exception:
        return False


