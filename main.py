import os
from dotenv import load_dotenv
from src.news_processor import NewsProcessor
from src.dialogue_generator import DialogueGenerator
from src.voice_generator import VoiceGenerator

load_dotenv()

def main():
    news_processor = NewsProcessor()
    dialogue_generator = DialogueGenerator()
    voice_generator = VoiceGenerator()

    # Fetch the latest news article
    article = news_processor.get_a_summarised_news_article()
    print(f"Summarised article:\n{article}\n")
    
    # Process the news and generate dialogue
    
    # speeches = dialogue_generator.generate_dialogue(article)
    # print(f"Generated dialogue, starting audio generation and playback...")
    
    # Generate and play audio in parallel
    # voice_generator.generate_and_play(speeches)

if __name__ == "__main__":
    main()
