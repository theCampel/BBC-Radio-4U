import feedparser
import requests
from bs4 import BeautifulSoup
from typing import Optional, Dict

class RSSFetcher:
    """"""
    def __init__(self, rss_urls: list[str]):
        self.rss_urls = rss_urls

    def fetch_full_text(self, url: str) -> str:
        """Fetch the full-text article from the given URL."""
        try:
            response = requests.get(url)
            response.raise_for_status()
            
            soup = BeautifulSoup(response.content, 'html.parser')
            
            content_selectors = ['article', 'main', '.article-content', '.story-content']
            
            for selector in content_selectors:
                content = soup.select_one(selector)
                if content:
                    # Remove unwanted elements
                    for tag in content.find_all(['script', 'style', 'nav', 'header', 'footer']):
                        tag.decompose()
                    
                    # Clean up the text
                    text = ' '.join(content.get_text(separator=' ').split())
                    return text
                    
            return soup.get_text(separator=' ')  # Fallback to full page text
            
        except Exception as e:
            return f"Error fetching article: {str(e)}"
