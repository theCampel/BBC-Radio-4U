import os
import sys
from dotenv import load_dotenv
import argparse
import time
import queue
from threading import Thread

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

def play_dialogues(speeches, visualiser, voice_generator, audio_player):
    """Utility function to play dialogues (either generated or dummy).
    Returns after all dialogues are played."""
    # Re-init display for dialogues
    visualiser.init_display()

    speech_queue = queue.Queue()
    gen_thread = Thread(target=voice_generator.generate_to_queue, args=(speeches, speech_queue))
    gen_thread.start()

    # This will block until dialogues are done (when None is received)
    audio_player.play_from_queue(speech_queue)

    # After done, close the visualiser to avoid freezing during music
    visualiser.quit_display()

def play_pre_recorded_dialogues(files_and_speakers, visualiser, audio_player):
    """Play a set of pre-recorded dialogues from a given list of (file, speaker)."""
    visualiser.init_display()

    q = queue.Queue()
    for item in files_and_speakers:
        q.put(item)
    q.put(None)

    audio_player.play_from_queue(q)

    visualiser.quit_display()

def main():
    args = parse_arguments()
    dummy_mode = args.dummy

    visualiser = Visualiser()
    audio_player = AudioPlayer(visualiser=visualiser)
    voice_generator = VoiceGenerator()

    spotify_handler = SpotifyHandler(username="leo.camacho1738")

    if dummy_mode:
        print("Running in dummy mode...")

        # Load the speeches from ./speeches
        speeches_folder = "./speeches"
        if not os.path.isdir(speeches_folder):
            print(f"Speeches folder not found at {speeches_folder}")
            return

        speech_files = sorted([f for f in os.listdir(speeches_folder) if f.endswith('.mp3')])
        if not speech_files:
            print("No speech files found in the speeches folder.")
            return

        # Assign speakers based on filename
        dummy_speeches = []
        for f in speech_files:
            speaker = 'default'
            fname_lower = f.lower()
            if 'matt' in fname_lower:
                speaker = 'matt'
            elif 'mollie' in fname_lower:
                speaker = 'mollie'
            dummy_speeches.append((os.path.join(speeches_folder, f), speaker))

        # Play all dummy speeches (conversation)
        play_pre_recorded_dialogues(dummy_speeches, visualiser, audio_player)

        # After finishing conversation, play a Spotify track
        random_song = spotify_handler.get_random_top_song()
        print(f"\nNow playing: {random_song['name']} by {random_song['artist']}")
        spotify_handler.play_track(random_song['uri'])

        end_dialogue_generated = False

        while True:
            remaining_time = spotify_handler.get_remaining_time()

            if remaining_time is None:
                print("Playback stopped")
                break

            # When less than 10s left, play short dialogue about next track
            if remaining_time < 10000 and not end_dialogue_generated:
                next_song = spotify_handler.get_random_top_song()
                while next_song['uri'] == random_song['uri']:
                    next_song = spotify_handler.get_random_top_song()

                end_speeches = [
                    "That was a great track, wasn't it?",
                    f"Up next, we have {next_song['name']} by {next_song['artist']}"
                ]

                # Play these end_of_song dialogues
                # Use play_dialogues to ensure blocking until done
                play_dialogues(end_speeches, visualiser, voice_generator, audio_player)

                print(f"\nNext up: {next_song['name']} by {next_song['artist']}")
                spotify_handler.play_track(next_song['uri'])
                end_dialogue_generated = True

            if remaining_time < 500:
                break

            # Here we are not updating the visualiser for the music track (no dialogues)
            # The window is closed, so no freeze.
            time.sleep(1)

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

        random_song = spotify_handler.get_random_top_song()
        summarised_article = news_processor.summarise_selected_article(selected_article)
        print(f"\nSummarised article: {summarised_article}")

        speeches = dialogue_generator.generate_dialogue(summarised_article, random_song)
        print(f"\nGenerated speeches: {speeches}")

        # Play main dialogues
        play_dialogues(speeches, visualiser, voice_generator, audio_player)

        print(f"\nNow playing: {random_song['name']} by {random_song['artist']}")
        spotify_handler.play_track(random_song['uri'])

        end_dialogue_generated = False
        while True:
            remaining_time = spotify_handler.get_remaining_time()

            if remaining_time is None:
                print("Playback stopped")
                break

            if remaining_time < 10000 and not end_dialogue_generated:
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

                # Play end_of_song dialogues
                play_dialogues(song_dialogue, visualiser, voice_generator, audio_player)

                print(f"\nNext up: {next_song['name']} by {next_song['artist']}")
                spotify_handler.play_track(next_song['uri'])
                end_dialogue_generated = True

            if remaining_time < 500:
                break

            # Again, no dialogues here, visualiser is closed. No freeze.
            time.sleep(1)

if __name__ == "__main__":
    main()
