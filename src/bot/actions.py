"""
Интерактивные действия с MR/Issue через inline-кнопки
"""

import json
from aiogram import Router, F
from aiogram.types import CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from loguru import logger
from sqlalchemy import select

from src.database import get_session, User
from src.gitlab_api import GitLabClient

router = Router()


def create_mr_action_keyboard(project_id: str, mr_iid: int) -> InlineKeyboardMarkup:
    """
    Создание клавиатуры с действиями для MR

    Args:
        project_id: ID проекта
        mr_iid: IID Merge Request

    Returns:
        Inline клавиатура
    """
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(
                text="Approve",
                callback_data=f"mr_approve:{project_id}:{mr_iid}"
            ),
            InlineKeyboardButton(
                text="Merge",
                callback_data=f"mr_merge:{project_id}:{mr_iid}"
            )
        ],
        [
            InlineKeyboardButton(
                text="Назначить ревьюера",
                callback_data=f"mr_assign_reviewer:{project_id}:{mr_iid}"
            )
        ],
        [
            InlineKeyboardButton(
                text="Перезапустить pipeline",
                callback_data=f"mr_restart_pipeline:{project_id}:{mr_iid}"
            )
        ]
    ])

    return keyboard


@router.callback_query(F.data.startswith("mr_approve:"))
async def handle_mr_approve(callback: CallbackQuery):
    """Обработка approve MR"""
    try:
        _, project_id, mr_iid = callback.data.split(":")

        async for session in get_session():
            result = await session.execute(
                select(User).where(User.telegram_id == callback.from_user.id)
            )
            user = result.scalar_one_or_none()

            if not user or not user.gitlab_token:
                await callback.answer("GitLab токен не настроен", show_alert=True)
                return

            # Создаем клиент GitLab
            client = GitLabClient(user.gitlab_token)

            try:
                # Approve MR
                await client.approve_merge_request(project_id, int(mr_iid))
                await callback.answer("MR успешно approve!", show_alert=True)
                await callback.message.edit_reply_markup(reply_markup=None)
                await callback.message.reply("Вы approve этот MR")

            except Exception as e:
                logger.error(f"Error approving MR: {e}")
                await callback.answer(f"Ошибка: {str(e)}", show_alert=True)

    except Exception as e:
        logger.error(f"Error in handle_mr_approve: {e}")
        await callback.answer("Произошла ошибка", show_alert=True)


@router.callback_query(F.data.startswith("mr_merge:"))
async def handle_mr_merge(callback: CallbackQuery):
    """Обработка merge MR"""
    try:
        _, project_id, mr_iid = callback.data.split(":")

        async for session in get_session():
            # Получаем пользователя
            result = await session.execute(
                select(User).where(User.telegram_id == callback.from_user.id)
            )
            user = result.scalar_one_or_none()

            if not user or not user.gitlab_token:
                await callback.answer("GitLab токен не настроен. Используйте /set_gitlab_token", show_alert=True)
                return

            # Создаем клиент GitLab
            client = GitLabClient(user.gitlab_token)

            try:
                # Merge MR
                result = await client.merge_merge_request(project_id, int(mr_iid))

                await callback.answer("MR успешно вмерджен!", show_alert=True)
                await callback.message.edit_reply_markup(reply_markup=None)
                await callback.message.reply("MR был вмерджен")

            except Exception as e:
                logger.error(f"Error merging MR: {e}")
                await callback.answer(f"Ошибка: {str(e)}", show_alert=True)

    except Exception as e:
        logger.error(f"Error in handle_mr_merge: {e}")
        await callback.answer("Произошла ошибка", show_alert=True)


@router.callback_query(F.data.startswith("mr_restart_pipeline:"))
async def handle_mr_restart_pipeline(callback: CallbackQuery):
    """Обработка перезапуска pipeline"""
    try:
        _, project_id, mr_iid = callback.data.split(":")

        async for session in get_session():
            result = await session.execute(
                select(User).where(User.telegram_id == callback.from_user.id)
            )
            user = result.scalar_one_or_none()

            if not user or not user.gitlab_token:
                await callback.answer("GitLab токен не настроен. Используйте /set_gitlab_token", show_alert=True)
                return

            # Создаем клиент GitLab
            client = GitLabClient(user.gitlab_token)

            try:
                # Получаем информацию о MR
                mr_info = await client.get_merge_request(project_id, int(mr_iid))

                if not mr_info:
                    await callback.answer("MR не найден", show_alert=True)
                    return

                # Получаем последний pipeline
                pipelines = await client.get_merge_request_pipelines(project_id, int(mr_iid))

                if not pipelines:
                    await callback.answer("Pipelines не найдены", show_alert=True)
                    return

                latest_pipeline = pipelines[0]
                pipeline_id = latest_pipeline.get("id")

                # Перезапускаем pipeline
                await client.retry_pipeline(project_id, pipeline_id)

                await callback.answer("Pipeline перезапущен!", show_alert=True)
                await callback.message.reply("Pipeline перезапускается...")

            except Exception as e:
                logger.error(f"Error restarting pipeline: {e}")
                await callback.answer(f"Ошибка: {str(e)}", show_alert=True)

    except Exception as e:
        logger.error(f"Error in handle_mr_restart_pipeline: {e}")
        await callback.answer("Произошла ошибка", show_alert=True)
