import os
from dotenv import load_dotenv
from src.news_processor import NewsProcessor
from src.dialogue_generator import DialogueGenerator
from src.voice_generator import VoiceGenerator
from src.spotify_handler import SpotifyHandler
from src.source_selector import SourceSelector

load_dotenv()

def main():
    source_selector = SourceSelector()
    selected_sources = source_selector.get_user_selection()
    
    print("\nSelected sources: ")
    for source_name, _, articles in selected_sources:
        print(f"- {source_name} ({articles} articles)")
    
    news_processor = NewsProcessor()
    news_processor.process_selected_sources(selected_sources)
    
    dialogue_generator = DialogueGenerator()
    voice_generator = VoiceGenerator()
    spotify_handler = SpotifyHandler(username="leo.camacho1738")

    # Get articles and let user choose
    articles = news_processor.get_latest_articles()
    
    if not articles:
        print("No articles found. Please try again.")
        return
    
    print("\nAvailable articles:")
    for i, article in enumerate(articles, 1):
        print(f"{i}: {article['title']} (from {article['source']})")
    
    while True:
        try:
            selection = int(input("\nSelect an article number to listen to: ")) - 1
            if 0 <= selection < len(articles):
                selected_article = articles[selection]
                break
            print("Invalid selection. Please try again.")
        except ValueError:
            print("Please enter a valid number.")

    # Get a random top song
    random_song = spotify_handler.get_random_top_song()
    print(f"\nSelected song: {random_song['name']} by {random_song['artist']}")

    print(f"\nSelected article: {selected_article['title']} \n {selected_article['full_text']}")
    summarised_article = news_processor.summarise_selected_article(selected_article)
    print(f"\nSummarised article: {summarised_article}")


    speeches = dialogue_generator.generate_dialogue(summarised_article, random_song)
    print(f"\nGenerated speeches: {speeches}")
    voice_generator.generate_and_play(speeches)
    
    print(f"\nNow playing: {random_song['name']} by {random_song['artist']}")
    spotify_handler.play_track(random_song['uri'])

if __name__ == "__main__":
    main()
