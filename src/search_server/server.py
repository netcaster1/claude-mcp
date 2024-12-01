import asyncio
import time
from typing import Literal, Any, Dict

from mcp.server.models import InitializationOptions
import mcp.types as types
from mcp.server import NotificationOptions, Server
from pydantic import AnyUrl
import mcp.server.stdio
from .search_engine import SearchEngine
from .web_scraper import WebScraper
from .knowledge_base import KnowledgeBase
from .logger import logger
import anyio
import click
import uvicorn
from starlette.applications import Starlette
from starlette.routing import Route
from mcp.server.sse import SseServerTransport
import os
from dotenv import load_dotenv

# Store notes as a simple key-value dict to demonstrate state management
notes: dict[str, str] = {}

server = Server("search_server")

# Initialize components
try:
    search_engine = SearchEngine()
    web_scraper = WebScraper()
    knowledge_base = KnowledgeBase()
    logger.info("All components initialized successfully")
except Exception as e:
    logger.error(f"Failed to initialize components: {str(e)}")
    raise

@server.set_logging_level()
async def set_logging_level(level: types.LoggingLevel) -> None:
    """Set the logging level for the server."""
    logger.setLevel(level.upper())
    await server.request_context.session.send_log_message(
        level="info",
        data=f"Log level set to {level}",
        logger="search-server"
    )

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
            description="Search internet using specified search engine",
            inputSchema={
                "type": "object",
                "properties": {
                    "engine": {
                        "type": "string",
                        "enum": ["tavily", "serper", "bing", "google", "linkup"],
                        "description": "Search engine to use"
                    },
                    "query": {
                        "type": "string",
                        "description": "Search query"
                    }
                },
                "required": ["engine", "query"],
            },
        ),
        types.Tool(
            name="scrape-url",
            description="Scrape content from a URL",
            inputSchema={
                "type": "object",
                "properties": {
                    "url": {
                        "type": "string",
                        "description": "URL to scrape"
                    }
                },
                "required": ["url"],
            },
        ),
        types.Tool(
            name="knowledge-search",
            description="Search my knowledge base",
            inputSchema={
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "Search query for knowledge base"
                    }
                },
                "required": ["query"],
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
        if name == "knowledge-search":
            query = arguments.get("query")
            if not query:
                logger.error("Missing query for knowledge search")
                raise ValueError("Missing query")

            logger.info(f"Searching knowledge base: {query}")
            try:
                # Test data instead of actual API call
                # result = {
                #     "results": [
                #         {
                #             "file_name": "test_file.txt",
                #             "chunk_text": "This is a test content",
                #             "distance": 0.82,
                #             "search_type": "vector",
                #             "relevance_score": 0.92
                #         },
                #         {
                #             "file_name": "another_test.txt",
                #             "chunk_text": "Another test content",
                #             "distance": 0.75,
                #             "search_type": "vector",
                #             "relevance_score": 0.85
                #         }
                #     ]
                # }
                result = knowledge_base.search(query)  # Comment out real API call              
                await server.request_context.session.send_resource_list_changed()
                                
                if not result or not isinstance(result, dict):
                    logger.error(f"Invalid response format: {result}")
                    return [
                        types.TextContent(
                            type="text",
                            text="Invalid response from knowledge base"
                        )
                    ]

                formatted_results = []
                results = result.get("results", [])
                logger.info(f"Processing {len(results)} results")
                
                if not results:
                    return [
                        types.TextContent(
                            type="text",
                            text="No results found in knowledge base"
                        )
                    ]
                
                for item in results:                       
                    text = (
                        f"Source: {item.get('file_name', 'Unknown')}\n"
                        f"Content: {item.get('chunk_text', '')}\n"
                        f"Distance: {item.get('distance', 'N/A')}\n"
                        f"Search Type: {item.get('search_type', 'N/A')}\n"
                        f"Relevance: {item.get('relevance_score', 'N/A')}\n"
                    )
                    
                    formatted_results.append(
                        types.TextContent(
                            type="text",
                            text=text
                        )
                    )

                
                if formatted_results:
                    logger.info(f"Returning {len(formatted_results)} formatted results")
                    return formatted_results

            except Exception as e:
                logger.error(f"Error processing knowledge base results: {str(e)}")
                return [
                    types.TextContent(
                        type="text",
                        text=f"Error processing results: {str(e)}"
                    )
                ]

        elif name == "scrape-url":
            url = arguments.get("url")
            if not url:
                logger.error("Missing URL for web scraping")
                raise ValueError("Missing URL")

            logger.info(f"Scraping URL: {url}")
            result = web_scraper.scrape_url(url)
            await server.request_context.session.send_resource_list_changed()
            
            if not result:
                return [
                    types.TextContent(
                        type="text",
                        text=f"Failed to scrape {url}: Unknown error"
                    )
                ]

            if result.get('status') == 'success':
                content = result.get('content', '')
                return [
                    types.TextContent(
                        type="text",
                        text=f"Successfully scraped content from {url}:\n\n{content}"
                    )
                ]
            else:
                error = result.get('error', 'Unknown error')
                return [
                    types.TextContent(
                        type="text",
                        text=f"Failed to scrape {url}: {error}"
                    )
                ]

        elif name == "add-note":
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
            await server.request_context.session.send_resource_list_changed()            
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

# Load environment variables
load_dotenv()

required_env_vars = [
    "TAVILY_API_KEY",
    "SERPER_API_KEY", 
    "BING_API_KEY",
    "GOOGLE_API_KEY",
    "GOOGLE_SEARCH_ENGINE_ID",
    "JINA_API_KEY",
    "KNOWLEDGE_BASE_URL",
    "LINKUP_API_KEY"
]

for var in required_env_vars:
    if not os.getenv(var):
        raise ValueError(f"Missing required environment variable: {var}")

@click.command()
@click.option("--port", default=8509, help="Port to listen on for SSE")
@click.option(
    "--transport",
    type=click.Choice(["stdio", "sse"]),
    default="stdio",
    help="Transport type",
)
def main(port: int, transport: str) -> int:
    if transport == "sse":
        sse = SseServerTransport("/messages")

        async def handle_sse(request):
            async with sse.connect_sse(
                request.scope, request.receive, request._send
            ) as streams:
                await server.run(
                    streams[0],
                    streams[1],
                    InitializationOptions(
                        server_name="search_server",
                        server_version="1.3.3",
                        capabilities=server.get_capabilities(
                            notification_options=NotificationOptions(),
                            experimental_capabilities={},
                        ),
                    ),
                )

        async def handle_messages(request):
            await sse.handle_post_message(request.scope, request.receive, request._send)

        starlette_app = Starlette(
            debug=True,
            routes=[
                Route("/sse", endpoint=handle_sse),
                Route("/messages", endpoint=handle_messages, methods=["POST"]),
            ],
        )

        logger.info(f"Starting SSE server on port {port}")
        uvicorn.run(starlette_app, host="0.0.0.0", port=port)
    else:
        async def arun():
            async with mcp.server.stdio.stdio_server() as streams:
                await server.run(
                    streams[0],
                    streams[1],
                    InitializationOptions(
                        server_name="search_server",
                        server_version="1.3.3",
                        capabilities=server.get_capabilities(
                            notification_options=NotificationOptions(),
                            experimental_capabilities={},
                        ),
                    ),
                )

        logger.info("Starting stdio server")
        anyio.run(arun)

    return 0

if __name__ == "__main__":
    main()