import asyncio
import logging
from typing import Literal, Any

from mcp.server.models import InitializationOptions
import mcp.types as types
from mcp.server import NotificationOptions, Server
from pydantic import AnyUrl
import mcp.server.stdio
from .search_engine import SearchEngine

# Set up logging
logger = logging.getLogger("search-server")
logger.setLevel(logging.INFO)

# Store notes as a simple key-value dict to demonstrate state management
notes: dict[str, str] = {}

server = Server("search_server")

@server.set_logging_level()
async def set_logging_level(level: types.LoggingLevel) -> None:
    """Set the logging level for the server."""
    logger.setLevel(level.upper())
    await server.request_context.session.send_log_message(
        level="info",
        data=f"Log level set to {level}",
        logger="search-server"
    )

# Initialize search engine
try:
    search_engine = SearchEngine()
    logger.info("Search engine initialized successfully")
except Exception as e:
    logger.error(f"Failed to initialize search engine: {str(e)}")
    raise

@server.list_tools()
async def handle_list_tools() -> list[types.Tool]:
    """List available tools."""
    logger.debug("Listing available tools")
    return [
        types.Tool(
            name="add-note",
            description="Add a new note",
            inputSchema={
                "type": "object",
                "properties": {
                    "name": {"type": "string"},
                    "content": {"type": "string"},
                },
                "required": ["name", "content"],
            },
        ),
        types.Tool(
            name="search",
            description="Search using specified engine",
            inputSchema={
                "type": "object",
                "properties": {
                    "engine": {
                        "type": "string",
                        "enum": ["tavily", "serper", "bing", "google"],
                        "description": "Search engine to use"
                    },
                    "query": {
                        "type": "string",
                        "description": "Search query"
                    }
                },
                "required": ["engine", "query"],
            },
        )
    ]

@server.call_tool()
async def handle_call_tool(
    name: str, arguments: dict | None
) -> list[types.TextContent | types.ImageContent | types.EmbeddedResource]:
    """Handle tool execution requests."""
    if not arguments:
        logger.error("Missing arguments for tool call")
        raise ValueError("Missing arguments")

    try:
        if name == "add-note":
            note_name = arguments.get("name")
            content = arguments.get("content")

            if not note_name or not content:
                logger.error("Missing name or content for add-note")
                raise ValueError("Missing name or content")

            logger.info(f"Adding note: {note_name}")
            notes[note_name] = content
            await server.request_context.session.send_resource_list_changed()

            return [
                types.TextContent(
                    type="text",
                    text=f"Added note '{note_name}' with content: {content}",
                )
            ]
        
        elif name == "search":
            engine = arguments.get("engine")
            query = arguments.get("query")

            if not engine or not query:
                logger.error("Missing engine or query for search")
                raise ValueError("Missing engine or query")

            logger.info(f"Performing search with engine: {engine}, query: {query}")
            results = search_engine.search(engine, query)
            logger.info(f"Found {len(results)} results")
            
            formatted_results = []
            for result in results:
                formatted_results.append(
                    types.TextContent(
                        type="text",
                        text=f"Source: {result['file_name']}\nURL: {result['url']}\nContent: {result['chunk_text']}\n"
                    )
                )
            
            return formatted_results

        else:
            logger.error(f"Unknown tool: {name}")
            raise ValueError(f"Unknown tool: {name}")

    except Exception as e:
        logger.error(f"Error executing tool {name}: {str(e)}")
        raise

@server.list_resources()
async def handle_list_resources() -> list[types.Resource]:
    logger.debug("Listing resources")
    return [
        types.Resource(
            uri=AnyUrl(f"note://internal/{name}"),
            name=f"Note: {name}",
            description=f"A simple note named {name}",
            mimeType="text/plain",
        )
        for name in notes
    ]

@server.read_resource()
async def handle_read_resource(uri: AnyUrl) -> str:
    logger.debug(f"Reading resource: {uri}")
    if uri.scheme != "note":
        logger.error(f"Unsupported URI scheme: {uri.scheme}")
        raise ValueError(f"Unsupported URI scheme: {uri.scheme}")

    name = uri.path
    if name is not None:
        name = name.lstrip("/")
        if name not in notes:
            logger.error(f"Note not found: {name}")
            raise ValueError(f"Note not found: {name}")
        return notes[name]
    raise ValueError(f"Note not found: {name}")

async def main():
    logger.info("Starting search server")
    async with mcp.server.stdio.stdio_server() as (read_stream, write_stream):
        await server.run(
            read_stream,
            write_stream,
            InitializationOptions(
                server_name="search_server",
                server_version="0.1.0",
                capabilities=server.get_capabilities(
                    notification_options=NotificationOptions(),
                    experimental_capabilities={},
                ),
            ),
        )