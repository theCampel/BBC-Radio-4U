from openai import OpenAI
import os
import feedparser
from typing import List, Dict, Any
from .rss_fetcher import RSSFetcher

# TODO: Make this not suck. 
class NewsProcessor:
    def __init__(self):
        self.client = OpenAI(api_key=os.getenv('OPENAI_API_KEY'))
        self.rss_fetcher = RSSFetcher([])  # Initialise with empty list as we'll use it for fetching only
        
        # Terrible prompt. Works for now.
        self.SYSTEM_PROMPT = """
        You're a news aggregator. You will be given a news article, summarise it in MAX 8 bullet points. 
        - Write in a clear, high-entropy style. 
        """

        self.articles = []

    def process_selected_sources(self, selected_sources: List[tuple[str, str, int]]) -> None:
        """
        Process the selected sources and store their articles.
        Args:
            selected_sources: List of tuples (source_name, source_url, num_articles)
        """
        self.articles = []
        
        for source_name, source_url, num_articles in selected_sources:
            try:
                feed = feedparser.parse(source_url)
                # Get the specified number of articles from this source
                source_articles = feed.entries[:num_articles]
                
                for entry in source_articles:
                    # Fetch full text using RSSFetcher
                    full_text = self.rss_fetcher.fetch_full_text(entry.link)
                    
                    article = {
                        'title': entry.title,
                        'summary': entry.get('summary', ''),
                        'full_text': full_text,  # Add full text
                        'link': entry.link,
                        'source': source_name
                    }
                    self.articles.append(article)
                    
            except Exception as e:
                print(f"Error processing {source_name}: {e}")

    def get_latest_articles(self) -> List[Dict[str, Any]]:
        """Return all processed articles."""
        return self.articles

    def summarise_selected_article(self, selected_article: Dict[str, str]) -> str:
        """Ok update. Currently we get the user to choose the article
        they'd like to learn about from the radioheads. What if instead, 
        we get a small LLM to filter them by order of interesting-ness?
        Then we slowly work our way through the top interesting ones. Genius."""
        
        # Use full text if available, otherwise fall back to summary
        article_content = selected_article.get('full_text') or selected_article.get('summary', '')
        
        response = self.client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {
                    "role": "system",
                    "content": self.SYSTEM_PROMPT
                },
                {
                    "role": "user",
                    "content": f"Summarise this news article:\nTitle: {selected_article['title']}\nContent: {article_content}"
                }
            ]
        )
        return response.choices[0].message.content