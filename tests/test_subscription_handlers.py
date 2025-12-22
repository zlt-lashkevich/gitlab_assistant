"""
Тесты для src/bot/subscription_handlers.py
"""

import pytest
from unittest.mock import AsyncMock, patch, MagicMock
from aiogram.types import Message, CallbackQuery, User as TelegramUser
from aiogram.fsm.context import FSMContext
from aiogram.fsm.storage.memory import MemoryStorage

from src.database import User, Subscription
from src.bot.handlers import cmd_start
from src.bot.subscription_handlers import (
    cmd_subscribe,
    process_platform_choice,
    process_project_choice,
    process_events_done,
    process_subscribe_confirmation,
    process_unsubscribe_confirmation
)
from src.bot.states import SubscriptionStates

from tests.mocks import MockAsyncSession, MockResult, MockGitLabClient, MockGitHubClient


# Фикстуры для мокирования:

@pytest.fixture
def mock_db_session():
    """Сессия БД"""
    return MockAsyncSession()


@pytest.fixture
def mock_message():
    """Ообъект Message"""
    message = MagicMock(spec=Message)
    message.from_user = TelegramUser(
        id=123456789,
        is_bot=False,
        first_name="Test",
        username="telegram_user"
    )
    message.answer = AsyncMock()
    message.delete = AsyncMock()
    return message


@pytest.fixture
def mock_callback():
    """Объект CallbackQuery"""
    callback = MagicMock(spec=CallbackQuery)
    callback.from_user = TelegramUser(
        id=123456789,
        is_bot=False,
        first_name="Test",
        username="telegram_user"
    )
    callback.message = MagicMock()
    callback.message.edit_text = AsyncMock()
    callback.answer = AsyncMock()
    return callback


@pytest.fixture
def mock_get_session_generator(mock_db_session):
    """Генератор get_session"""

    async def mock_generator():
        yield mock_db_session

    return mock_generator


@pytest.fixture
def state():
    """FSMContext"""
    return FSMContext(storage=MemoryStorage(), key=MagicMock())


@pytest.fixture
def user_data():
    """Создание тестового пользователя"""
    return User(
        telegram_id=123456789,
        username="telegram_user",
        first_name="Test",
        gitlab_token="fake_gitlab_token",
        github_token="fake_github_token",
        gitlab_username="gitlab_test_user",
        github_username="github_test_user"
    )


# cmd_subscribe

@pytest.mark.asyncio
async def test_cmd_subscribe_no_tokens(mock_message, mock_db_session, mock_get_session_generator, user_data, state):
    """Нет токенов"""
    user_data.gitlab_token = None
    user_data.github_token = None
    mock_db_session.execute.return_value = MockResult([user_data])

    with patch('src.bot.subscription_handlers.get_session', new=mock_get_session_generator):
        await cmd_subscribe(mock_message, state)

        mock_message.answer.assert_called_once()
        assert "У вас не установлены токены доступа" in mock_message.answer.call_args[0][0]


@pytest.mark.asyncio
async def test_cmd_subscribe_success(mock_message, mock_db_session, mock_get_session_generator, user_data, state):
    """Успешный старт подписки"""
    mock_db_session.execute.return_value = MockResult([user_data])

    with patch('src.bot.subscription_handlers.get_session', new=mock_get_session_generator):
        await cmd_subscribe(mock_message, state)

        current_state = await state.get_state()
        assert current_state == SubscriptionStates.choosing_platform
        mock_message.answer.assert_called_once()
        assert "Выберите платформу" in mock_message.answer.call_args[0][0]


# выбор платформы

@pytest.mark.asyncio
async def test_process_platform_choice_gitlab_success(mock_callback, mock_db_session, mock_get_session_generator,
                                                      user_data, state):
    """Выбор GitLab, успешное получение проектов"""
    mock_callback.data = "platform:gitlab"
    mock_db_session.execute.return_value = MockResult([user_data])

    # GitLabClient из mocks
    mock_gitlab_client = MockGitLabClient("http://gitlab.com", "fake_gitlab_token")
    mock_gitlab_client.get_projects.return_value = [
        {"id": 1, "name": "Project A", "path_with_namespace": "group/project-a"},
        {"id": 2, "name": "Project B", "path_with_namespace": "group/project-b"}
    ]

    with patch('src.bot.subscription_handlers.get_session', new=mock_get_session_generator), \
            patch('src.bot.subscription_handlers.GitLabClient', new=MagicMock(return_value=mock_gitlab_client)):
        await process_platform_choice(mock_callback, state)

        data = await state.get_data()
        assert data["platform"] == "gitlab"
        assert len(data["projects"]) == 2

        current_state = await state.get_state()
        assert current_state == SubscriptionStates.choosing_project

        mock_callback.message.edit_text.assert_called_once()
        assert "Выберите проект из GitLab" in mock_callback.message.edit_text.call_args[0][0]


