# Vikunja Todo Tool for OpenWebUI
# Update 3 - v1.5
# see Project Status (2024-08-26) - Update 3 - v1.5
# Updated status after implementing get_projects() method and refining tool structure.
# 
# work in progress, experimental
#



import requests
import logging
from datetime import datetime
import pytz
from typing import Callable, Any, Dict, List
from pydantic import BaseModel, Field
from urllib.parse import urljoin

logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)


class HelpFunctions:
    def __init__(self):
        self.berlin_tz = pytz.timezone("Europe/Berlin")

    def get_api_url(self, base_url: str, endpoint: str) -> str:
        base_url = base_url.rstrip("/")
        api_path = f"/api/v1/{endpoint.lstrip('/')}"
        return urljoin(base_url, api_path)

    def query_projects(self, base_url: str, api_token: str) -> Dict[int, str]:
        projects_url = self.get_api_url(base_url, "projects")
        headers = {"Authorization": f"Bearer {api_token}"}
        try:
            response = requests.get(projects_url, headers=headers)
            response.raise_for_status()
            return {project["id"]: project["title"] for project in response.json()}
        except Exception as e:
            logger.error(f"Error querying projects: {e}")
            return {}

    def fetch_tasks(
        self, base_url: str, api_token: str, max_todos: int
    ) -> List[Dict[str, Any]]:
        tasks_url = self.get_api_url(base_url, "tasks/all")
        headers = {"Authorization": f"Bearer {api_token}"}
        tasks = []
        page = 1
        while True:
            try:
                response = requests.get(
                    f"{tasks_url}?page={page}&per_page={max_todos}", headers=headers
                )
                response.raise_for_status()
                page_tasks = response.json()
                tasks.extend(page_tasks)
                if len(page_tasks) < max_todos:
                    break
                page += 1
            except Exception as e:
                logger.error(f"Error fetching tasks: {e}")
                break
        return tasks

    def format_date(self, date_str: str) -> str:
        if not date_str or date_str == "0001-01-01T00:00:00Z":
            return "No due date"
        try:
            date = datetime.fromisoformat(date_str.replace("Z", "+00:00"))
            date_berlin = date.astimezone(self.berlin_tz)
            return date_berlin.strftime("%d %B %Y, %H:%M")
        except Exception as e:
            logger.error(f"Error formatting date: {e}")
            return "No due date"

    def format_tasks(
        self,
        tasks: List[Dict[str, Any]],
        project_map: Dict[int, str],
        max_content_length: int,
        specific_project: str = None,
    ) -> str:
        filtered_tasks = [
            {
                "title": task["title"][:max_content_length],
                "due_date": self.format_date(task.get("due_date")),
                "project": project_map.get(task.get("project_id"), "No project"),
            }
            for task in tasks
            if not task["done"]
            and (
                specific_project is None
                or project_map.get(task.get("project_id"), "").lower()
                == specific_project
            )
        ]

        sorted_tasks = sorted(filtered_tasks, key=lambda x: x["project"])
        tasks_by_project = {}
        for task in sorted_tasks:
            project = task["project"]
            if project not in tasks_by_project:
                tasks_by_project[project] = []
            tasks_by_project[project].append(
                f"- {task['title']} (Due: {task['due_date']})"
            )

        formatted_tasks = []
        for project, project_tasks in tasks_by_project.items():
            formatted_tasks.append(f"\nProject: {project}")
            formatted_tasks.extend(project_tasks)

        return "\n".join(formatted_tasks) if formatted_tasks else "No open todos found."


