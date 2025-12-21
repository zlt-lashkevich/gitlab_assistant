"""
Обработчики команд настройки уведомлений
"""

from aiogram import Router, F
from aiogram.filters import Command
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from loguru import logger
from sqlalchemy import select

from src.database import get_session, User, NotificationSettings

router = Router()


def create_settings_keyboard(settings: NotificationSettings) -> InlineKeyboardMarkup:
    """
    Клавиатура с настройками уведомлений
    """

    def get_status(enabled: bool) -> str:
        return "👍" if enabled else "👎"

    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(
                text=f"{get_status(settings.mentions_enabled)} Упоминания",
                callback_data="toggle_mentions"
            )
        ],
        [
            InlineKeyboardButton(
                text=f"{get_status(settings.reviewer_assignment_enabled)} Назначение ревьюером",
                callback_data="toggle_reviewer_assignment"
            )
        ],
        [
            InlineKeyboardButton(
                text=f"{get_status(settings.pipeline_completion_enabled)} Завершение пайплайнов",
                callback_data="toggle_pipeline_completion"
            )
        ],
        [
            InlineKeyboardButton(
                text=f"{get_status(settings.merge_enabled)} Мердж MR",
                callback_data="toggle_merge"
            )
        ],
        [
            InlineKeyboardButton(
                text=f"{get_status(settings.issue_assignment_enabled)} Назначение исполнителем Issue",
                callback_data="toggle_issue_assignment"
            )
        ],
        [
            InlineKeyboardButton(
                text=f"{get_status(settings.label_changes_enabled)} Изменение лейблов",
                callback_data="toggle_label_changes"
            )
        ],
        [
            InlineKeyboardButton(
                text=f"{get_status(settings.thread_updates_enabled)} Обновления в тредах",
                callback_data="toggle_thread_updates"
            )
        ],
        [
            InlineKeyboardButton(
                text="👍 Включить все",
                callback_data="enable_all"
            ),
            InlineKeyboardButton(
                text="👎 Выключить все",
                callback_data="disable_all"
            )
        ],
        [
            InlineKeyboardButton(
                text="Закрыть",
                callback_data="close_settings"
            )
        ]
    ])

    return keyboard


@router.message(Command("notifications"))
async def cmd_notifications(message: Message):
    """Управление настройками уведомлений"""
    try:
        async for session in get_session():
            result = await session.execute(
                select(User).where(User.telegram_id == message.from_user.id)
            )
            user = result.scalar_one_or_none()

            if not user:
                await message.answer("Вы не зарегистрированы. Используйте /start")
                return

            settings_result = await session.execute(
                select(NotificationSettings).where(
                    NotificationSettings.user_id == user.telegram_id
                )
            )
            settings = settings_result.scalar_one_or_none()

            if not settings:
                settings = NotificationSettings(user_id=user.telegram_id)
                session.add(settings)
                await session.commit()

            # Сообщение с настройками
            text = (
                "**Настройки уведомлений**\n\n"
                "Выберите типы уведомлений, которые хотите получать:\n\n"
                "👍 - включено\n"
                "👎 - выключено\n\n"
                "Нажмите на кнопку, чтобы переключить настройку"
            )

            await message.answer(
                text,
                reply_markup=create_settings_keyboard(settings)
            )

    except Exception as e:
        logger.error(f"Error in cmd_notifications: {e}")
        await message.answer("Произошла ошибка при загрузке настроек")


@router.callback_query(F.data.startswith("toggle_"))
async def handle_toggle_setting(callback: CallbackQuery):
    """Переключение настройки"""
    try:
        setting_name = callback.data.replace("toggle_", "")

        async for session in get_session():
            result = await session.execute(
                select(NotificationSettings).where(
                    NotificationSettings.user_id == callback.from_user.id
                )
            )
            settings = result.scalar_one_or_none()

            if not settings:
                await callback.answer("Настройки не найдены", show_alert=True)
                return

            # Словарь переключений
            setting_map = {
                "mentions": "mentions_enabled",
                "reviewer_assignment": "reviewer_assignment_enabled",
                "pipeline_completion": "pipeline_completion_enabled",
                "merge": "merge_enabled",
                "issue_assignment": "issue_assignment_enabled",
                "label_changes": "label_changes_enabled",
                "thread_updates": "thread_updates_enabled"
            }

            attr_name = setting_map.get(setting_name)
            if attr_name:
                current_value = getattr(settings, attr_name)
                setattr(settings, attr_name, not current_value)
                await session.commit()

                # Обновляем клавиатуру после переключений
                await callback.message.edit_reply_markup(
                    reply_markup=create_settings_keyboard(settings)
                )

                status = "включено" if not current_value else "выключено"
                await callback.answer(f"Уведомление {status}")
            else:
                await callback.answer("Неизвестная настройка", show_alert=True)

    except Exception as e:
        logger.error(f"Error in handle_toggle_setting: {e}")
        await callback.answer("Произошла ошибка", show_alert=True)


@router.callback_query(F.data == "enable_all")
async def handle_enable_all(callback: CallbackQuery):
    """Включение всех уведомлений"""
    try:
        async for session in get_session():
            result = await session.execute(
                select(NotificationSettings).where(
                    NotificationSettings.user_id == callback.from_user.id
                )
            )
            settings = result.scalar_one_or_none()

            if not settings:
                await callback.answer("Настройки не найдены", show_alert=True)
                return

            # Все включаем
            settings.mentions_enabled = True
            settings.reviewer_assignment_enabled = True
            settings.pipeline_completion_enabled = True
            settings.merge_enabled = True
            settings.issue_assignment_enabled = True
            settings.label_changes_enabled = True
            settings.thread_updates_enabled = True

            await session.commit()

            await callback.message.edit_reply_markup(
                reply_markup=create_settings_keyboard(settings)
            )

            await callback.answer("Все уведомления включены")

    except Exception as e:
        logger.error(f"Error in handle_enable_all: {e}")
        await callback.answer("Произошла ошибка", show_alert=True)


@router.callback_query(F.data == "disable_all")
async def handle_disable_all(callback: CallbackQuery):
    """Выключение всех уведомлений"""
    try:
        async for session in get_session():
            result = await session.execute(
                select(NotificationSettings).where(
                    NotificationSettings.user_id == callback.from_user.id
                )
            )
            settings = result.scalar_one_or_none()

            if not settings:
                await callback.answer("Настройки не найдены", show_alert=True)
                return

            # Выключаем все
            settings.mentions_enabled = False
            settings.reviewer_assignment_enabled = False
            settings.pipeline_completion_enabled = False
            settings.merge_enabled = False
            settings.issue_assignment_enabled = False
            settings.label_changes_enabled = False
            settings.thread_updates_enabled = False

            await session.commit()

            await callback.message.edit_reply_markup(
                reply_markup=create_settings_keyboard(settings)
            )

            await callback.answer("Все уведомления выключены")

    except Exception as e:
        logger.error(f"Error in handle_disable_all: {e}")
        await callback.answer("Произошла ошибка", show_alert=True)


@router.callback_query(F.data == "close_settings")
async def handle_close_settings(callback: CallbackQuery):
    """Закрытие клавиатуры с настройками"""
    try:
        await callback.message.delete()
        await callback.answer()
    except Exception as e:
        logger.error(f"Error in handle_close_settings: {e}")
        await callback.answer("Произошла ошибка", show_alert=True)
