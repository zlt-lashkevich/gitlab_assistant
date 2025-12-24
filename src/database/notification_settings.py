"""
Модель настроек уведомлений пользователя
"""

from datetime import datetime
from typing import Optional

from sqlalchemy import String, Integer, BigInteger, Boolean, DateTime, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.database.models import Base


class NotificationSettings(Base):
    """Модель настроек уведомлений для пользователя"""

    __tablename__ = "notification_settings"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("users.telegram_id"), unique=True, nullable=False)

    # упоминания
    mentions_enabled: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)


    # Общие настройки
    general_updates_enabled: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    # GitLab/GitHub Merge Request / Pull Request
    reviewer_assignment_enabled: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    merge_enabled: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    # GitLab Pipeline
    pipeline_completion_enabled: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    # Issue/Note
    issue_assignment_enabled: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    issue_mention_enabled: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    note_mention_enabled: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    # изменение лейблов в связанных Issue
    label_changes_enabled: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    # новые комментарии в тредах
    thread_updates_enabled: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False
    )

    # Связь с пользователем
    # user: Mapped["User"] = relationship("User", back_populates="settings", lazy="selectin")
    user: Mapped["User"] = relationship("User", backref="notification_settings")