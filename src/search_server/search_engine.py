import requests
import json
import os
from typing import List, Dict, Any

class SearchEngine:
    def __init__(self):
        self.tavily_api_key = os.getenv("TAVILY_API_KEY", "tavily_api_key")
        self.serper_api_key = os.getenv("SERPER_API_KEY", "serper_api_key")
        self.bing_api_key = os.getenv("BING_API_KEY", "bing_api_key")
        self.google_api_key = os.getenv("GOOGLE_API_KEY", "google_api_key")
        self.google_search_engine_id = os.getenv("GOOGLE_SEARCH_ENGINE_ID", "google_search_engine_id")
        self.linkup_api_key = os.getenv("LINKUP_API_KEY", "linkup_api_key")
        self.exa_api_key = os.getenv("EXA_API_KEY", "exa_api_key")
        
    def search_tavily(self, query: str) -> List[Dict[str, Any]]:
        endpoint = "https://api.tavily.com/search"
        payload = {
            "api_key": self.tavily_api_key,
            "query": query
        }
        headers = {"Content-Type": "application/json"}

        try:
            response = requests.post(endpoint, headers=headers, json=payload)
            response.raise_for_status()
            search_results = response.json()

            results = []
            for result in search_results.get('results', []):
                results.append({
                    "file_name": "Tavily",
                    "chunk_text": result.get('content'),
                    "distance": 0.9,
                    "search_type": "web",
                    "url": result.get('url')
                })
            return results
        except requests.exceptions.RequestException as e:
            print(f"Error in Tavily search: {e}")
            return []

    def search_serper(self, query: str) -> List[Dict[str, Any]]:
        url = "https://google.serper.dev/search"
        payload = json.dumps({
            "q": query,
            "hl": "zh-cn",
            "num": 10
        })
        headers = {
            'X-API-KEY': self.serper_api_key,
            'Content-Type': 'application/json'
        }

        try:
            response = requests.post(url, headers=headers, data=payload)
            response.raise_for_status()
            search_results = response.json()

            results = []
            for result in search_results.get('organic', []):
                results.append({
                    "file_name": "Serper",
                    "chunk_text": result.get('snippet'),
                    "distance": 0.9,
                    "search_type": "web",
                    "url": result.get('link')
                })
            return results
        except requests.exceptions.RequestException as e:
            print(f"Error in Serper search: {e}")
            return []

    def search_bing(self, query: str) -> List[Dict[str, Any]]:
        endpoint = "https://api.bing.microsoft.com/v7.0/search"
        headers = {"Ocp-Apim-Subscription-Key": self.bing_api_key}
        params = {"q": query, "mkt": "global"}

        try:
            response = requests.get(endpoint, headers=headers, params=params)
            response.raise_for_status()
            search_results = response.json()

            results = []
            for result in search_results.get('webPages', {}).get('value', []):
                results.append({
                    "file_name": "Bing",
                    "chunk_text": result.get('snippet'),
                    "distance": 0.9,
                    "search_type": "web",
                    "url": result.get('displayUrl')
                })
            return results
        except requests.exceptions.RequestException as e:
            print(f"Error in Bing search: {e}")
            return []

    def search_google(self, query: str) -> List[Dict[str, Any]]:
        url = "https://www.googleapis.com/customsearch/v1"
        params = {
            "key": self.google_api_key,
            "cx": self.google_search_engine_id,
            "q": query
        }

        try:
            response = requests.get(url, params=params)
            response.raise_for_status()
            search_results = response.json()

            results = []
            for item in search_results.get('items', []):
                results.append({
                    "file_name": "Google",
                    "chunk_text": item.get('snippet'),
                    "distance": 0.9,
                    "search_type": "web",
                    "url": item.get('link')
                })
            return results
        except requests.exceptions.RequestException as e:
            print(f"Error in Google search: {e}")
            return []

    def search_linkup(self, query: str) -> List[Dict[str, Any]]:
        endpoint = "https://api.linkup.so/v1/search"
        params = {
            "q": query,
            "depth": "standard",
            "outputType": "searchResults"
        }
        headers = {
            "Authorization": f"Bearer {self.linkup_api_key}"
        }

        try:
            response = requests.get(endpoint, headers=headers, params=params)
            response.raise_for_status()
            search_results = response.json()

            results = []
            for result in search_results.get('results', []):
                results.append({
                    "file_name": "Linkup",
                    "chunk_text": result.get('content'),
                    "distance": 0.9,
                    "search_type": "web",
                    "url": result.get('url')
                })
            return results
        except requests.exceptions.RequestException as e:
            print(f"Error in Linkup search: {e}")
            return []

    def search_exa(self, query: str) -> List[Dict[str, Any]]:
        endpoint = "https://api.exa.ai/search"
        headers = {
            "accept": "application/json",
            "content-type": "application/json",
            "x-api-key": self.exa_api_key
        }
        data = {
            "query": query,
            "type": "auto",
            "useAutoprompt": True,
            "numResults": 10,
            "contents": {
                "summary": True
            }
        }

        try:
            response = requests.post(endpoint, headers=headers, json=data)
            response.raise_for_status()
            search_results = response.json()

            results = []
            for result in search_results.get('results', []):
                results.append({
                    "file_name": "Exa",
                    "chunk_text": result.get('summary'),
                    "distance": 0.9,
                    "search_type": "web",
                    "url": result.get('url')
                })
            return results
        except requests.exceptions.RequestException as e:
            print(f"Error in Exa search: {e}")
            return []


    def search(self, engine: str, query: str) -> List[Dict[str, Any]]:
        if engine == "tavily":
            return self.search_tavily(query)
        elif engine == "serper":
            return self.search_serper(query)
        elif engine == "bing":
            return self.search_bing(query)
        elif engine == "google":
            return self.search_google(query)
        elif engine == "linkup":
            return self.search_linkup(query)
        elif engine == "exa":
            return self.search_exa(query)
        else:
            return [] 