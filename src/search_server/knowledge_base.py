import requests
import os
import time
from typing import Optional, Dict, Any, List
from .logger import logger
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

class KnowledgeBase:
    def __init__(self):
        self.base_url = os.getenv("KNOWLEDGE_BASE_URL", "http://192.168.0.16:3201")
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

    def normalize_result(self, item: Dict[str, Any]) -> Dict[str, Any]:
        """Normalize a single result item to ensure consistent format"""
        return {
            "file_name": str(item.get("file_name", "Unknown")),
            "chunk_text": str(item.get("chunk_text", "")),
            "distance": float(item.get("distance", 0.0)),
            "search_type": str(item.get("search_type", "vector")),
            "relevance_score": float(item.get("relevance_score", 0.0))
        }

    def search(self, query: str) -> Dict[str, List[Dict[str, Any]]]:
        """
        Search documents using knowledge base API
        
        Args:
            query: The search query text
            
        Returns:
            Dict containing the search results with consistent format
        """
        try:
            payload = {
                "query": query,
                "k": 5,
                "llm": "claude",
                "threshold": 3,
                "full_docs_search": True,
                "rerank_method": "jina",
                "file_name": "claude-mcp-call", 
                "contextual_embedding_query": True,
                "search_engine": "bing"
            }
            
            response = self.session.post(self.query_url, json=payload, timeout=30)
            response.raise_for_status()
            result = response.json()
            
            # Get raw results
            raw_results = result.get("results", [])
            if not isinstance(raw_results, list):
                logger.error(f"Invalid results format: {raw_results}")
                return {"results": []}

            # Normalize and limit results
            normalized_results = []
            for item in raw_results[:5]:  # Limit to 5 results
                try:
                    if isinstance(item, dict):
                        normalized_item = self.normalize_result(item)
                        normalized_results.append(normalized_item)
                except (ValueError, TypeError) as e:
                    logger.warning(f"Failed to normalize result item: {e}")
                    continue

            logger.info(f"Normalized {len(normalized_results)} results")
            return {"results": normalized_results}
            
        except requests.Timeout:
            logger.error("Knowledge base search timed out")
            return {"results": []}
        except requests.RequestException as e:
            logger.error(f"Failed to search knowledge base: {str(e)}")
            return {"results": []} 