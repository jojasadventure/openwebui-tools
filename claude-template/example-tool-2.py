# Paperless document loader, based on a script by Jason Leine 
# https://github.com/JLeine 
# Simple tool for openwebui to retrieve search results from the Paperless API. 
# The tool tries to keep returned context size small and manageable for LLM Assistant using it. 
# More docs on how to style Python for open web UI tools, available in other file example-tool.py
# Basics: A Tools class is required + a method for the LLM to interact with the tool, a docstring inside.
# Valves are used to set user preferences
# EventEmitters emit status and also populate LLM context 
# Before the example script begins, some relevant Paperless API documentation below. 

""" 
Paperless makes use of the Django REST Framework standard API interface. It provides a browsable API for most of its endpoints, which you can inspect at http://<paperless-host>:<port>/api/. This also documents most of the available filters and ordering fields.

The API provides the following main endpoints:

    /api/correspondents/: Full CRUD support.
    /api/custom_fields/: Full CRUD support.
    /api/documents/: Full CRUD support, except POSTing new documents. See below.
    ... cut for brevity by user ...
    /api/tags/: Full CRUD support.
    /api/tasks/: Read-only.
    /api/users/: Full CRUD support.
    /api/workflows/: Full CRUD support.
    /api/search/ GET, see below.

All of these endpoints except for the logging endpoint allow you to fetch (and edit and delete where appropriate) individual objects by appending their primary key to the path, e.g. /api/documents/454/.

The objects served by the document endpoint contain the following fields:

    id: ID of the document. Read-only.
    title: Title of the document.
    content: Plain text content of the document.
    tags: List of IDs of tags assigned to this document, or empty list.
    document_type: Document type of this document, or null.
    correspondent: Correspondent of this document or null.
    created: The date time at which this document was created.
    created_date: The date (YYYY-MM-DD) at which this document was created. Optional. If also passed with created, this is ignored.
    modified: The date at which this document was last edited in paperless. Read-only.
    added: The date at which this document was added to paperless. Read-only.
    archive_serial_number: The identifier of this document in a physical document archive.
    original_file_name: Verbose filename of the original document. Read-only.
    archived_file_name: Verbose filename of the archived document. Read-only. Null if no archived document is available.
    notes: Array of notes associated with the document.
    set_permissions: Allows setting document permissions. Optional, write-only. See below.
    custom_fields: Array of custom fields & values, specified as { field: CUSTOM_FIELD_ID, value: VALUE }
 """


import json
import aiohttp
from typing import Optional, Callable, Any, List, Dict
from pydantic import BaseModel, Field
from urllib.parse import urljoin


class PaperlessDocumentLoader:
    def __init__(
        self,
        base_url: str,
        token: str,
        query: Optional[str] = None,
        max_documents: int = 5,
        max_content_length: int = 500,
    ):
        self.base_url = base_url
        self.token = token
        self.query = query
        self.max_documents = max_documents
        self.max_content_length = max_content_length

    async def load(self) -> List[Dict[str, Any]]:
        url = urljoin(self.base_url, "api/documents/")
        headers = {"Authorization": f"Token {self.token}"}
        params = {"query": self.query, "page_size": self.max_documents}

        documents = []

        async with aiohttp.ClientSession() as session:
            async with session.get(url, headers=headers, params=params) as response:
                if response.status == 200:
                    data = await response.json()
                    for result in data.get("results", []):
                        document = {
                            "id": result.get("id"),
                            "title": result.get("title", "Untitled"),
                            "content": result.get("content", "No content available")[
                                : self.max_content_length
                            ],
                            "tags": result.get("tags", []),
                            "document_type": result.get("document_type"),
                            "correspondent": result.get("correspondent"),
                            "created": result.get("created", "Unknown"),
                            "original_file_name": result.get(
                                "original_file_name", "Unknown"
                            ),
                        }
                        documents.append(document)
                else:
                    error_text = await response.text()
                    raise Exception(f"Error: {response.status}, Details: {error_text}")

        return documents

    async def get_tag_names(self, tag_ids: List[int]) -> Dict[int, str]:
        url = urljoin(self.base_url, "api/tags/")
        headers = {"Authorization": f"Token {self.token}"}
        tag_dict = {}

        async with aiohttp.ClientSession() as session:
            async with session.get(url, headers=headers) as response:
                if response.status == 200:
                    data = await response.json()
                    tags = data.get("results", [])
                    tag_dict = {tag["id"]: tag["name"] for tag in tags}
                else:
                    error_text = await response.text()
                    raise Exception(
                        f"Error fetching tags: {response.status}, Details: {error_text}"
                    )

        return tag_dict

    async def get_correspondent_name(self, correspondent_id: int) -> str:
        if correspondent_id is None:
            return "No correspondent"
        url = urljoin(self.base_url, f"api/correspondents/{correspondent_id}/")
        headers = {"Authorization": f"Token {self.token}"}

        async with aiohttp.ClientSession() as session:
            async with session.get(url, headers=headers) as response:
                if response.status == 200:
                    data = await response.json()
                    return data.get("name", "Unknown correspondent")
                else:
                    return "Unknown correspondent"

    async def get_document_type_name(self, document_type_id: int) -> str:
        if document_type_id is None:
            return "No document type"
        url = urljoin(self.base_url, f"api/document_types/{document_type_id}/")
        headers = {"Authorization": f"Token {self.token}"}

        async with aiohttp.ClientSession() as session:
            async with session.get(url, headers=headers) as response:
                if response.status == 200:
                    data = await response.json()
                    return data.get("name", "Unknown document type")
                else:
                    return "Unknown document type"


