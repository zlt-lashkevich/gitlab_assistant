"""
Персонализированные обработчики webhook событий GitLab/GitHub
"""

import json
from typing import Dict, List, Any
from loguru import logger
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.database import User, Subscription, NotificationSettings

# GitLab Handlers
async def check_user_mentioned(text: str, user: User) -> bool:
    """Проверка, упомянут ли пользователь в тексте"""
    if not text:
        return False

    if user.gitlab_username and f"@{user.gitlab_username}" in text:
        return True

    if user.github_username and f"@{user.github_username}" in text:
        return True

    if user.first_name and user.first_name.lower() in text.lower():
        return True

    return False


async def get_subscribed_users(session: AsyncSession, project_id: str, platform: str = "gitlab") -> List[User]:
    """Пользователи, подписанные на проект"""
    result = await session.execute(
        select(Subscription).where(
            Subscription.project_id == project_id,
            Subscription.platform == platform,
            Subscription.is_active == True
        )
    )
    subscriptions = result.scalars().all()

    users = []
    for sub in subscriptions:
        result = await session.execute(
            select(User).where(User.telegram_id == sub.user_id)
        )
        user = result.scalar_one_or_none()
        if user:
            users.append(user)

    logger.debug(f"Found {len(users)} subscribed users for project {project_id}")
    return users


async def get_or_create_settings(session: AsyncSession, user_telegram_id: int) -> NotificationSettings:
    """Получение или создание настроек уведомлений"""
    result = await session.execute(
        select(NotificationSettings).where(
            NotificationSettings.user_id == user_telegram_id
        )
    )
    settings = result.scalar_one_or_none()

    if not settings:
        settings = NotificationSettings(user_id=user_telegram_id)
        session.add(settings)
        await session.commit()

    return settings


async def handle_gitlab_note(data: Dict[str, Any], session: AsyncSession) -> List[Dict[str, Any]]:
    """Комментарии-заметки в GitLab"""
    notifications = []

    try:
        note = data.get("object_attributes", {})
        project = data.get("project", {})
        author = data.get("user", {})

        note_text = note.get("note", "")
        noteable_type = note.get("noteable_type", "")
        noteable_id = note.get("noteable_id")
        note_url = note.get("url", "")
        comment_author_username = author.get("username", "")

        logger.debug(f"Note Hook: type={noteable_type}, author={comment_author_username}")

        mr_or_issue = data.get("merge_request") or data.get("issue")
        if not mr_or_issue:
            logger.debug("No MR or Issue found in note data")
            return notifications

        mr_title = mr_or_issue.get("title", "")
        mr_author_username = mr_or_issue.get("author", {}).get("username", "")
        assignees = mr_or_issue.get("assignees", [])
        reviewers = mr_or_issue.get("reviewers", [])

        project_id = str(project.get("id"))
        users = await get_subscribed_users(session, project_id)

        for user in users:
            # Пропускаем пользователей без gitlab_username
            if not user.gitlab_username:
                logger.debug(f"User {user.telegram_id} has no gitlab_username, skipping")
                continue

            # Не уведомляем автора комментария
            if user.gitlab_username == comment_author_username:
                continue

            settings = await get_or_create_settings(session, user.telegram_id)

            should_notify = False
            notification_reason = ""

            # Проверяем упоминание
            if settings.mentions_enabled and await check_user_mentioned(note_text, user):
                should_notify = True
                notification_reason = "💬 Вас упомянули в комментарии"

            # Автор MR/Issue
            elif user.gitlab_username == mr_author_username and settings.thread_updates_enabled:
                should_notify = True
                notification_reason = "💬 Новый комментарий в вашем MR/Issue"

            # Ревьюер
            elif settings.thread_updates_enabled:
                for reviewer in reviewers:
                    if user.gitlab_username == reviewer.get("username"):
                        should_notify = True
                        notification_reason = "💬 Новый комментарий в MR, где вы ревьюер"
                        break

            # Исполнитель
            if not should_notify and settings.thread_updates_enabled:
                for assignee in assignees:
                    if user.gitlab_username == assignee.get("username"):
                        should_notify = True
                        notification_reason = "💬 Новый комментарий в Issue, где вы исполнитель"
                        break

            if should_notify:
                message = (
                    f"{notification_reason}\n\n"
                    f"<b>Проект:</b> {project.get('name')}\n"
                    f"<b>{noteable_type}:</b> {mr_title}\n"
                    f"<b>Автор комментария:</b> {author.get('name', 'Unknown')}\n\n"
                    f"<b>Комментарий:</b>\n"
                    f"<code>{note_text[:500]}</code>\n\n"
                    f" <a href='{note_url}'>Перейти к обсуждению</a>"
                )

                notifications.append({
                    "user_id": user.telegram_id,
                    "platform": "gitlab",
                    "event_type": "note",
                    "project_name": project.get("name", ""),
                    "message": message,
                    "metadata": json.dumps({
                        "note_id": note.get("id"),
                        "noteable_type": noteable_type,
                        "noteable_id": noteable_id,
                        "project_id": project.get("id"),
                        "url": note_url
                    })
                })
                logger.info(f"Created note notification for user {user.telegram_id} (@{user.gitlab_username})")

    except Exception as e:
        logger.error(f"Ошибка при обработке GitLab Note: {e}")
        import traceback
        logger.error(traceback.format_exc())

    return notifications


