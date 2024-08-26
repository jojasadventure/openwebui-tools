# Just an example of a working valves class that creates valves for open web UI but does not actually do anything. 

from pydantic import BaseModel, Field


class Tools:
    class Valves(BaseModel):
        VIKUNJA_BASE_URL: str = Field(
            default="https://vikunja.yourdomain.com/api/v1/",
            description="The base URL for the Vikunja API",
        )
        VIKUNJA_API_TOKEN: str = Field(
            default="your_api_token_here",
            description="The API token for authentication",
        )
        MAX_TODOS: int = Field(
            default=5, description="Maximum number of todos to retrieve"
        )
        MAX_CONTENT_LENGTH: int = Field(
            default=500, description="Maximum length of todo content to return"
        )

    def __init__(self):
        self.valves = self.Valves()

    async def debug_log(self, message: str):
        """
        Log debug messages.

        :param message: The debug message to log.
        """
        print(f"[DEBUG] {message}")

    async def load_todos(self) -> str:
        """
        Placeholder method to load todos from Vikunja.

        :return: A string indicating the method was called.
        """
        await self.debug_log(
            f"load_todos called with base URL: {self.valves.VIKUNJA_BASE_URL}"
        )
        return "Todos would be loaded here"


# Example usage
async def main():
    tool = Tools()
    await tool.debug_log("Tools instance created")
    result = await tool.load_todos()
    await tool.debug_log(f"load_todos result: {result}")


if __name__ == "__main__":
    import asyncio

    asyncio.run(main())
