"""
Обработчики webhook событий от GitLab и GitHub с персонализацией
"""

from typing import Dict, Any
from loguru import logger

from src.database import get_session
from src.webhook.notifier import send_personalized_notifications
from src.webhook.personalized_handlers import (
    handle_gitlab_note,
    handle_gitlab_merge_request,
    handle_gitlab_pipeline,
    handle_gitlab_issue,
    handle_github_pull_request,
    handle_github_issues,
    handle_github_issue_comment,
    handle_github_workflow_run
)


async def handle_gitlab_event(event_type: str, data: Dict[str, Any]) -> None:
    """Персонализированные уведомления для GitLab"""
    try:
        logger.info(f"Processing GitLab event: {event_type}")

        # Логируем данные проекта
        project = data.get("project", {})
        project_id = project.get("id")
        project_name = project.get("name")
        logger.info(f"Project: id={project_id}, name={project_name}")

        notifications = []

        async for session in get_session():
            logger.info(f"Got database session, processing {event_type}")

            if event_type in ["Note Hook", "Comment Hook"]:
                notifications = await handle_gitlab_note(data, session)

            elif event_type == "Merge Request Hook":
                notifications = await handle_gitlab_merge_request(data, session)

            elif event_type == "Pipeline Hook":
                notifications = await handle_gitlab_pipeline(data, session)

            elif event_type == "Issue Hook":
                notifications = await handle_gitlab_issue(data, session)

            else:
                logger.warning(f"No handler for GitLab event: {event_type}")
                return

            # Логируем результат
            logger.info(f"Handler returned {len(notifications)} notifications")

            if notifications:
                for i, n in enumerate(notifications):
                    logger.info(f"  Notification {i + 1}: user_id={n.get('user_id')}, type={n.get('event_type')}")

                await send_personalized_notifications(notifications, session)
                logger.info(f"Successfully sent {len(notifications)} notifications for {event_type}")
            else:
                logger.warning(f"No notifications generated for {event_type}")

    except Exception as e:
        logger.error(f"Error handling GitLab event: {e}")
        import traceback
        logger.error(traceback.format_exc())


async def handle_github_event(event_type: str, data: Dict[str, Any]) -> None:
    """Персонализированные уведомления для GitHub"""
    try:
        logger.info(f"Processing GitHub event: {event_type}")

        # Логируем данные репозитория
        repo = data.get("repository", {})
        repo_name = repo.get("full_name")
        logger.info(f"Repository: {repo_name}")

        notifications = []

        async for session in get_session():
            logger.info(f"Got database session, processing {event_type}")

            if event_type == "pull_request":
                notifications = await handle_github_pull_request(data, session)
            elif event_type == "issues":
                notifications = await handle_github_issues(data, session)
            elif event_type == "issue_comment":
                notifications = await handle_github_issue_comment(data, session)
            elif event_type == "workflow_run":
                notifications = await handle_github_workflow_run(data, session)
            else:
                logger.warning(f"No handler for GitHub event: {event_type}")
                return

            logger.info(f"Handler returned {len(notifications)} notifications")

            if notifications:
                for i, n in enumerate(notifications):
                    logger.info(f"  Notification {i + 1}: user_id={n.get('user_id')}, type={n.get('event_type')}")

                await send_personalized_notifications(notifications, session)
                logger.info(f"Successfully sent {len(notifications)} notifications for {event_type}")
            else:
                logger.warning(f"No notifications generated for {event_type}")

    except Exception as e:
        logger.error(f"Error handling GitHub event: {e}")
        import traceback
        logger.error(traceback.format_exc())