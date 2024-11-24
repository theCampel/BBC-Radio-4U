from openai import OpenAI
import os

class DialogueGenerator:
    # Used for testing cos OpenAI is expensive lol
    SYSTEM_PROMPT = """
<instructions>
- You are a conversational AI designed to generate realistic conversations between two engaging, and humorous radio hosts, similar to those on BBC Radio 1. 
- You will be given  a news article, summarised or in full, and you will create a lively dialogue between two hosts, Matt and Mollie. 
- You will maintain their style and tone described in <conversation_style> and <hosts_personalities>
</instructions>

<conversation_style>
- The hosts have AMAZING chemistry. 
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
    
    HARD_CODED_RESPONSE = """
</MUSIC_ENDS>
MATT: Well, well, well, Mollie! It seems Tesla is out here living their best life, unveiling a new electric vehicle that promises more range than my personal life!

MOLLIE: Ha! Right? Over 500 miles on a single charge? That’s like driving to the moon and back—or at least to the nearest coffee shop and not running out of battery! 

MATT: Exactly! I mean, I can't even make it through a Netflix binge without needing a snack, let alone a road trip. They should include a snack dispenser in that car—now that would be a game changer!

MOLLIE: Oh! Imagine the “Tesla-muncher” feature! Like, “What’s that? Snacks every 100 miles? Now that’s my kind of road trip!” 

MATT: And let's not forget the autonomous driving features! At this point, the car will practically do your grocery shopping for you. “Sorry Mum, I can't pick you up. My car's busy updating itself!”

MOLLIE: Right? And you’ll finally be able to sit back and relax without worrying about being stuck behind a tortoise-driving grandma. If only the car could do my taxes too, I’d be sorted!

MATT: Someone's gotta pitch that idea! But seriously, folks, think about it. A Tesla that drives itself while you catch up on the latest episode of your favourite series. Sounds dreamy, doesn’t it? 

MOLLIE: It really does! So, listeners, what's the first thing you'd watch on autopilot? Message us @bbc_radio_4u with your binge-watch list while we all pray for these cars to ship sooner rather than later!

MATT: Don’t forget, plan your snack menu while you’re at it! Who knows what the future holds? Snacks and streaming, the ultimate combo! 
<MUSIC_BEGINS>
"""

    def __init__(self):
        self.client = OpenAI(api_key=os.getenv('OPENAI_API_KEY'))

    def generate_dialogue(self, summary):
        response = self.client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {
                    "role": "system",
                    "content": self.SYSTEM_PROMPT
                },
                {
                    "role": "user",
                    "content": f"Create a dialogue about this news: {summary}"
                }
            ]
        )
        
        # dialogue = self.HARD_CODED_RESPONSE #response.choices[0].message.content
        dialogue = response.choices[0].message.content
        speeches = []
        
        for line in dialogue.split('\n'):
            if 'MATT:' in line:
                speeches.append(line.replace('MATT:', '').strip())
            elif 'MOLLIE:' in line:
                speeches.append(line.replace('MOLLIE:', '').strip())
        
        return speeches 