async def handle_gitlab_merge_request(data: Dict[str, Any], session: AsyncSession) -> List[Dict[str, Any]]:
    """ Merge Request в GitLab"""
    notifications = []

    try:
        mr = data.get("object_attributes", {})
        project = data.get("project", {})

        action = mr.get("action")
        mr_title = mr.get("title", "")
        mr_url = mr.get("url", "")
        mr_author_username = mr.get("author", {}).get("username", "")
        target_branch = mr.get("target_branch", "")
        source_branch = mr.get("source_branch", "")

        assignees = data.get("assignees", [])
        reviewers = data.get("reviewers", [])

        project_id = str(project.get("id"))

        logger.debug(f"MR Hook: action={action}, author={mr_author_username}, reviewers={len(reviewers)}")

        users = await get_subscribed_users(session, project_id)

        for user in users:
            if not user.gitlab_username:
                logger.debug(f"User {user.telegram_id} has no gitlab_username, skipping")
                continue

            # Флаг, что уведомление уже создано для этого пользователя
            notification_created = False

            # Подписан ли пользователь на событие 'merge_request'

            user_subscriptions = [sub for sub in user.subscriptions if
                                  sub.project_id == project_id and sub.platform == "gitlab"]
            if not user_subscriptions or "merge_request" not in user_subscriptions[0].event_types:
                logger.debug(f"User {user.telegram_id} is not subscribed to 'merge_request' event")
                continue

            settings = await get_or_create_settings(session, user.telegram_id)

            # Назначение ревьюером
            if settings.reviewer_assignment_enabled and action in ["open", "update"]:
                for reviewer in reviewers:
                    if user.gitlab_username == reviewer.get("username"):
                        if user.gitlab_username == mr_author_username:
                            continue

                        message = (
                            f"Вас назначили ревьюером\n\n"
                            f"<b>Проект:</b> {project.get('name')}\n"
                            f"<b>MR:</b> {mr_title}\n"
                            f"<b>Автор:</b> {mr_author_username}\n"
                            f"<b>Ветка:</b> {source_branch} → {target_branch}\n\n"
                            f"🔗 <a href='{mr_url}'>Перейти к MR</a>"
                        )

                        notifications.append({
                            "user_id": user.telegram_id,
                            "platform": "gitlab",
                            "event_type": "reviewer_assigned",
                            "project_name": project.get("name", ""),
                            "message": message,
                            "metadata": json.dumps({
                                "mr_id": mr.get("id"),
                                "mr_iid": mr.get("iid"),
                                "project_id": project.get("id"),
                                "url": mr_url,
                                "action": "reviewer_assigned"
                            })
                        })
                        logger.info(
                            f"Created reviewer notification for user {user.telegram_id} (@{user.gitlab_username})")
                        notification_created = True
                        break

            # Мердж своего MR
            if settings.merge_enabled and action == "merge" and user.gitlab_username == mr_author_username:
                message = (
                    f"Ваш MR был вмерджен!\n\n"
                    f"<b>Проект:</b> {project.get('name')}\n"
                    f"<b>MR:</b> {mr_title}\n"
                    f"<b>Ветка:</b> {source_branch} → {target_branch}\n\n"
                    f" <a href='{mr_url}'>Перейти к MR</a>"
                )

                notifications.append({
                    "user_id": user.telegram_id,
                    "platform": "gitlab",
                    "event_type": "merge_request_merged",
                    "project_name": project.get("name", ""),
                    "message": message,
                    "metadata": json.dumps({
                        "mr_id": mr.get("id"),
                        "mr_iid": mr.get("iid"),
                        "project_id": project.get("id"),
                        "url": mr_url,
                        "target_branch": target_branch
                    })
                })
                logger.info(f"Created merge notification for user {user.telegram_id} (@{user.gitlab_username})")

                notification_created = True
                continue

            # Если пользователь подписан на 'merge_request' и не попал в персонализированные фильтры
            if not notification_created and settings.general_updates_enabled:

                message = (
                    f"Обновление Merge Request\n\n"
                    f"<b>Проект:</b> {project.get('name')}\n"
                    f"<b>MR:</b> {mr_title}\n"
                    f"<b>Действие:</b> {action}\n"
                    f"<b>Автор:</b> {mr_author_username}\n\n"
                    f" <a href='{mr_url}'>Перейти к MR</a>"
                )

                notifications.append({
                    "user_id": user.telegram_id,
                    "platform": "gitlab",
                    "event_type": "merge_request_general",
                    "project_name": project.get("name", ""),
                    "message": message,
                    "metadata": json.dumps({
                        "mr_id": mr.get("id"),
                        "mr_iid": mr.get("iid"),
                        "project_id": project.get("id"),
                        "url": mr_url,
                        "action": action
                    })
                })
                logger.info(
                    f"Created general MR notification for user {user.telegram_id} (@{user.gitlab_username})")

    except Exception as e:
        logger.error(f"Ошибка при обработке GitLab MR: {e}")
        import traceback
        logger.error(traceback.format_exc())

    return notifications


