"""
Модели базы данных для GitLab Assistant
"""

from datetime import datetime
from typing import Optional

from sqlalchemy import String, Integer, BigInteger, Boolean, DateTime, Text, ForeignKey
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    """Базовый класс"""
    pass


class User(Base):
    """Модель пользователя Telegram"""

    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    telegram_id: Mapped[int] = mapped_column(BigInteger, unique=True, nullable=False, index=True)
    username: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    first_name: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    last_name: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)

    # Токены доступа к GitLab/GitHub
    gitlab_token: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    github_token: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)

    # ID в GitLab/GitHub
    gitlab_username: Mapped[Optional[str]] = mapped_column(String(255), nullable=True, index=True)
    github_username: Mapped[Optional[str]] = mapped_column(String(255), nullable=True, index=True)

    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False
    )

    # Связи
    subscriptions: Mapped[list["Subscription"]] = relationship(
        "Subscription", back_populates="user", cascade="all, delete-orphan", lazy="selectin"
    )
    notifications: Mapped[list["Notification"]] = relationship(
        "Notification", back_populates="user", cascade="all, delete-orphan", lazy="selectin"
    )


class Subscription(Base):
    """Модель подписки на события в репозиториях"""

    __tablename__ = "subscriptions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("users.telegram_id"), nullable=False)

    # GitLab или GitHub
    platform: Mapped[str] = mapped_column(String(50), nullable=False)

    # ID проекта или репозитория
    project_id: Mapped[str] = mapped_column(String(255), nullable=False)
    project_name: Mapped[str] = mapped_column(String(500), nullable=False)

    event_types: Mapped[str] = mapped_column(Text, nullable=False)

    # ID webhook в GitLab/GitHub
    webhook_id: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)

    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)

    # Связи
    user: Mapped["User"] = relationship("User", back_populates="subscriptions", lazy="selectin")


class Notification(Base):
    """Модель истории уведомлений"""

    __tablename__ = "notifications"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("users.telegram_id"), nullable=False)

    platform: Mapped[str] = mapped_column(String(50), nullable=False)
    event_type: Mapped[str] = mapped_column(String(100), nullable=False)
    project_name: Mapped[str] = mapped_column(String(500), nullable=False)

    message: Mapped[str] = mapped_column(Text, nullable=False)

    # ID сообщения и уведомения родительского
    telegram_message_id: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    parent_notification_id: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey("notifications.id"),
                                                                  nullable=True)
    # Дополнительные данные в JSON
    meta_data: Mapped[Optional[str]] = mapped_column("meta_data", Text, nullable=True)

    sent_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)

    # Связи
    user: Mapped["User"] = relationship("User", back_populates="notifications", lazy="selectin")
    parent: Mapped[Optional["Notification"]] = relationship("Notification", remote_side=[id], backref="replies")
