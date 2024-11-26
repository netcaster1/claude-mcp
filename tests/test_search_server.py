import pytest
import os
from unittest.mock import patch, Mock, AsyncMock
import json
from pydantic import AnyUrl
from contextlib import asynccontextmanager
import mcp.types as types
import contextvars

# Set test API keys
os.environ["TAVILY_API_KEY"] = "test_tavily"
os.environ["SERPER_API_KEY"] = "test_serper"
os.environ["BING_API_KEY"] = "test_bing"
os.environ["GOOGLE_API_KEY"] = "test_google"
os.environ["GOOGLE_SEARCH_ENGINE_ID"] = "test_google_id"

from search_server.server import (
    handle_call_tool,
    handle_list_resources,
    handle_list_tools,
    handle_read_resource,
    search_engine,
    server
)

@pytest.fixture
def anyio_backend():
    return "asyncio"

@pytest.fixture
async def mock_session():
    class MockSession:
        async def send_resource_list_changed(self):
            pass
        
        async def send_log_message(self, *args, **kwargs):
            pass

    return MockSession()

@pytest.fixture
async def mock_request_context(mock_session):
    class MockRequestContext:
        def __init__(self, session, server):
            self.session = session
            self.server = server

    return MockRequestContext(mock_session, server)

# Create a mock context variable
request_ctx = contextvars.ContextVar('request_ctx')

@asynccontextmanager
async def set_request_context(context):
    token = request_ctx.set(context)
    try:
        yield
    finally:
        request_ctx.reset(token)

@pytest.fixture(autouse=True)
def mock_server_context(monkeypatch):
    """Mock the server's request_context property to use our test context"""
    class MockServer:
        @property
        def request_context(self):
            return request_ctx.get()
    
    # Create a new instance with our mocked property
    mock_server = MockServer()
    
    # Copy all attributes from the original server
    for attr in dir(server):
        if not attr.startswith('_') and attr != 'request_context':
            setattr(mock_server, attr, getattr(server, attr))
    
    # Replace the global server instance
    monkeypatch.setattr('search_server.server.server', mock_server)

@pytest.fixture
def mock_tavily_response():
    return {
        "results": [
            {
                "content": "Test content from Tavily",
                "url": "https://test.com/tavily"
            }
        ]
    }

@pytest.fixture
def mock_serper_response():
    return {
        "organic": [
            {
                "snippet": "Test content from Serper",
                "link": "https://test.com/serper"
            }
        ]
    }

@pytest.fixture
def mock_bing_response():
    return {
        "webPages": {
            "value": [
                {
                    "snippet": "Test content from Bing",
                    "displayUrl": "https://test.com/bing"
                }
            ]
        }
    }

@pytest.fixture
def mock_google_response():
    return {
        "items": [
            {
                "snippet": "Test content from Google",
                "link": "https://test.com/google"
            }
        ]
    }

@pytest.mark.anyio
async def test_search_tavily(mock_tavily_response, mock_request_context):
    async with set_request_context(mock_request_context):
        with patch('requests.post') as mock_post:
            mock_post.return_value.json.return_value = mock_tavily_response
            mock_post.return_value.raise_for_status = Mock()

            result = await handle_call_tool("search", {"engine": "tavily", "query": "test"})
            
            assert len(result) == 1
            assert result[0].type == "text"
            assert "Test content from Tavily" in result[0].text
            assert "https://test.com/tavily" in result[0].text

@pytest.mark.anyio
async def test_search_serper(mock_serper_response, mock_request_context):
    async with set_request_context(mock_request_context):
        with patch('requests.post') as mock_post:
            mock_post.return_value.json.return_value = mock_serper_response
            mock_post.return_value.raise_for_status = Mock()

            result = await handle_call_tool("search", {"engine": "serper", "query": "test"})
            
            assert len(result) == 1
            assert result[0].type == "text"
            assert "Test content from Serper" in result[0].text
            assert "https://test.com/serper" in result[0].text

@pytest.mark.anyio
async def test_search_bing(mock_bing_response, mock_request_context):
    async with set_request_context(mock_request_context):
        with patch('requests.get') as mock_get:
            mock_get.return_value.json.return_value = mock_bing_response
            mock_get.return_value.raise_for_status = Mock()

            result = await handle_call_tool("search", {"engine": "bing", "query": "test"})
            
            assert len(result) == 1
            assert result[0].type == "text"
            assert "Test content from Bing" in result[0].text
            assert "https://test.com/bing" in result[0].text

@pytest.mark.anyio
async def test_search_google(mock_google_response, mock_request_context):
    async with set_request_context(mock_request_context):
        with patch('requests.get') as mock_get:
            mock_get.return_value.json.return_value = mock_google_response
            mock_get.return_value.raise_for_status = Mock()

            result = await handle_call_tool("search", {"engine": "google", "query": "test"})
            
            assert len(result) == 1
            assert result[0].type == "text"
            assert "Test content from Google" in result[0].text
            assert "https://test.com/google" in result[0].text

@pytest.mark.anyio
async def test_add_note(mock_request_context):
    async with set_request_context(mock_request_context):
        result = await handle_call_tool("add-note", {"name": "test", "content": "test content"})
        assert len(result) == 1
        assert result[0].type == "text"
        assert "test content" in result[0].text

@pytest.mark.anyio
async def test_read_resource(mock_request_context):
    async with set_request_context(mock_request_context):
        # First add a note
        await handle_call_tool("add-note", {"name": "test", "content": "test content"})
        
        # Then read it
        uri = AnyUrl("note://internal/test")
        content = await handle_read_resource(uri)
        assert content == "test content"

@pytest.mark.anyio
async def test_list_resources(mock_request_context):
    async with set_request_context(mock_request_context):
        # First add a note
        await handle_call_tool("add-note", {"name": "test", "content": "test content"})
        
        resources = await handle_list_resources()
        assert len(resources) == 1
        assert resources[0].name == "Note: test"
        assert resources[0].mimeType == "text/plain"

@pytest.mark.anyio
async def test_list_tools(mock_request_context):
    async with set_request_context(mock_request_context):
        tools = await handle_list_tools()
        assert len(tools) == 2
        tool_names = {tool.name for tool in tools}
        assert "add-note" in tool_names
        assert "search" in tool_names

@pytest.mark.anyio
async def test_invalid_tool(mock_request_context):
    async with set_request_context(mock_request_context):
        with pytest.raises(ValueError) as exc_info:
            await handle_call_tool("invalid_tool", {"test": "test"})
        assert "Unknown tool: invalid_tool" in str(exc_info.value)

@pytest.mark.anyio
async def test_missing_arguments(mock_request_context):
    async with set_request_context(mock_request_context):
        with pytest.raises(ValueError) as exc_info:
            await handle_call_tool("search", None)
        assert "Missing arguments" in str(exc_info.value)

@pytest.mark.anyio
async def test_missing_search_params(mock_request_context):
    async with set_request_context(mock_request_context):
        with pytest.raises(ValueError) as exc_info:
            await handle_call_tool("search", {"engine": "tavily"})
        assert "Missing engine or query" in str(exc_info.value) 