async def handle_gitlab_pipeline(data: Dict[str, Any], session: AsyncSession) -> List[Dict[str, Any]]:
    """Pipeline в GitLab"""
    notifications = []

    try:
        pipeline = data.get("object_attributes", {})
        project = data.get("project", {})
        merge_requests = data.get("merge_requests", [])

        status = pipeline.get("status")
        pipeline_id = pipeline.get("id")
        ref = pipeline.get("ref", "")

        logger.debug(f"Pipeline Hook: status={status}, ref={ref}, MRs={len(merge_requests)}")

        if status not in ["success", "failed", "canceled"]:
            return notifications

        if not merge_requests:
            logger.debug("No merge requests associated with pipeline")
            return notifications

        project_id = str(project.get("id"))

        for mr_data in merge_requests:
            mr_iid = mr_data.get("iid")
            mr_author_username = mr_data.get("author", {}).get("username", "")
            mr_title = mr_data.get("title", "")
            mr_url = mr_data.get("url", "")

            users = await get_subscribed_users(session, project_id)

            for user in users:
                if not user.gitlab_username:
                    continue

                if user.gitlab_username != mr_author_username:
                    continue

                settings = await get_or_create_settings(session, user.telegram_id)

                if not settings.pipeline_completion_enabled:
                    continue

                status_text = {"success": "успешно завершен", "failed": "завершен с ошибкой",
                               "canceled": "отменен"}.get(status, status)

                message = (
                    f"Pipeline {status_text}\n\n"
                    f"<b>Проект:</b> {project.get('name')}\n"
                    f"<b>MR:</b> {mr_title}\n"
                    f"<b>Ветка:</b> {ref}\n"
                    f"<b>Pipeline ID:</b> #{pipeline_id}\n\n"
                    f"<a href='{mr_url}'>Перейти к MR</a>"
                )

                notifications.append({
                    "user_id": user.telegram_id,
                    "platform": "gitlab",
                    "event_type": "pipeline_completed",
                    "project_name": project.get("name", ""),
                    "message": message,
                    "metadata": json.dumps({
                        "pipeline_id": pipeline_id,
                        "mr_iid": mr_iid,
                        "project_id": project.get("id"),
                        "status": status,
                        "url": mr_url
                    })
                })
                logger.info(f"Created pipeline notification for user {user.telegram_id} (@{user.gitlab_username})")

    except Exception as e:
        logger.error(f"Ошибка при обработке GitLab Pipeline: {e}")
        import traceback
        logger.error(traceback.format_exc())

    return notifications


