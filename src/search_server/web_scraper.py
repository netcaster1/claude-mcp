import requests
import os
from typing import Optional, Dict, Any
from .logger import logger

class WebScraper:
    def __init__(self):
        self.jina_api_key = os.getenv("JINA_API_KEY", "jina_api_key")
        if not self.jina_api_key:
            logger.error("JINA_API_KEY environment variable not set")
            raise ValueError("JINA_API_KEY environment variable not set")
            
        self.headers = {
            'Authorization': f'Bearer {self.jina_api_key}'
        }
        logger.info("WebScraper initialized successfully with JINA API key")

    def scrape_url(self, url: str) -> Optional[Dict[str, Any]]:
        """
        Scrape content from a URL using Jina Reader API
        
        Args:
            url: The target URL to scrape
            
        Returns:
            Dict containing the scraped content or None if failed
        """
        try:
            jina_url = f'https://r.jina.ai/{url}'
            response = requests.get(jina_url, headers=self.headers)
            response.raise_for_status()
            
            return {
                'url': url,
                'content': response.text,
                'status': 'success'
            }
            
        except requests.RequestException as e:
            logger.error(f"Failed to scrape URL {url}: {str(e)}")
            return {
                'url': url,
                'error': str(e),
                'status': 'failed'
            } 