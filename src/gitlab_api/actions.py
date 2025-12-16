"""
Методы для выполнения действий с MR/Issue в GitLab
"""

from typing import Dict, Any, Optional, List
import aiohttp
from loguru import logger


class GitLabActions:

    def __init__(self, token: str, base_url: str = "https://gitlab.com/api/v4"):
        self.token = token
        self.base_url = base_url
        self.headers = {"PRIVATE-TOKEN": token}

    async def approve_merge_request(self, project_id: str, mr_iid: int) -> Dict[str, Any]:
        """
        Args:
            project_id: ID проекта
            mr_iid: IID Merge Request

        Returns:
            Информация об approval
        """
        url = f"{self.base_url}/projects/{project_id}/merge_requests/{mr_iid}/approve"

        async with aiohttp.ClientSession() as session:
            async with session.post(url, headers=self.headers) as response:
                if response.status == 201:
                    return await response.json()
                else:
                    error_text = await response.text()
                    logger.error(f"Failed to approve MR: {error_text}")
                    raise Exception(f"Failed to approve MR: {error_text}")

    async def merge_merge_request(
            self,
            project_id: str,
            mr_iid: int,
            merge_commit_message: Optional[str] = None,
            should_remove_source_branch: bool = True
    ) -> Dict[str, Any]:
        """
        Args:
            project_id: ID проекта
            mr_iid: IID Merge Request
            merge_commit_message: Сообщение коммита (опционально)
            should_remove_source_branch: Удалить исходную ветку после мерджа

        Returns:
            Информация о MR после мерджа
        """
        url = f"{self.base_url}/projects/{project_id}/merge_requests/{mr_iid}/merge"

        data = {
            "should_remove_source_branch": should_remove_source_branch
        }

        if merge_commit_message:
            data["merge_commit_message"] = merge_commit_message

        async with aiohttp.ClientSession() as session:
            async with session.put(url, headers=self.headers, json=data) as response:
                if response.status == 200:
                    return await response.json()
                else:
                    error_text = await response.text()
                    logger.error(f"Failed to merge MR: {error_text}")
                    raise Exception(f"Failed to merge MR: {error_text}")

    async def get_merge_request(self, project_id: str, mr_iid: int) -> Dict[str, Any]:
        """
        Args:
            project_id: ID проекта
            mr_iid: IID Merge Request

        Returns:
            Информация о MR
        """
        url = f"{self.base_url}/projects/{project_id}/merge_requests/{mr_iid}"

        async with aiohttp.ClientSession() as session:
            async with session.get(url, headers=self.headers) as response:
                if response.status == 200:
                    return await response.json()
                else:
                    error_text = await response.text()
                    logger.error(f"Failed to get MR: {error_text}")
                    raise Exception(f"Failed to get MR: {error_text}")

    async def get_merge_request_pipelines(self, project_id: str, mr_iid: int) -> List[Dict[str, Any]]:
        """
        Args:
            project_id: ID проекта
            mr_iid: IID Merge Request

        Returns:
            Список pipelines
        """
        url = f"{self.base_url}/projects/{project_id}/merge_requests/{mr_iid}/pipelines"

        async with aiohttp.ClientSession() as session:
            async with session.get(url, headers=self.headers) as response:
                if response.status == 200:
                    return await response.json()
                else:
                    error_text = await response.text()
                    logger.error(f"Failed to get MR pipelines: {error_text}")
                    return []

    async def retry_pipeline(self, project_id: str, pipeline_id: int) -> Dict[str, Any]:
        """
        Args:
            project_id: ID проекта
            pipeline_id: ID pipeline

        Returns:
            Информация о pipeline
        """
        url = f"{self.base_url}/projects/{project_id}/pipelines/{pipeline_id}/retry"

        async with aiohttp.ClientSession() as session:
            async with session.post(url, headers=self.headers) as response:
                if response.status == 201:
                    return await response.json()
                else:
                    error_text = await response.text()
                    logger.error(f"Failed to retry pipeline: {error_text}")
                    raise Exception(f"Failed to retry pipeline: {error_text}")

    async def assign_reviewer(
            self,
            project_id: str,
            mr_iid: int,
            reviewer_ids: List[int]
    ) -> Dict[str, Any]:
        """
        Args:
            project_id: ID проекта
            mr_iid: IID Merge Request
            reviewer_ids: Список ID ревьюеров

        Returns:
            Обновленная информация о MR
        """
        url = f"{self.base_url}/projects/{project_id}/merge_requests/{mr_iid}"

        data = {
            "reviewer_ids": reviewer_ids
        }

        async with aiohttp.ClientSession() as session:
            async with session.put(url, headers=self.headers, json=data) as response:
                if response.status == 200:
                    return await response.json()
                else:
                    error_text = await response.text()
                    logger.error(f"Failed to assign reviewers: {error_text}")
                    raise Exception(f"Failed to assign reviewers: {error_text}")

    async def get_project_members(self, project_id: str) -> List[Dict[str, Any]]:
        """
        Args:
            project_id: ID проекта

        Returns:
            Список участников
        """
        url = f"{self.base_url}/projects/{project_id}/members"

        async with aiohttp.ClientSession() as session:
            async with session.get(url, headers=self.headers) as response:
                if response.status == 200:
                    return await response.json()
                else:
                    error_text = await response.text()
                    logger.error(f"Failed to get project members: {error_text}")
                    return []
