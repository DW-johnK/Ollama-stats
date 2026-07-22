#!/usr/bin/env python3
"""
Scrape Ollama models from their search interface.
Extract metadata including owner, size variants, pull counts, and capabilities.
Designed to go deep into pagination (20+ pages) to capture the most popular models.
"""

import requests
from typing import Dict, List, Optional
from urllib.parse import urljoin
import time
import re
import json


class OllamaScrape:
    """Comprehensive scraper for Ollama model data."""
    
    def __init__(self, delay: float = 1.0):
        self.delay = delay
        self.session = requests.Session()
        self.session.headers.update({
             "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36"
        })

    def scrape_from_api(self, limit=200):
        """Try to fetch models from Ollama API directly."""
        url = "https://ollama.com/api/tags"
        
        try:
            response = requests.get(url, headers=self.session.headers)
            if response.status_code == 200:
                data = response.json()
                return data.get("models", [])
        except Exception as e:
            print(f"API call failed: {e}")
        
        return []

    def scrape_library_page(self):
        """Scrape the library page for model information."""
        # Will use browser automation to extract all model cards
        pass

if __name__ == "__main__":
    scraper = OllamaScrape()
    models = scraper.scrape_from_api(limit=50)
    if models:
        print(f"Found {len(models)} models")
        for m in models[:10]:
            print(f"  - {m}")
