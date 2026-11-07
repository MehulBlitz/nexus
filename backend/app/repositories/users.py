"""Database access for users and credentials. Routes and services never build raw SQL."""

from __future__ import annotations

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.user import User


def get_user(session: Session, user_id: str) -> User | None:
    return session.get(User, user_id)


def get_user_by_email(session: Session, email: str) -> User | None:
    return session.scalar(select(User).where(User.email == email.strip().lower()))


def create_user(session: Session, *, email: str, password_hash: str, display_name: str) -> User:
    user = User(email=email.strip().lower(), password_hash=password_hash, display_name=display_name)
    session.add(user)
    session.flush()
    return user


def count_users(session: Session) -> int:
    return int(session.scalar(select(func.count()).select_from(User)) or 0)


def delete_user(session: Session, user: User) -> None:
    session.delete(user)
