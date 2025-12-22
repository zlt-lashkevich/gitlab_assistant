"""
Модель настроек уведомлений пользователя
"""

from datetime import datetime
from typing import Optional

from sqlalchemy import String, Integer, BigInteger, Boolean, DateTime, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.database.models import Base


class NotificationSettings(Base):
    """Настройки уведомлений пользователя"""

    __tablename__ = "notification_settings"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("users.telegram_id"), nullable=False, unique=True)

    # упоминания
    mentions_enabled: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    # назначение ревьюером
    reviewer_assignment_enabled: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    # завершение пайплайнов для своих MR
    pipeline_completion_enabled: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    # мердж своих MR
    merge_enabled: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    # назначение исполнителем Issue
    issue_assignment_enabled: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    # изменение лейблов в связанных Issue
    label_changes_enabled: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    # новые комментарии в тредах
    thread_updates_enabled: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False
    )

    # Связи
    user: Mapped["User"] = relationship("User", backref="notification_settings")
