from openai import OpenAI
import os
from .rss_fetcher import RSSFetcher

# TODO: Make this not suck. 
class NewsProcessor:
    def __init__(self):
        self.client = OpenAI(api_key=os.getenv('OPENAI_API_KEY'))

        # Terrible prompt. Works for now.
        self.SYSTEM_PROMPT = """
        You're a news aggregator. Given a list of news articles, pick the most interesting one and summarise it.
        For choosing an interesting article, pick the one that would create the best conversation. 
        Avoid advertising articles.
        Provide your summarisation in a list of 7 bullet points max. 
        Write in a clear, high-entropy style. 
        """

        self.rss_feeds = [
            "https://www.wired.com/feed/rss",
            #"https://rss.nytimes.com/services/xml/rss/nyt/Technology.xml",
            
        ]
        self.rss_fetcher = RSSFetcher(self.rss_feeds)

    def get_a_summarised_news_article(self) -> str:
        """Pick the most interesting article from an overly 
        bloated list and summarise it. Ok let's be honest. This is a 
        terrible way of doing it - it's incredibly expensive. But 
        do the simplest thing that could possibly work first and then improve right?
        Ideally, we'd have a microllm to pick an interesting title
        and then another super lightweight llm to summarise it. Then this 
        get's fed into the dialogue generator. Currently, we're 
        unncessarily raising costs by an order of magnitude. (still very
        cheap compared to the voice generation costs though.)"""

        response = self.client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {
                    "role": "system",
                    "content": self.SYSTEM_PROMPT
                },
                {
                    "role": "user",
                    "content": f"Create a dialogue about this news: {self.rss_fetcher.get_latest_articles(5)}"
                }
            ]
        )
        return response.choices[0].message.content