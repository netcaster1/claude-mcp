import requests
import os
from typing import Optional, Dict, Any
from .logger import logger
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

class KnowledgeBase:
    def __init__(self):
        self.base_url = os.getenv("KNOWLEDGE_BASE_URL")
        if not self.base_url:
            logger.error("KNOWLEDGE_BASE_URL environment variable not set")
            raise ValueError("KNOWLEDGE_BASE_URL environment variable not set")
            
        self.query_url = f"{self.base_url}/query"
        
        # Setup session with retries
        self.session = requests.Session()
        retries = Retry(total=3, backoff_factor=0.1)
        self.session.mount('http://', HTTPAdapter(max_retries=retries))
        self.session.mount('https://', HTTPAdapter(max_retries=retries))
        
        logger.info("KnowledgeBase initialized successfully")

    def search(self, query: str) -> Optional[Dict[str, Any]]:
        """
        Search documents using knowledge base API
        
        Args:
            query: The search query text
            
        Returns:
            Dict containing the search results or None if failed
        """
        try:
            payload = {
                "query": query,
                "k": 20,
                "llm": "claude",
                "threshold": 3,
                "full_docs_search": True,
                "rerank_method": "jina",
                "file_name": "claude-mcp-call",
                "contextual_embedding_query": True,
                "search_engine": "linkup"
            }
            
            response = self.session.post(self.query_url, json=payload, timeout=30)
            response.raise_for_status()
            
            result = response.json()
            # Filter out summary as requested
            if "summary" in result:
                del result["summary"]
                
            return result
            
        except requests.Timeout:
            logger.error("Knowledge base search timed out")
            return {
                "error": "Request timed out",
                "status": "failed"
            }
        except requests.RequestException as e:
            logger.error(f"Failed to search knowledge base: {str(e)}")
            return {
                "error": str(e),
                "status": "failed"
            } 