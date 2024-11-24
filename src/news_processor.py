from openai import OpenAI
import os

class NewsProcessor:
    def __init__(self):
        self.client = OpenAI(api_key=os.getenv('OPENAI_API_KEY'))

    def summarise(self, article):
        response = self.client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {
                    "role": "system",
                    "content": "You are a professional news summariser. Create concise, engaging summaries."
                },
                {
                    "role": "user",
                    "content": f"Please summarise this news article: {article}"
                }
            ]
        )
        return response.choices[0].message.content 