async def handle_gitlab_issue(data: Dict[str, Any], session: AsyncSession) -> List[Dict[str, Any]]:
    """ Issue в GitLab"""
    notifications = []

    logger.info("=== handle_gitlab_issue START ===")

    try:
        issue = data.get("object_attributes", {})
        project = data.get("project", {})
        changes = data.get("changes", {})

        action = issue.get("action", "")
        issue_title = issue.get("title", "")
        issue_url = issue.get("url", "")
        issue_author = issue.get("author", {})
        issue_author_username = issue_author.get("username", "") if isinstance(issue_author, dict) else ""

        # assignees могут быть в разных местах
        assignees = data.get("assignees", [])
        if not assignees:
            assignees = issue.get("assignees", [])

        labels = issue.get("labels", [])

        project_id = str(project.get("id"))

        logger.info(f"Issue action: {action}")
        logger.info(f"Issue title: {issue_title}")
        logger.info(f"Issue author: {issue_author_username}")
        logger.info(f"Assignees: {assignees}")
        logger.info(f"Project ID: {project_id}")

        # Логируем полную структуру данных для отладки
        logger.info(f"Full data keys: {list(data.keys())}")
        logger.info(f"Issue keys: {list(issue.keys())}")

        users = await get_subscribed_users(session, project_id)
        logger.info(f"Found {len(users)} subscribed users")

        if not users:
            logger.warning("No subscribed users found!")
            return notifications

        for user in users:
            logger.info(f"Checking user: telegram_id={user.telegram_id}, gitlab_username='{user.gitlab_username}'")

            if not user.gitlab_username:
                logger.warning(f"User {user.telegram_id} has no gitlab_username")
                continue

            settings = await get_or_create_settings(session, user.telegram_id)
            logger.info(f"Settings: issue_assignment_enabled={settings.issue_assignment_enabled}")

            # Проверяем является ли пользователь assignee
            is_assignee = False
            for assignee in assignees:
                assignee_username = assignee.get("username", "")
                logger.info(
                    f"Comparing: user.gitlab_username='{user.gitlab_username}' vs assignee='{assignee_username}'")
                if user.gitlab_username == assignee_username:
                    is_assignee = True
                    break

            logger.info(f"is_assignee: {is_assignee}")

            # Создаём уведомление для ВСЕХ подписанных
            if settings.issue_assignment_enabled:
                # Пропускаем если автор сам создал issue
                if user.gitlab_username == issue_author_username and action == "open":
                    logger.info("Skipping: user is issue author on open action")
                    continue

                logger.info(f"Creating notification for user {user.telegram_id}")

                message = (
                    f"Новое событие в Issue\n\n"
                    f"<b>Действие:</b> {action}\n"
                    f"<b>Проект:</b> {project.get('name')}\n"
                    f"<b>Issue:</b> {issue_title}\n"
                    f"<b>Автор:</b> {issue_author_username}\n"
                    f"<b>Assignees:</b> {', '.join([a.get('username', '') for a in assignees]) if assignees else 'Нет'}\n\n"
                    f"<a href='{issue_url}'>Перейти к Issue</a>"
                )

                notifications.append({
                    "user_id": user.telegram_id,
                    "platform": "gitlab",
                    "event_type": "issue_assigned",
                    "project_name": project.get("name", ""),
                    "message": message,
                    "metadata": json.dumps({
                        "issue_id": issue.get("id"),
                        "issue_iid": issue.get("iid"),
                        "project_id": project.get("id"),
                        "url": issue_url
                    })
                })
                logger.info(f"Notification created!")

        logger.info(f"=== handle_gitlab_issue END: {len(notifications)} notifications ===")

    except Exception as e:
        logger.error(f"Ошибка при обработке GitLab Issue: {e}")
        import traceback
        logger.error(traceback.format_exc())

    return notifications


# Аналогично GitHub Handlers