class EventEmitter:
    def __init__(self, event_emitter: Callable[[dict], Any] = None):
        self.event_emitter = event_emitter

    async def emit(self, description="Unknown State", status="in_progress", done=False):
        if self.event_emitter:
            await self.event_emitter(
                {
                    "type": "status",
                    "data": {
                        "status": status,
                        "description": description,
                        "done": done,
                    },
                }
            )


class Tools:
    class Valves(BaseModel):
        PAPERLESS_URL: str = Field(
            default="https://paperless.yourdomain.com/",
            description="The domain of your paperless service",
        )
        PAPERLESS_TOKEN: str = Field(
            default="",
            description="The token to read docs from paperless",
        )

    def __init__(self):
        self.valves = self.Valves()

    async def search_paperless_documents(
        self,
        query: str,
        __event_emitter__: Callable[[dict], Any] = None,
    ) -> str:
        """
        Search for paperless documents using a query string.

        :param query: The search query to find relevant documents.
        :return: A formatted string containing document summaries or an error message.
        """
        emitter = EventEmitter(__event_emitter__)

        try:
            await emitter.emit(f"Searching documents for: {query}")

            loader = PaperlessDocumentLoader(
                base_url=self.valves.PAPERLESS_URL,
                token=self.valves.PAPERLESS_TOKEN,
                query=query,
            )
            documents = await loader.load()

            if len(documents) == 0:
                error_message = f"Query returned 0 documents for: {query}"
                await emitter.emit(error_message, "error", True)
                return error_message

            # Fetch tag names for all documents
            all_tag_ids = list(
                set(tag_id for doc in documents for tag_id in doc["tags"])
            )
            tag_dict = await loader.get_tag_names(all_tag_ids)

            # Add tag names, correspondent names, and document type names to documents
            for doc in documents:
                doc["tag_names"] = [
                    tag_dict.get(tag_id, f"Unknown tag ({tag_id})")
                    for tag_id in doc["tags"]
                ]
                doc["correspondent_name"] = await loader.get_correspondent_name(
                    doc["correspondent"]
                )
                doc["document_type_name"] = await loader.get_document_type_name(
                    doc["document_type"]
                )

            # Format the documents for better readability
            formatted_documents = []
            for doc in documents:
                formatted_doc = (
                    f"Document ID: {doc['id']}\n"
                    f"Title: {doc['title']}\n"
                    f"Content Preview: {doc['content'][:100]}...\n"
                    f"Tags: {', '.join(doc['tag_names'])}\n"
                    f"Correspondent: {doc['correspondent_name']}\n"
                    f"Document Type: {doc['document_type_name']}\n"
                    f"Created: {doc['created']}\n"
                    f"Original File Name: {doc['original_file_name']}\n"
                    f"---\n"
                )
                formatted_documents.append(formatted_doc)

            result = f"Found {len(documents)} documents for query: {query}\n\n"
            result += "\n".join(formatted_documents)

            await emitter.emit(
                f"Retrieved {len(documents)} documents for query: {query}",
                "success",
                True,
            )

            if __event_emitter__:
                await __event_emitter__(
                    {
                        "type": "citation",
                        "data": {
                            "document": [result],
                            "metadata": [
                                {
                                    "source": "Paperless Document Search",
                                    "query": query,
                                    "document_count": len(documents),
                                }
                            ],
                            "source": {
                                "name": f"{self.valves.PAPERLESS_URL}api/documents/"
                            },
                        },
                    }
                )

            return result
        except Exception as e:
            error_message = f"Error: {str(e)}"
            await emitter.emit(error_message, "error", True)
            return error_message