@pytest.mark.asyncio
async def test_process_platform_choice_github_success(mock_callback, mock_db_session, mock_get_session_generator,
                                                      user_data, state):
    """Выбор GitHub, успешное получение проектов"""
    mock_callback.data = "platform:github"
    mock_db_session.execute.return_value = MockResult([user_data])

    #  GitHubClient из mocks
    mock_github_client = MockGitHubClient("fake_github_token")
    mock_github_client.get_repositories.return_value = [
        {"id": 1, "full_name": "user/repo-a"},
        {"id": 2, "full_name": "user/repo-b"}
    ]

    with patch('src.bot.subscription_handlers.get_session', new=mock_get_session_generator), \
            patch('src.bot.subscription_handlers.GitHubClient', new=MagicMock(return_value=mock_github_client)):
        await process_platform_choice(mock_callback, state)

        data = await state.get_data()
        assert data["platform"] == "github"
        assert len(data["projects"]) == 2

        current_state = await state.get_state()
        assert current_state == SubscriptionStates.choosing_project

        mock_callback.message.edit_text.assert_called_once()
        assert "Выберите проект из GitHub" in mock_callback.message.edit_text.call_args[0][0]


# Выбор проекта

@pytest.mark.asyncio
async def test_process_project_choice_gitlab(mock_callback, state):
    """Выбор проекта GitLab"""

    gitlab_project = {"id": 1, "name": "Project A", "name_with_namespace": "group/project-a"}

    await state.update_data(
        platform="gitlab",
        projects=[gitlab_project],
        project_id="1"
    )
    mock_callback.data = "project:gitlab:1"

    await process_project_choice(mock_callback, state)

    data = await state.get_data()
    assert data["selected_project"] == gitlab_project
    assert data["project_id"] == "1"

    current_state = await state.get_state()
    assert current_state == SubscriptionStates.choosing_events

    mock_callback.message.edit_text.assert_called_once()
    assert "Выбран проект: group/project-a" in mock_callback.message.edit_text.call_args[0][0]


# process_events_done

@pytest.mark.asyncio
async def test_process_events_done_no_events(mock_callback, state):
    """Завершение выбора без выбранных событий"""
    await state.update_data(selected_events=[])
    mock_callback.data = "events:done"
    await process_events_done(mock_callback, state)

    mock_callback.answer.assert_called_once()
    assert "Выберите хотя бы одно событие" in mock_callback.answer.call_args[0][0]


@pytest.mark.asyncio
async def test_process_events_done_success(mock_callback, state):
    """Успешное завершение выбора событий"""

    gitlab_project = {"id": 1, "name": "Project A", "name_with_namespace": "group/project-a"}

    await state.update_data(
        platform="gitlab",
        selected_project=gitlab_project,
        project_id="1",
        selected_events=["merge_request", "issue"]
    )
    mock_callback.data = "events:done"

    await process_events_done(mock_callback, state)

    current_state = await state.get_state()
    assert current_state == SubscriptionStates.confirming

    mock_callback.message.edit_text.assert_called_once()
    assert "Подтверждение подписки" in mock_callback.message.edit_text.call_args[0][0]
    assert "События: merge_request, issue" in mock_callback.message.edit_text.call_args[0][0]


# Для согласования выбора (confirm)

@pytest.mark.asyncio
async def test_process_subscribe_confirmation_cancel(mock_callback, state):
    """Отмена подписки (должна быть обработана как общая отмена)"""
    mock_callback.data = "cancel"

    from src.bot.subscription_handlers import process_cancel
    await process_cancel(mock_callback, state)

    current_state = await state.get_state()
    assert current_state is None

    mock_callback.message.edit_text.assert_called_once()
    assert "Операция отменена." in mock_callback.message.edit_text.call_args[0][0]


@pytest.mark.asyncio
async def test_process_subscribe_confirmation_success(mock_callback, mock_db_session, mock_get_session_generator,
                                                      user_data, state):
    """Успешное подтверждение подписки"""

    gitlab_project = {"id": 1, "name": "Project A", "path_with_namespace": "group/project-a"}

    await state.update_data(
        platform="gitlab",
        selected_project=gitlab_project,
        project_id="1",
        selected_events=["merge_request", "issue"]
    )
    mock_callback.data = "confirm:subscribe"

    # Мокируем execute для возврата разных результатов
    # Первый вызов - проверка существующей подписки (вернет пусто)
    # Второй вызов - получение пользователя (вернет user_data)
    mock_db_session.execute.side_effect = [
        MockResult([]),
        MockResult([user_data])
    ]

    # WebhookManager из mocks
    mock_webhook_manager = MagicMock()
    mock_webhook_manager.setup_gitlab_webhook = AsyncMock(return_value="123")

    with patch('src.bot.subscription_handlers.get_session', new=mock_get_session_generator), \
            patch('src.bot.subscription_handlers.WebhookManager', mock_webhook_manager):
        await process_subscribe_confirmation(mock_callback, state)

        # Проверяем, что подписка добавлена и сессия закоммичена
        mock_db_session.add.assert_called_once()
        assert mock_db_session.commit.call_count >= 1

        # Проверяем, что WebhookManager был вызван
        mock_webhook_manager.setup_gitlab_webhook.assert_called_once()

        current_state = await state.get_state()
        assert current_state is None

        mock_callback.message.edit_text.assert_called_once()
        assert "Подписка создана!" in mock_callback.message.edit_text.call_args[0][0]
