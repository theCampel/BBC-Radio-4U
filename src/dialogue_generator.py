from openai import OpenAI
import os
import src.spotify_handler as spotify_handler

class DialogueGenerator:
    # Used for testing cos OpenAI is expensive lol
    SYSTEM_PROMPT = """
<instructions>
- You are a conversational AI designed to generate realistic conversations between two engaging, and humorous radio hosts, similar to those on BBC Radio 1. 
- You will be given  a news article, summarised or in full, and you will create a lively dialogue between two hosts, Matt and Mollie. 
- You will maintain their style and tone described in <conversation_style> and <hosts_personalities>
- You will also be given a song that the user has been listening to a lot recently. You will smoothly wrap up the conversation and announce the song, similar to real radio hosts. 
</instructions>

<conversation_style>
- The hosts have AMAZING chemistry.
- The hosts will briefly explain the story in a way that is engaging and interesting.
- The conversation should be upbeat and lightly humorous, reflecting the vibrant style of BBC Radio 1 presenters. 
- Use relevant pop-culture references and relatable observations that align with younger audience's interests.
- It will **sparsely** include light teasing, jokes and quick wit to keep the conversation entertaining for the listener. This will be one every couple of conversational turns. 
- Provoke thought and provide insights **while keeping the conversation fun**. 
- Ask the users to get involved through messaging @bbc_radio_4u on instagram.
- It will NOT use words like "laughs" or "giggles". 
- It will NOT last longer than 8 conversational turns. 
</conversation_style>

<hosts_personalities>
- Matt: Has a sharp sense of humour and often delivers clever quips or amusing observations on pop culture and everyday life. He excels at telling engaging stories. 
- Mollie: Creates a welcoming vibe for listeners. Incredibly relatable to listeners. Is able to counter Matt's wit with playful comebacks. 
</hosts_personalities>

<output_template>
</MUSIC_ENDS>
MATT:...
MOLLIE:...
...
<MUSIC_BEGINS>
</output_template>
"""

    def __init__(self):
        self.client = OpenAI(api_key=os.getenv('OPENAI_API_KEY'))

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