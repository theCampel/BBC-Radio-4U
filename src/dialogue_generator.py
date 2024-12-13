from openai import OpenAI
import os
from .constants import RADIO_SYSTEM_PROMPT, SONG_DIALOGUE_PROMPT, NEWS_SUMMARY_PROMPT

class DialogueGenerator:
    def __init__(self):
        self.client = OpenAI(api_key=os.getenv('OPENAI_API_KEY'))
        self.RADIO_SYSTEM_PROMPT = RADIO_SYSTEM_PROMPT

    def generate_dialogue_for_news(self, summarised_article):
        """
        Generate a conversation about a news article's summary.
        """
        response = self.client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {
                    "role": "system",
                    "content": self.RADIO_SYSTEM_PROMPT
                },
                {
                    "role": "user",
                    "content": f"Create a radio host style conversation about the following news summary:\n\n{summarised_article}\n"
                }
            ]
        )
        
        dialogue = response.choices[0].message.content
        speeches = []
        
        for line in dialogue.split('\n'):
            if 'MATT:' in line.upper():
                speeches.append(line.split(':',1)[1].strip())
            elif 'MOLLIE:' in line.upper():
                speeches.append(line.split(':',1)[1].strip())
        
        return speeches

    def summarise_article_for_dialogue(self, article):
        """Summarise the article content for use in generating a conversation."""
        article_content = article.get('full_text') or article.get('summary', '')
        response = self.client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {
                    "role": "system",
                    "content": NEWS_SUMMARY_PROMPT
                },
                {
                    "role": "user",
                    "content": f"Summarise this news article:\nTitle: {article['title']}\nContent: {article_content}"
                }
            ]
        )
        return response.choices[0].message.content

    def generate_dialogue(self, article, song_info):
        """
        Old method: Generate dialogue about article and song.
        Not used now, but kept for reference.
        """
        response = self.client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {
                    "role": "system",
                    "content": self.SYSTEM_PROMPT
                },
                {
                    "role": "user",
                    "content": f"Create a dialogue about the following:\n <song_context>{song_info}</song_context>\n<news_summary>{article}</news_summary>\n "
                }
            ]
        )
        
        dialogue = response.choices[0].message.content
        speeches = []
        
        for line in dialogue.split('\n'):
            if 'MATT:' in line.upper():
                speeches.append(line.split(':',1)[1].strip())
            elif 'MOLLIE:' in line.upper():
                speeches.append(line.split(':',1)[1].strip())
        
        return speeches 

    def generate_song_dialogue(self, song_name, artist, next_song_name=None, next_artist=None):
        """
        Generate a very short dialogue about the song that just played and optionally announce the next song.
        """
        prompt = f"Generate a dialogue about the song '{song_name}' by {artist} that just finished playing."
        if next_song_name and next_artist:
            prompt += f" Then smoothly transition and announce that '{next_song_name}' by {next_artist} is coming up next."

        response = self.client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {
                    "role": "system",
                    "content": SONG_DIALOGUE_PROMPT
                },
                {
                    "role": "user", 
                    "content": prompt
                }
            ]
        )
        dialogue = response.choices[0].message.content
        speeches = []
        
        for line in dialogue.split('\n'):
            if 'MATT:' in line.upper():
                speeches.append(line.split(':',1)[1].strip())
            elif 'MOLLIE:' in line.upper():
                speeches.append(line.split(':',1)[1].strip())
        
        return speeches
