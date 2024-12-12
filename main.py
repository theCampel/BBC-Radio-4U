import os
import sys
from dotenv import load_dotenv
import argparse
import time

# Only import these if not dummy mode
from src.news_processor import NewsProcessor
from src.dialogue_generator import DialogueGenerator
from src.voice_generator import VoiceGenerator
from src.spotify_handler import SpotifyHandler
from src.source_selector import SourceSelector

from src.audio_player import AudioPlayer
from src.visualiser import Visualiser

load_dotenv()

def parse_arguments():
    parser = argparse.ArgumentParser(description='Run the customised radio station.')
    parser.add_argument('--dummy', action='store_true', help='Run in dummy mode using pre-recorded speeches.')
    return parser.parse_args()

def main():
    args = parse_arguments()
    dummy_mode = args.dummy

    if dummy_mode:
        print("Running in dummy mode...")

        # Instead of selecting and processing news and generating dialogue, 
        # we will just play the mp3 files in the speeches folder.
        speeches_folder = "./speeches"
        if not os.path.isdir(speeches_folder):
            print(f"Speeches folder not found at {speeches_folder}")
            return

        # Collect mp3 files in order
        speech_files = sorted([f for f in os.listdir(speeches_folder) if f.endswith('.mp3')])
        if not speech_files:
            print("No speech files found in the speeches folder.")
            return

        # Initialise audio player and visualiser
        visualiser = Visualiser()
        audio_player = AudioPlayer(visualiser=visualiser)

        # Play all speeches in sequence
        audio_player.play_files([os.path.join(speeches_folder, f) for f in speech_files])

    else:
        # Normal mode
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
        summarised_article = news_processor.summarise_selected_article(selected_article)
        print(f"\nSummarised article: {summarised_article}")

        speeches = dialogue_generator.generate_dialogue(summarised_article, random_song)
        print(f"\nGenerated speeches: {speeches}")

        # Initialise visualiser and audio player
        visualiser = Visualiser()
        audio_player = AudioPlayer(visualiser=visualiser)

        # Generate and play the speeches via voice generator
        generated_files = voice_generator.generate_speech_files(speeches)
        audio_player.play_files(generated_files)
        
        print(f"\nNow playing: {random_song['name']} by {random_song['artist']}")
        spotify_handler.play_track(random_song['uri'])
        
        # Monitor song progress and handle end-of-song dialogue
        end_dialogue_generated = False
        while True:
            remaining_time = spotify_handler.get_remaining_time()
            
            if remaining_time is None:
                print("Playback stopped")
                break
                
            if remaining_time < 10000 and not end_dialogue_generated:
                # Get and play next song (ensuring it's different)
                next_song = spotify_handler.get_random_top_song()
                while next_song['uri'] == random_song['uri']:
                    next_song = spotify_handler.get_random_top_song()
                
                song_dialogue = dialogue_generator.generate_song_dialogue(
                    random_song['name'], 
                    random_song['artist'],
                    next_song['name'],
                    next_song['artist']
                )

                print("\nGenerating end-of-song dialogue...")
                end_speech_files = voice_generator.generate_speech_files(song_dialogue)
                audio_player.play_files(end_speech_files)           
                    
                print(f"\nNext up: {next_song['name']} by {next_song['artist']}")
                spotify_handler.play_track(next_song['uri'])
                end_dialogue_generated = True
                
            if remaining_time < 500:  # Song has effectively finished
                break
                
            time.sleep(1)  # Check every second

if __name__ == "__main__":
    main()
