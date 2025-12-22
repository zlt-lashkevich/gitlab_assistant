"""
Тесты для обработчиков webhook событий.
"""

import pytest
from unittest.mock import AsyncMock, patch, MagicMock
from sqlalchemy.ext.asyncio import AsyncSession

from src.database import User, Subscription, NotificationSettings
from tests.mocks import MockUser, MockNotificationSettings, MockAsyncSession
from src.webhook.personalized_handlers import (
    handle_gitlab_note,
    handle_gitlab_merge_request,
    handle_gitlab_pipeline,
    handle_gitlab_issue
)
from src.webhook.handlers import handle_gitlab_event
from src.webhook.notifier import set_bot_instance, send_personalized_notifications

from tests.mocks import MockAsyncSession, MockBot, MockResult


# Фикстуры

@pytest.fixture
def mock_db_session():
    """Мокирование сессии БД"""
    return MockAsyncSession()


@pytest.fixture
def mock_bot():
    """Мокирование Telegram Bot"""
    bot = MockBot()
    set_bot_instance(bot)
    return bot


@pytest.fixture
def user_data():
    """Создание тестового пользователя"""
    return User(
        telegram_id=123456789,
        username="telegram_user",
        first_name="Test",
        gitlab_username="gitlab_test_user",
        github_username="github_test_user"
    )


@pytest.fixture
def subscription_data(user_data):
    """Создание тестовой подписки"""
    return Subscription(
        user_id=user_data.telegram_id,
        platform="gitlab",
        project_id="123",
        project_name="test/project",
        event_types="merge_request,issue,pipeline",
        is_active=True
    )


@pytest.fixture
def settings_data(user_data):
    """Создание тестовых настроек уведомлений"""
    return NotificationSettings(
        user_id=user_data.telegram_id,
        mentions_enabled=True,
        thread_updates_enabled=True,
        reviewer_assignment_enabled=True,
        merge_enabled=True,
        pipeline_completion_enabled=True,
        issue_assignment_enabled=True,
        label_changes_enabled=True
    )


# Тесты для personalized_handlers.py

@pytest.mark.asyncio
async def test_handle_gitlab_issue_assignment(mock_db_session, mock_bot, user_data, subscription_data, settings_data):
    """Уведомление о назначении исполнителем Issue"""

    # mock-данные
    mock_db_session.data["User"] = [user_data]
    mock_db_session.data["Subscription"] = [subscription_data]
    mock_db_session.data["NotificationSettings"] = [settings_data]

    # Мокируем execute для возврата данных
    mock_db_session.execute.side_effect = [
        MockResult([subscription_data]),  # Для запроса подписки
        MockResult([user_data]),  # Для запроса пользователя
        MockResult([settings_data])  # Для запроса настроек
    ]

    # Мокируем get для возврата пользователя
    mock_db_session.get.side_effect = [user_data]

    # Данные Webhook: Issue Hook, назначение пользователя
    webhook_data = {
        "object_kind": "issue",
        "event_type": "issue",
        "project": {
            "id": 123,
            "name": "Test Project",
            "path_with_namespace": "test/project"
        },
        "object_attributes": {
            "action": "update",
            "title": "Test Issue",
            "url": "http://gitlab.com/issue/1",
            "assignees": [
                {"username": "gitlab_test_user"}
            ],
            "labels": [],
            "iid": 1
        },
        "changes": {
            "assignees": {
                "previous": [],
                "current": [
                    {"username": "gitlab_test_user"}
                ]
            }
        }
    }

    notifications = await handle_gitlab_issue(webhook_data, mock_db_session)

    # Уведомление должно быть сгенерировано
    assert len(notifications) == 1
    assert notifications[0]["event_type"] == "issue_assigned"
    assert "Новое событие в Issue" in notifications[0]["message"]


@pytest.mark.asyncio
async def test_handle_gitlab_mr_reviewer_assignment(mock_db_session, mock_bot, user_data, subscription_data,
                                                    settings_data):
    """Уведомление о назначении ревьюером MR"""

    mock_db_session.data["User"] = [user_data]
    mock_db_session.data["Subscription"] = [subscription_data]
    mock_db_session.data["NotificationSettings"] = [settings_data]

    # Мокируем execute для возврата данных
    mock_db_session.execute.side_effect = [
        MockResult([subscription_data]),  # Для запроса подписки
        MockResult([user_data]),  # Для запроса пользователя
        MockResult([settings_data])  # Для запроса настроек
    ]

    mock_db_session.get.side_effect = [user_data]

    # Данные Webhook: Merge Request Hook, назначение ревьюера
    webhook_data = {
        "object_kind": "merge_request",
        "event_type": "merge_request",
        "project": {
            "id": 123,
            "name": "Test Project",
            "path_with_namespace": "test/project"
        },
        "object_attributes": {
            "action": "update",
            "title": "Test MR",
            "url": "http://gitlab.com/mr/1",
            "author_id": 999,
            "author": {"username": "other_user"},
            "target_branch": "main",
            "source_branch": "feature",
            "iid": 1
        },
        "reviewers": [
            {"username": "gitlab_test_user"}
        ]
    }
    notifications = await handle_gitlab_merge_request(webhook_data, mock_db_session)

    # Уведомление должно быть сгенерировано
    assert len(notifications) == 1
    assert notifications[0]["event_type"] == "reviewer_assigned"
    assert "Вас назначили ревьюером" in notifications[0]["message"]


