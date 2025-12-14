from datetime import datetime
from typing import Optional

from sqlalchemy import String, BigInteger, Boolean, DateTime, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.database.models import Base


class NotificationSettings(Base):
    """Настройки уведомлений пользователя"""

    __tablename__ = "notification_settings"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("users.telegram_id"), nullable=False, unique=True)

    # О упоминаниях
    mentions_enabled: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    # О назначении ревьюером
    reviewer_assignment_enabled: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    # О завершении пайплайнов для своих MR
    pipeline_completion_enabled: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    # О мердже своих MR
    merge_enabled: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    # О назначении исполнителем Issue
    issue_assignment_enabled: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    # Об изменении лейблов в связанных Issue
    label_changes_enabled: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    # О новых комментариях в тредах
    thread_updates_enabled: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False
    )

    # Связи
    user: Mapped["User"] = relationship("User", backref="notification_settings")