async def handle_github_pull_request(data: Dict[str, Any], session: AsyncSession) -> List[Dict[str, Any]]:
    """
     Pull Request в GitHub
    Уведомления о назначении ревьюером и мердже PR
    """
    notifications = []

    try:
        action = data.get("action")  # opened, synchronize, closed
        pr = data.get("pull_request", {})
        repo = data.get("repository", {})

        if not pr:
            return notifications

        pr_title = pr.get("title", "")
        pr_url = pr.get("html_url", "")
        pr_author = pr.get("user", {}).get("login", "")
        requested_reviewers = pr.get("requested_reviewers", [])

        project_id = str(repo.get("id"))
        project_name = repo.get("full_name", "")

        # Бреем подписанных пользователей
        users = await get_subscribed_users(session, project_id, platform="github")

        if not users:
            return notifications

        for user in users:
            if not user.github_username:
                continue

            settings = await get_or_create_settings(session, user.telegram_id)

            # Назначение ревьюером
            if settings.reviewer_assignment_enabled and action in ["opened", "synchronize"]:
                for reviewer in requested_reviewers:
                    if user.github_username == reviewer.get("login"):
                        message = (
                            f"Вас назначили ревьюером\n\n"
                            f"<b>Репозиторий:</b> {project_name}\n"
                            f"<b>PR:</b> {pr_title}\n"
                            f"<b>Автор:</b> {pr_author}\n\n"
                            f"<a href='{pr_url}'>Перейти к PR</a>"
                        )

                        notifications.append({
                            "user_id": user.telegram_id,
                            "platform": "github",
                            "event_type": "reviewer_assigned",
                            "project_name": project_name,
                            "message": message,
                            "metadata": json.dumps({
                                "pr_number": pr.get("number"),
                                "repo_id": project_id,
                                "url": pr_url
                            })
                        })
                        break

            #  Мердж своего PR
            if settings.merge_enabled and action == "closed" and pr.get("merged") and user.github_username == pr_author:
                message = (
                    f"Ваш PR был вмерджен!\n\n"
                    f"<b>Репозиторий:</b> {project_name}\n"
                    f"<b>PR:</b> {pr_title}\n\n"
                    f"<a href='{pr_url}'>Перейти к PR</a>"
                )

                notifications.append({
                    "user_id": user.telegram_id,
                    "platform": "github",
                    "event_type": "pull_request_merged",
                    "project_name": project_name,
                    "message": message,
                    "metadata": json.dumps({
                        "pr_number": pr.get("number"),
                        "repo_id": project_id,
                        "url": pr_url
                    })
                })

    except Exception as e:
        logger.error(f"Ошибка при обработке GitHub PR: {e}")

    return notifications


async def handle_github_issues(data: Dict[str, Any], session: AsyncSession) -> List[Dict[str, Any]]:
    """
    Issue в GitHub
    """
    notifications = []

    try:
        action = data.get("action")  # opened, closed, assigned
        issue = data.get("issue", {})
        repo = data.get("repository", {})

        if not issue:
            return notifications

        issue_title = issue.get("title", "")
        issue_url = issue.get("html_url", "")
        assignees = issue.get("assignees", [])

        project_id = str(repo.get("id"))
        project_name = repo.get("full_name", "")

        # Пользователи подписанные на событие
        users = await get_subscribed_users(session, project_id, platform="github")

        if not users:
            return notifications

        for user in users:
            if not user.github_username:
                continue

            settings = await get_or_create_settings(session, user.telegram_id)

            # Назначение исполнителем
            if settings.issue_assignment_enabled and action in ["opened", "assigned"]:
                for assignee in assignees:
                    if user.github_username == assignee.get("login"):
                        message = (
                            f"Вас назначили исполнителем Issue\n\n"
                            f"<b>Репозиторий:</b> {project_name}\n"
                            f"<b>Issue:</b> {issue_title}\n\n"
                            f"<a href='{issue_url}'>Перейти к Issue</a>"
                        )

                        notifications.append({
                            "user_id": user.telegram_id,
                            "platform": "github",
                            "event_type": "issue_assigned",
                            "project_name": project_name,
                            "message": message,
                            "metadata": json.dumps({
                                "issue_number": issue.get("number"),
                                "repo_id": project_id,
                                "url": issue_url
                            })
                        })
                        break

    except Exception as e:
        logger.error(f"Ошибка при обработке GitHub Issue: {e}")

    return notifications