@pytest.mark.asyncio
async def test_handle_gitlab_pipeline_success_for_author(mock_db_session, mock_bot, user_data, subscription_data,
                                                         settings_data):
    """Уведомление об успешном пайплайне для автора MR"""

    mock_db_session.data["User"] = [user_data]
    mock_db_session.data["Subscription"] = [subscription_data]
    mock_db_session.data["NotificationSettings"] = [settings_data]

    # Мокируем execute для возврата данных
    mock_db_session.execute.side_effect = [
        MockResult([subscription_data]),  # Для запроса подписки
        MockResult([user_data]),  # Для запроса пользователя
        MockResult([settings_data])  # Для запроса настроек
    ]

    mock_db_session.get.side_effect = [user_data]

    # Данные Webhook: Pipeline Hook, успешный статус, связан с MR, где пользователь - автор
    webhook_data = {
        "object_kind": "pipeline",
        "event_type": "pipeline",
        "project": {
            "id": 123,
            "name": "Test Project",
            "path_with_namespace": "test/project"
        },
        "object_attributes": {
            "status": "success",
            "ref": "refs/heads/feature",
            "id": 100
        },
        "merge_requests": [
            {
                "iid": 1,
                "title": "Test MR",
                "author": {"username": "gitlab_test_user"}
            }
        ]
    }

    notifications = await handle_gitlab_pipeline(webhook_data, mock_db_session)

    # Уведомление должно быть сгенерировано
    assert len(notifications) == 1
    assert notifications[0]["event_type"] == "pipeline_completed"
    assert "Pipeline успешно завершен" in notifications[0]["message"]


@pytest.mark.asyncio
async def test_handle_gitlab_note_mention(mock_db_session, mock_bot, user_data, subscription_data, settings_data):
    """Уведомление об упоминании в комментарии"""

    mock_db_session.data["User"] = [user_data]
    mock_db_session.data["Subscription"] = [subscription_data]
    mock_db_session.data["NotificationSettings"] = [settings_data]

    # Мокируем execute для возврата подписки
    mock_db_session.execute.side_effect = [
        MockResult([subscription_data]),  # Для запроса подписки
        MockResult([user_data]),  # Для запроса пользователя
        MockResult([settings_data])  # Для запроса настроек
    ]

    mock_db_session.get.side_effect = [user_data]

    # Данные Webhook: Note Hook, упоминание пользователя
    webhook_data = {
        "object_kind": "note",
        "event_type": "note",
        "project": {
            "id": 123,
            "name": "Test Project",
            "path_with_namespace": "test/project"
        },
        "user": {"name": "Other User"},
        "object_attributes": {
            "noteable_type": "MergeRequest",
            "noteable_id": 1,
            "note": "Hey @gitlab_test_user, check this out!",
            "url": "http://gitlab.com/note/1"
        },
        "merge_request": {
            "title": "Test MR",
            "author": {"username": "mr_author"},
            "assignees": [],
            "reviewers": []
        }
    }

    notifications = await handle_gitlab_note(webhook_data, mock_db_session)

    # Уведомление сгенерировано
    assert len(notifications) == 1
    assert notifications[0]["event_type"] == "note"
    assert "Вас упомянули в комментарии" in notifications[0]["message"]


# Тесты для handlers.py

@pytest.mark.asyncio
async def test_handle_gitlab_event_calls_notifier(mock_db_session, mock_bot, user_data, subscription_data,
                                                  settings_data):
    """handle_gitlab_event вызывает send_personalized_notifications"""

    mock_db_session.data["User"] = [user_data]
    mock_db_session.data["Subscription"] = [subscription_data]
    mock_db_session.data["NotificationSettings"] = [settings_data]

    # Мокируем execute для возврата данных
    mock_db_session.execute.side_effect = [
        MockResult([subscription_data]),  # Для запроса подписки
        MockResult([user_data]),  # Для запроса пользователя
        MockResult([settings_data])  # Для запроса настроек
    ]

    mock_db_session.get.side_effect = [user_data]

    # Данные Webhook: Issue Hook, назначение пользователя
    webhook_data = {
        "object_kind": "issue",
        "event_type": "issue",
        "project": {
            "id": 123,
            "name": "Test Project",
            "path_with_namespace": "test/project"
        },
        "object_attributes": {
            "action": "update",
            "title": "Test Issue",
            "url": "http://gitlab.com/issue/1",
            "assignees": [
                {"username": "gitlab_test_user"}
            ],
            "labels": [],
            "iid": 1
        },
        "changes": {
            "assignees": {
                "previous": [],
                "current": [
                    {"username": "gitlab_test_user"}
                ]
            }
        }
    }

    # Мокируем get_session, чтобы он возвращал наш mock_db_session
    async def mock_get_session_generator():
        yield mock_db_session

    with patch('src.webhook.handlers.get_session', new=mock_get_session_generator):
        # Мокируем personalized_handlers.handle_gitlab_issue, чтобы он возвращал фиктивное уведомление
        mock_notification = [{"user_id": 123456789, "message": "Test", "platform": "gitlab", "event_type": "test",
                              "project_name": "test"}]
        with patch('src.webhook.handlers.handle_gitlab_issue',
                   new=AsyncMock(return_value=mock_notification)) as mock_handler:
            # Мокируем send_personalized_notifications
            with patch('src.webhook.handlers.send_personalized_notifications', new=AsyncMock()) as mock_send:
                await handle_gitlab_event("Issue Hook", webhook_data)

                mock_handler.assert_called_once()
                # Проверяем, что send_personalized_notifications был вызван с результатом обработчика
                mock_send.assert_called_once_with(mock_notification, mock_db_session)
