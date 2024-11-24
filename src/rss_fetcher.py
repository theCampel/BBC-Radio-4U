import feedparser
import requests
from bs4 import BeautifulSoup
from typing import Optional, Dict

class RSSFetcher:
    def __init__(self, rss_urls: list[str]):
        self.rss_urls = rss_urls

    def fetch_full_text(self, url: str) -> str:
        """Fetch the full-text article from the given URL."""
        try:
            response = requests.get(url)
            response.raise_for_status()
            
            soup = BeautifulSoup(response.content, 'html.parser')
            
            # Try different content selectors (customize based on target sites)
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

    def get_latest_articles(self, n: int = 5) -> list[Dict[str, str]]:
        """Fetch and return the latest n articles from hardcoded RSS feeds."""
        articles = []
        
        for rss_url in self.rss_urls:
            try:
                feed = feedparser.parse(rss_url)
                
                if feed.bozo == 0 and feed.entries:
                    # Get the n latest entries from this feed
                    latest_entries = feed.entries[:n]
                    
                    for entry in latest_entries:
                        full_text = self.fetch_full_text(entry.link)
                        articles.append({
                            'title': entry.title,
                            'text': full_text,
                            'url': entry.link
                        })
                        
                        # Stop if we've reached desired number of articles
                        if len(articles) >= n:
                            return articles
                    
            except Exception as e:
                print(f"Error processing feed {rss_url}: {str(e)}")
                continue
                
        return articles 