async def handle_github_issue_comment(data: Dict[str, Any], session: AsyncSession) -> List[Dict[str, Any]]:
    """
    Issue Comment в GitHub
    """
    notifications = []

    try:
        action = data.get("action")  # created, edited, deleted
        comment = data.get("comment", {})
        issue = data.get("issue", {})
        repo = data.get("repository", {})

        if action != "created" or not comment or not issue:
            return notifications

        comment_text = comment.get("body", "")
        comment_author = comment.get("user", {}).get("login", "")
        comment_url = comment.get("html_url", "")
        issue_title = issue.get("title", "")
        issue_url = issue.get("html_url", "")
        issue_author = issue.get("user", {}).get("login", "")
        assignees = issue.get("assignees", [])

        project_id = str(repo.get("id"))
        project_name = repo.get("full_name", "")

        users = await get_subscribed_users(session, project_id, platform="github")

        if not users:
            return notifications

        for user in users:
            if not user.github_username:
                continue

            settings = await get_or_create_settings(session, user.telegram_id)

            should_notify = False
            notification_reason = ""

            # Проверяем упоминание
            if settings.mentions_enabled and await check_user_mentioned(comment_text, user):
                should_notify = True
                notification_reason = "💬 Вас упомянули в комментарии"

            # Проверяем, если автор Issue
            elif user.github_username == issue_author and settings.thread_updates_enabled:
                should_notify = True
                notification_reason = "💬 Новый комментарий в вашем Issue"

            # Проверяем, если исполнитель
            if not should_notify and settings.thread_updates_enabled:
                for assignee in assignees:
                    if user.github_username == assignee.get("login"):
                        should_notify = True
                        notification_reason = "💬 Новый комментарий в Issue, где вы исполнитель"
                        break

            if should_notify:
                message = (
                    f"{notification_reason}\n\n"
                    f"<b>Репозиторий:</b> {project_name}\n"
                    f"<b>Issue:</b> {issue_title}\n"
                    f"<b>Автор комментария:</b> {comment_author}\n\n"
                    f"<b>Комментарий:</b>\n"
                    f"<pre>{comment_text[:200]}</pre>\n\n"
                    f"<a href='{comment_url}'>Перейти к комментарию</a>"
                )

                notifications.append({
                    "user_id": user.telegram_id,
                    "platform": "github",
                    "event_type": "issue_comment",
                    "project_name": project_name,
                    "message": message,
                    "metadata": json.dumps({
                        "issue_number": issue.get("number"),
                        "comment_id": comment.get("id"),
                        "repo_id": project_id,
                        "url": comment_url
                    })
                })

    except Exception as e:
        logger.error(f"Ошибка при обработке GitHub Issue Comment: {e}")

    return notifications


async def handle_github_workflow_run(data: Dict[str, Any], session: AsyncSession) -> List[Dict[str, Any]]:
    """
    Workflow Run (Pipeline) в GitHub
    """
    notifications = []

    try:
        action = data.get("action")  # requested, completed
        workflow_run = data.get("workflow_run", {})
        repo = data.get("repository", {})

        if action != "completed" or not workflow_run:
            return notifications

        status = workflow_run.get("conclusion")  # success, failure, cancelled
        workflow_name = workflow_run.get("name", "")
        workflow_url = workflow_run.get("html_url", "")
        head_branch = workflow_run.get("head_branch", "")

        # Получаем информацию о PR
        pull_requests = workflow_run.get("pull_requests", [])
        if not pull_requests:
            return notifications

        project_id = str(repo.get("id"))
        project_name = repo.get("full_name", "")

        users = await get_subscribed_users(session, project_id, platform="github")

        if not users:
            return notifications

        for pr_data in pull_requests:
            pr_author = pr_data.get("user", {}).get("login", "")
            pr_title = pr_data.get("title", "")
            pr_url = pr_data.get("html_url", "")

            for user in users:
                # Уведомляем только автора PR
                if user.github_username != pr_author:
                    continue

                settings = await get_or_create_settings(session, user.telegram_id)

                if not settings.pipeline_completion_enabled:
                    continue

                status_text = {
                    "success": "успешно завершен",
                    "failure": "завершен с ошибкой",
                    "cancelled": "отменен"
                }.get(status, status)

                message = (
                    f"Workflow {status_text}\n\n"
                    f"<b>Репозиторий:</b> {project_name}\n"
                    f"<b>PR:</b> {pr_title}\n"
                    f"<b>Workflow:</b> {workflow_name}\n"
                    f"<b>Ветка:</b> {head_branch}\n\n"
                    f"<a href='{workflow_url}'>Перейти к Workflow</a>"
                )

                notifications.append({
                    "user_id": user.telegram_id,
                    "platform": "github",
                    "event_type": "workflow_completed",
                    "project_name": project_name,
                    "message": message,
                    "metadata": json.dumps({
                        "workflow_id": workflow_run.get("id"),
                        "pr_number": pr_data.get("number"),
                        "repo_id": project_id,
                        "status": status,
                        "url": workflow_url
                    })
                })

    except Exception as e:
        logger.error(f"Ошибка при обработке GitHub Workflow Run: {e}")

    return notifications
