#    A simple tool that performs basic math operations.
#    This tool doubles a given number when the LLM calls it.
#
#     It's structured to meet the requirements of Open Web UI, which uses tools to augment the LLM's capabilities.
#
#     The key sections of this tool include:
#     
#     - A `Valves` class: Holds configurations. 
#     - Event Emitters fpr Error handling and emitting status updates, shown to user and LLM, as well as filling LLM context before reply to user.
#     - A Tools class to help openwebui connect LLM
#     - Methods that perform the operations, e.g., `double_number`, in this case simply but may call APIs etc.
#     - inside that method a docstring (essential) which describes the functionality - LLM is able to read this to infer how and when to use the tool.
#     - Note, otherwise from that, this code is excessively documented to be a helpful template only, and the rest of the comments are not essential. 
#     - example-tool-2.py shows that there is only one docstring in the essential method and no comments in the file otherwise. 
#     - everything must remain a single file.

from typing import Callable, Any
from pydantic import BaseModel, Field


class SimpleMathTool:
    """
    A simple tool that performs basic math operations.

    This tool doubles a given number when the LLM calls it.
    
    """

    class Valves(BaseModel):
        """This class holds the configuration values needed by the tool.

        In Open Web UI, every tool needs to have a `Valves` class for holding configurations.
        Even if not required, like in this example, placeholder values can be used. This
        keeps the format consistent, making it easier to add real configurations in future tools.
        """

        PLACEHOLDER_VALUE: str = Field(
            default="Placeholder",  # This is just a placeholder since we aren't using any external services here.
            description="This is a placeholder valve for demonstration purposes.",
        )

    def __init__(self):
        """
        The constructor for the SimpleMathTool. It initializes the valves,
        which are typically configuration values but are just placeholders here.
        """
        self.valves = (
            self.Valves()
        )  # Initialize the valves (even if just placeholder values for now)

    async def double_number(
        self,
        query: str,
        __event_emitter__: Callable[[dict], Any] = None,
    ) -> str:
        """
        This method doubles a number provided in the query string.

        The LLM will pass the user's query (e.g., "What is twice 4?"), and this method extracts
        the number, performs the calculation, and returns the result.

        :param query: The user's query containing the number.
        :param __event_emitter__: Optional event emitter to send status updates to Open Web UI.
        :return: The result of doubling the number as a string.
        """
        # Extract number from the query string (assuming the format "twice X").
        try:
            number = int(
                query.split()[-1]
            )  # Extract the last part of the query, which should be the number.

            # Emit status: Let the system know we're starting the doubling process.
            if __event_emitter__:
                await __event_emitter__(
                    {
                        "type": "status",
                        "data": {
                            "status": "in_progress",
                            "description": f"Doubling the number: {number}",
                            "done": False,
                        },
                    }
                )

            # Perform the doubling calculation.
            result = number * 2

            # Emit success status: Let the system know the calculation was successful.
            if __event_emitter__:
                await __event_emitter__(
                    {
                        "type": "status",
                        "data": {
                            "status": "success",
                            "description": f"Successfully doubled the number: {result}",
                            "done": True,
                        },
                    }
                )

            # Return the result as a string that will be passed back to the LLM for output.
            return f"The double of {number} is {result}"

        except ValueError:
            # Handle errors, like if the query doesn't contain a valid number.
            error_message = "Error: Could not parse the number from the query."
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


class Tools:
    """
    This class manages all the tools available to the LLM in Open Web UI.

    Open Web UI looks for a `Tools` class as the entry point for all tools. This class
    contains the methods the LLM will call, such as performing math operations, interacting
    with APIs, etc.

    In this case, we have a method `perform_math_operation` that calls the `double_number`
    method from the `SimpleMathTool` class.
    """

    class Valves(SimpleMathTool.Valves):
        """Inherit from SimpleMathTool.Valves to maintain a consistent configuration structure."""

        pass

    def __init__(self):
        """Initialize the tool, including its valves and the actual tool logic."""
        self.valves = (
            self.Valves()
        )  # Inherited from SimpleMathTool.Valves (could be expanded for real config)
        self.math_tool = (
            SimpleMathTool()
        )  # Initialize the SimpleMathTool for handling math operations

    async def perform_math_operation(
        self, query: str, __event_emitter__: Callable[[dict], Any] = None
    ) -> str:
        """
        This method is called by the LLM to perform a math operation based on the user's query.

        :param query: The user's query asking for a math operation (e.g., "twice 4").
        :param __event_emitter__: Optional event emitter to send status updates to Open Web UI.
        :return: The result of the math operation.
        """
        # Delegate the math operation to the SimpleMathTool.
        return await self.math_tool.double_number(query, __event_emitter__)
