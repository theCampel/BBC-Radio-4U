from openai import OpenAI
import os
import src.spotify_handler as spotify_handler
from .constants import RADIO_SYSTEM_PROMPT, SONG_DIALOGUE_PROMPT

class DialogueGenerator:
    def __init__(self):
        self.client = OpenAI(api_key=os.getenv('OPENAI_API_KEY'))
        self.SYSTEM_PROMPT = RADIO_SYSTEM_PROMPT

    def generate_dialogue(self, article, song_info):
        """
        Generate dialogue based on the article and song info
        Args:
            article (str): The news article text
            song_info (dict, optional): Dictionary containing song name and artist
        Returns:
            list: List of dialogue speeches
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
            if 'MATT:' in line:
                speeches.append(line.replace('MATT:', '').strip())
            elif 'MOLLIE:' in line:
                speeches.append(line.replace('MOLLIE:', '').strip())
        
        return speeches 

    def generate_song_dialogue(self, song_name, artist, next_song_name=None, next_artist=None):
        """
        Generate a very short dialogue about the song that just played and optionally announce the next song
        
        Args:
            song_name (str): Name of the song that just played
            artist (str): Artist of the song that just played
            next_song_name (str, optional): Name of the next song to play
            next_artist (str, optional): Artist of the next song
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
                    "role": "user", "content": prompt
                }
            ]
        )
        dialogue = response.choices[0].message.content
        speeches = []
        
        for line in dialogue.split('\n'):
            if 'MATT:' in line:
                speeches.append(line.replace('MATT:', '').strip())
            elif 'MOLLIE:' in line:
                speeches.append(line.replace('MOLLIE:', '').strip())
        
        return speeches