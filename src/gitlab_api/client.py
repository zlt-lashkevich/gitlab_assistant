"""
Клиент для работы с GitLab API
"""

from typing import List, Dict, Optional, Any
from loguru import logger

import aiohttp
from aiohttp import ClientSession


class GitLabClient:

    def __init__(self, gitlab_url: str, private_token: str):
        """
        Args:
            gitlab_url: URL GitLab инстанса (например, https://gitlab.com)
            private_token: Personal Access Token для аутентификации
        """
        self.gitlab_url = gitlab_url.rstrip('/')
        self.api_url = f"{self.gitlab_url}/api/v4"
        self.private_token = private_token
        self.session: Optional[ClientSession] = None

    # Контекстный менеджеры
    async def __aenter__(self):
        """Вход"""
        self.session = aiohttp.ClientSession(
            headers={
                "PRIVATE-TOKEN": self.private_token,
                "Content-Type": "application/json"
            }
        )
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Выход"""
        if self.session:
            await self.session.close()

    async def _request(
            self,
            method: str,
            endpoint: str,
            params: Optional[Dict[str, Any]] = None,
            json_data: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        HTTP запрос

        Args:
            method: HTTP метод (GET, POST, PUT, DELETE)
            endpoint: Endpoint API (без базового URL)
            params: Query параметры
            json_data: JSON данные для POST/PUT запросов

        Returns:
            Ответ от API в виде словаря

        Raises:
            aiohttp.ClientError: При ошибке запроса
        """
        if not self.session:
            raise RuntimeError("Session not initialized. Use async with context manager.")

        url = f"{self.api_url}/{endpoint.lstrip('/')}"

        try:
            async with self.session.request(
                    method=method,
                    url=url,
                    params=params,
                    json=json_data
            ) as response:
                response.raise_for_status()
                return await response.json()
        except aiohttp.ClientError as e:
            logger.error(f"GitLab API request failed: {method} {url} - {e}")
            raise

    async def get_current_user(self) -> Dict[str, Any]:
        """
        Информация о текущем пользователе
        """
        return await self._request("GET", "/user")

    async def get_projects(
            self,
            owned: bool = True,
            membership: bool = True,
            per_page: int = 50,
            page: int = 1
    ) -> List[Dict[str, Any]]:
        """
        Args:
            owned: Только проекты, которыми владеет пользователь
            membership: Проекты, в которых пользователь является участником
            per_page: Количество проектов на странице
            page: Номер страницы

        Returns:
            Список проектов
        """
        params = {
            "owned": str(owned).lower(),
            "membership": str(membership).lower(),
            "per_page": per_page,
            "page": page,
            "order_by": "last_activity_at",
            "sort": "desc"
        }

        return await self._request("GET", "/projects", params=params)

    async def get_project(self, project_id: str) -> Dict[str, Any]:
        """
        Args:
            project_id: ID проекта или путь (namespace/project)

        Returns:
            Информация о проекте
        """
        # URL-encode для путей вида namespace/project
        from urllib.parse import quote
        encoded_id = quote(project_id, safe='')

        return await self._request("GET", f"/projects/{encoded_id}")

    async def get_project_hooks(self, project_id: str) -> List[Dict[str, Any]]:
        """
        Args:
            project_id: ID проекта

        Returns:
            Список webhooks
        """
        from urllib.parse import quote
        encoded_id = quote(str(project_id), safe='')

        return await self._request("GET", f"/projects/{encoded_id}/hooks")

    async def create_project_hook(
            self,
            project_id: str,
            url: str,
            push_events: bool = False,
            issues_events: bool = False,
            merge_requests_events: bool = True,
            wiki_page_events: bool = True,
            pipeline_events: bool = True,
            job_events: bool = False,
            token: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Создание webhook для проекта

        Args:
            project_id: ID проекта
            url: URL для отправки webhook
            push_events: События push
            issues_events: События issues
            merge_requests_events: События merge requests
            wiki_page_events: События wiki
            pipeline_events: События pipeline
            job_events: События jobs
            token: Секретный токен для webhook

        Returns:
            Информация о созданном webhook
        """
        from urllib.parse import quote
        encoded_id = quote(str(project_id), safe='')

        data = {
            "url": url,
            "push_events": push_events,
            "issues_events": issues_events,
            "merge_requests_events": merge_requests_events,
            "wiki_page_events": wiki_page_events,
            "pipeline_events": pipeline_events,
            "job_events": job_events,
        }

        if token:
            data["token"] = token

        return await self._request("POST", f"/projects/{encoded_id}/hooks", json_data=data)

    async def delete_project_hook(self, project_id: str, hook_id: int) -> None:
        """
        Args:
            project_id: ID проекта
            hook_id: ID webhook
        """
        from urllib.parse import quote
        encoded_id = quote(str(project_id), safe='')

        await self._request("DELETE", f"/projects/{encoded_id}/hooks/{hook_id}")

    async def get_merge_requests(
            self,
            project_id: str,
            state: str = "opened",
            per_page: int = 20
    ) -> List[Dict[str, Any]]:
        """
        Args:
            project_id: ID проекта
            state: Состояние MR (opened, closed, merged, all)
            per_page: Количество результатов на странице

        Returns:
            Список merge requests
        """
        from urllib.parse import quote
        encoded_id = quote(str(project_id), safe='')

        params = {
            "state": state,
            "per_page": per_page,
            "order_by": "updated_at",
            "sort": "desc"
        }

        return await self._request("GET", f"/projects/{encoded_id}/merge_requests", params=params)

    async def get_pipelines(
            self,
            project_id: str,
            per_page: int = 20
    ) -> List[Dict[str, Any]]:
        """
        Args:
            project_id: ID проекта
            per_page: Количество результатов на странице

        Returns:
            Список pipelines
        """
        from urllib.parse import quote
        encoded_id = quote(str(project_id), safe='')

        params = {
            "per_page": per_page,
            "order_by": "updated_at",
            "sort": "desc"
        }

        return await self._request("GET", f"/projects/{encoded_id}/pipelines", params=params)
