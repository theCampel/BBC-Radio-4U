import os
from dotenv import load_dotenv
from src.news_processor import NewsProcessor
from src.dialogue_generator import DialogueGenerator
from src.voice_generator import VoiceGenerator

load_dotenv()

# Sample news article (hardcoded for now)
SAMPLE_ARTICLE = """
Tesla has unveiled its latest electric vehicle model, promising unprecedented range and innovative features. 
The new model, set to hit markets in 2024, boasts a range of over 500 miles on a single charge and 
introduces autonomous driving capabilities that surpass current industry standards.
"""

def main():
    news_processor = NewsProcessor() # TODO: I'm getting to it
    dialogue_generator = DialogueGenerator()
    voice_generator = VoiceGenerator()

    # Process the news and generate dialogue
    summary = SAMPLE_ARTICLE  # news_processor.summarise(SAMPLE_ARTICLE)
    print(f"Summary:\n{summary}")
    speeches = dialogue_generator.generate_dialogue(summary)
    print(f"Generated dialogue, starting audio generation and playback...")
    
    # Generate and play audio in parallel
    voice_generator.generate_and_play(speeches)

if __name__ == "__main__":
    main()
