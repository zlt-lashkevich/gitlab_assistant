"""
Модуль для отправки уведомлений пользователям с поддержкой тредов
"""

import json
from typing import Dict, List, Any, Optional
from loguru import logger
from aiogram import Bot
from aiogram.exceptions import TelegramAPIError
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.database import Notification

# Хранит экземпляр бота
_bot_instance: Optional[Bot] = None


def set_bot_instance(bot: Bot):
    """Установка экземпляра бота"""
    global _bot_instance
    _bot_instance = bot


async def send_personalized_notifications(
        notifications: List[Dict[str, Any]],
        session: AsyncSession
) -> None:
    """
    Отправка персонализированных уведомлений с поддержкой тредов
    """
    if not _bot_instance:
        logger.error("Bot instance not set. Call set_bot_instance() first.")
        return

    for notif_data in notifications:
        try:
            user_id = notif_data["user_id"]
            message = notif_data["message"]
            platform = notif_data["platform"]
            event_type = notif_data["event_type"]
            project_name = notif_data["project_name"]
            metadata = notif_data.get("metadata", "{}")

            # Парсим метаданные
            meta = json.loads(metadata) if isinstance(metadata, str) else metadata

            # Определяем, нужно ли отвечать в треде
            reply_to_message_id = None
            parent_notification_id = None

            # Для комментариев ищем родительское уведомление
            if event_type == "note":
                noteable_id = meta.get("noteable_id")
                noteable_type = meta.get("noteable_type")

                if noteable_id and noteable_type:
                    result = await session.execute(
                        select(Notification).where(
                            Notification.user_id == user_id,
                            Notification.platform == platform,
                            Notification.project_name == project_name
                        ).order_by(Notification.sent_at.desc()).limit(10)
                    )
                    previous_notifications = result.scalars().all()

                    # Ищем предыдущее уведомление по этому MR/Issue
                    for prev_notif in previous_notifications:
                        if prev_notif.meta_data:
                            prev_meta = json.loads(prev_notif.meta_data)

                            # Проверяем, относится ли к тому же MR/Issue
                            if (prev_meta.get("noteable_id") == noteable_id or
                                    prev_meta.get("mr_iid") == meta.get("mr_iid") or
                                    prev_meta.get("issue_iid") == meta.get("issue_iid")):
                                reply_to_message_id = prev_notif.telegram_message_id
                                parent_notification_id = prev_notif.id
                                break

            # Отправляем сообщение
            try:
                sent_message = await _bot_instance.send_message(
                    chat_id=user_id,
                    text=message,
                    parse_mode="HTML",
                    reply_to_message_id=reply_to_message_id,
                    disable_web_page_preview=True
                )

                # Сохраняем в БД
                notification = Notification(
                    user_id=user_id,
                    platform=platform,
                    event_type=event_type,
                    project_name=project_name,
                    message=message,
                    telegram_message_id=sent_message.message_id,
                    parent_notification_id=parent_notification_id,
                    metadata=metadata if isinstance(metadata, str) else json.dumps(metadata)
                )

                session.add(notification)
                await session.commit()

                logger.info(f"Sent personalized notification to user {user_id}, event: {event_type}")

            except TelegramAPIError as e:
                logger.error(f"Failed to send message to user {user_id}: {e}")

                # Если не удалось ответить в треде, отправляем как обычное сообщение
                if reply_to_message_id:
                    try:
                        sent_message = await _bot_instance.send_message(
                            chat_id=user_id,
                            text=message,
                            parse_mode="HTML",
                            disable_web_page_preview=True
                        )

                        notification = Notification(
                            user_id=user_id,
                            platform=platform,
                            event_type=event_type,
                            project_name=project_name,
                            message=message,
                            telegram_message_id=sent_message.message_id,
                            metadata=metadata if isinstance(metadata, str) else json.dumps(metadata)
                        )

                        session.add(notification)
                        await session.commit()

                        logger.info(f"Sent notification without thread to user {user_id}")

                    except TelegramAPIError as e2:
                        logger.error(f"Failed to send message without thread to user {user_id}: {e2}")

        except Exception as e:
            logger.error(f"Error sending personalized notification: {e}")


async def send_notification(user_id: int, message: str, session: AsyncSession) -> None:
    """
    Отправка простого уведомления (для обратной совместимости)
    """
    if not _bot_instance:
        logger.error("Bot instance not set. Call set_bot_instance() first.")
        return

    try:
        await _bot_instance.send_message(
            chat_id=user_id,
            text=message,
            parse_mode="HTML",
            disable_web_page_preview=True
        )
        logger.info(f"Sent simple notification to user {user_id}")

    except TelegramAPIError as e:
        logger.error(f"Failed to send message to user {user_id}: {e}")