class Tools:
    class Valves(BaseModel):
        VIKUNJA_BASE_URL: str = Field(
            default="https://vikunja.yourdomain.com",
            description="The base URL for your Vikunja instance (without /api/v1/)",
        )
        VIKUNJA_API_TOKEN: str = Field(
            default="your_api_token_here",
            description="The API token for authentication",
        )
        MAX_TODOS: int = Field(
            default=50, description="Maximum number of todos to retrieve per page"
        )
        MAX_CONTENT_LENGTH: int = Field(
            default=500, description="Maximum length of todo content to return"
        )

    def __init__(self):
        self.valves = self.Valves()
        self.helper = HelpFunctions()

    async def get_todos(
        self, query: str, __event_emitter__: Callable[[dict], Any] = None
    ) -> str:
        """
        Retrieve todos from Vikunja, optionally filtered by project.
        :param query: The user's query about todos. Can be "Show me my tasks" for all tasks or "Show me my tasks for project X" for project-specific tasks.
        :param __event_emitter__: Optional event emitter to send status updates to Open Web UI.
        :return: A formatted string representation of the todos.
        """
        logger.debug(f"Received query: {query}")
        logger.debug(f"Using base URL: {self.valves.VIKUNJA_BASE_URL}")

        if __event_emitter__:
            await __event_emitter__(
                {
                    "type": "status",
                    "data": {
                        "status": "in_progress",
                        "description": "Fetching todos...",
                        "done": False,
                    },
                }
            )

        try:
            specific_project = None
            if "for project" in query.lower():
                specific_project = query.lower().split("for project")[-1].strip()

            project_map = self.helper.query_projects(
                self.valves.VIKUNJA_BASE_URL, self.valves.VIKUNJA_API_TOKEN
            )
            tasks = self.helper.fetch_tasks(
                self.valves.VIKUNJA_BASE_URL,
                self.valves.VIKUNJA_API_TOKEN,
                self.valves.MAX_TODOS,
            )
            result = self.helper.format_tasks(
                tasks, project_map, self.valves.MAX_CONTENT_LENGTH, specific_project
            )

            if __event_emitter__:
                await __event_emitter__(
                    {
                        "type": "status",
                        "data": {
                            "status": "success",
                            "description": "Todos retrieved successfully.",
                            "done": True,
                        },
                    }
                )

            logger.debug("Todos retrieved and formatted successfully")
            return result

        except Exception as e:
            error_message = f"Error retrieving todos: {str(e)}"
            logger.error(error_message)
            if __event_emitter__:
                await __event_emitter__(
                    {
                        "type": "status",
                        "data": {
                            "status": "error",
                            "description": error_message,
                            "done": True,
                        },
                    }
                )
            return error_message

    async def get_projects(
        self, __event_emitter__: Callable[[dict], Any] = None
    ) -> str:
        """
        Retrieve all project names from Vikunja.
        :param __event_emitter__: Optional event emitter to send status updates to Open Web UI.
        :return: A formatted string representation of all projects.
        """
        logger.debug("Fetching projects")

        if __event_emitter__:
            await __event_emitter__(
                {
                    "type": "status",
                    "data": {
                        "status": "in_progress",
                        "description": "Fetching projects...",
                        "done": False,
                    },
                }
            )

        try:
            project_map = self.helper.query_projects(
                self.valves.VIKUNJA_BASE_URL, self.valves.VIKUNJA_API_TOKEN
            )

            if not project_map:
                return "No projects found or unable to retrieve projects."

            # Sort projects by name
            sorted_projects = sorted(project_map.values())

            # Format the project list
            project_list = "\n".join(f"- {project}" for project in sorted_projects)
            result = f"Your projects:\n{project_list}"

            if __event_emitter__:
                await __event_emitter__(
                    {
                        "type": "status",
                        "data": {
                            "status": "success",
                            "description": "Projects retrieved successfully.",
                            "done": True,
                        },
                    }
                )

            logger.debug("Projects retrieved and formatted successfully")
            return result

        except Exception as e:
            error_message = f"Error retrieving projects: {str(e)}"
            logger.error(error_message)
            if __event_emitter__:
                await __event_emitter__(
                    {
                        "type": "status",
                        "data": {
                            "status": "error",
                            "description": error_message,
                            "done": True,
                        },
                    }
                )
            return error_message


# Example usage (for testing, not needed in OpenWebUI)
if __name__ == "__main__":
    import asyncio

    async def main():
        tool = Tools()
        logger.debug("Tools instance created")

        tool.valves.VIKUNJA_BASE_URL = "https://yourinstance"
        tool.valves.VIKUNJA_API_TOKEN = "tk_....."

        all_tasks = await tool.get_todos("Show me my tasks")
        logger.debug(f"All tasks:\n{all_tasks}")
        print("All tasks:")
        print(all_tasks)

        print("\n" + "=" * 50 + "\n")

        project_tasks = await tool.get_todos("Show me my tasks for project Personal")
        logger.debug(f"Tasks for project Personal:\n{project_tasks}")
        print("Tasks for project Personal:")
        print(project_tasks)

    asyncio.run(main())
