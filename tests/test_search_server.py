import pytest
import os
from unittest.mock import patch, MagicMock, Mock, AsyncMock
import json
from pydantic import AnyUrl
import mcp.types as types
import contextvars
from contextlib import asynccontextmanager
from requests.exceptions import RequestException

# Set up test environment variables before imports
os.environ.update({
    "TAVILY_API_KEY": "test_tavily",
    "SERPER_API_KEY": "test_serper",
    "BING_API_KEY": "test_bing",
    "GOOGLE_API_KEY": "test_google",
    "GOOGLE_SEARCH_ENGINE_ID": "test_google_id",
    "KNOWLEDGE_BASE_URL": "http://test:3201",
    "JINA_API_KEY": "test_jina"
})

from search_server.server import (
    handle_call_tool,
    handle_list_tools,
    handle_list_resources,
    handle_read_resource,
    server
)
from search_server.web_scraper import WebScraper
from search_server.knowledge_base import KnowledgeBase

# Test fixtures
@pytest.fixture
def mock_request_context():
    class MockRequestContext:
        class MockSession:
            async def send_resource_list_changed(self):
                pass
            async def send_log_message(self, *args, **kwargs):
                pass
        session = MockSession()
        server = server
    return MockRequestContext()

# Create a context variable for request context
request_context = contextvars.ContextVar("request_context")

@asynccontextmanager
async def set_request_context(context):
    """Async context manager for setting request context"""
    token = request_context.set(context)
    try:
        yield
    finally:
        request_context.reset(token)

# Mock server's request_context property
@pytest.fixture(autouse=True)
def mock_server_context(monkeypatch):
    """Mock the server's request_context property to use our test context"""
    class MockServer:
        @property
        def request_context(self):
            return request_context.get()
    
    # Create a new instance with our mocked property
    mock_server = MockServer()
    
    # Copy all attributes from the original server
    for attr in dir(server):
        if not attr.startswith('_') and attr != 'request_context':
            setattr(mock_server, attr, getattr(server, attr))
    
    # Replace the global server instance
    monkeypatch.setattr('search_server.server.server', mock_server)

# Mock responses
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

# Search engine tests
@pytest.mark.anyio
async def test_search_tavily(mock_tavily_response, mock_request_context):
    async with set_request_context(mock_request_context):
        with patch('requests.post') as mock_post:
            mock_post.return_value.json.return_value = mock_tavily_response
            mock_post.return_value.raise_for_status = Mock()

            result = await handle_call_tool("search", {"engine": "tavily", "query": "test"})
            
            assert len(result) == 1
            assert isinstance(result[0], types.TextContent)
            assert "Test content from Tavily" in result[0].text
            assert "https://test.com/tavily" in result[0].text

# Note management tests
@pytest.mark.anyio
async def test_add_note(mock_request_context):
    async with set_request_context(mock_request_context):
        result = await handle_call_tool("add-note", {"name": "test", "content": "test content"})
        assert len(result) == 1
        assert isinstance(result[0], types.TextContent)
        assert "test content" in result[0].text

@pytest.mark.anyio
async def test_read_resource(mock_request_context):
    async with set_request_context(mock_request_context):
        await handle_call_tool("add-note", {"name": "test", "content": "test content"})
        uri = AnyUrl("note://internal/test")
        content = await handle_read_resource(uri)
        assert content == "test content"

# Web scraper tests
def test_web_scraper_init_with_key():
    with patch.dict(os.environ, {'JINA_API_KEY': 'test_key'}):
        scraper = WebScraper()
        assert scraper.jina_api_key == 'test_key'
        assert scraper.headers == {'Authorization': 'Bearer test_key'}

def test_web_scraper_init_without_key():
    with patch.dict(os.environ, {}, clear=True):
        with pytest.raises(ValueError, match="JINA_API_KEY environment variable not set"):
            WebScraper()

# Knowledge base tests
def test_knowledge_base_init_with_url():
    with patch.dict(os.environ, {'KNOWLEDGE_BASE_URL': 'http://test:3201'}):
        kb = KnowledgeBase()
        assert kb.base_url == 'http://test:3201'
        assert kb.query_url == 'http://test:3201/query'

def test_knowledge_base_init_without_url():
    with patch.dict(os.environ, {}, clear=True):
        with pytest.raises(ValueError, match="KNOWLEDGE_BASE_URL environment variable not set"):
            KnowledgeBase()

def test_knowledge_base_search_success():
    mock_response = MagicMock()
    mock_response.json.return_value = {
        "results": [
            {
                "file_name": "test.txt",
                "chunk_text": "Test content",
                "relevance_score": 0.9
            }
        ],
        "summary": "Test summary",  # This should be filtered out
        "relevant_count": 1
    }
    mock_response.raise_for_status.return_value = None
    
    with patch.dict(os.environ, {'KNOWLEDGE_BASE_URL': 'http://test:3201'}):
        with patch('requests.post', return_value=mock_response) as mock_post:
            kb = KnowledgeBase()
            result = kb.search("test query")
            
            # Verify result is not None
            assert result is not None
            
            # Verify summary is filtered out and check results
            assert "summary" not in result
            assert "results" in result
            results = result.get("results", [])
            assert len(results) == 1
            assert results[0].get("file_name") == "test.txt"

@pytest.mark.anyio
async def test_knowledge_search_tool(mock_request_context):
    mock_result = {
        "results": [
            {
                "file_name": "test.txt",
                "chunk_text": "Test content",
                "relevance_score": 0.9
            }
        ],
        "relevant_count": 1
    }
    
    with patch.dict(os.environ, {'KNOWLEDGE_BASE_URL': 'http://test:3201'}):
        with patch('search_server.knowledge_base.KnowledgeBase.search', return_value=mock_result):
            async with set_request_context(mock_request_context):
                result = await handle_call_tool("knowledge-search", {"query": "test query"})
                
                assert len(result) == 1
                assert isinstance(result[0], types.TextContent)
                text_content = result[0]
                assert "Source: test.txt" in text_content.text
                assert "Test content" in text_content.text
                assert "Relevance: 0.9" in text_content.text

@pytest.mark.anyio
async def test_knowledge_search_tool_missing_query(mock_request_context):
    async with set_request_context(mock_request_context):
        with pytest.raises(ValueError, match="Missing arguments"):
            await handle_call_tool("knowledge-search", {})
  