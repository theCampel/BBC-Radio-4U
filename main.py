import os
import sys
from dotenv import load_dotenv
import argparse
import time
import queue
from threading import Thread
import random

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
    """Play dialogues (list of text strings) by generating voice and playing them."""
    visualiser.init_display()

    speech_queue = queue.Queue()
    gen_thread = Thread(target=voice_generator.generate_to_queue, args=(speeches, speech_queue))
    gen_thread.start()

    audio_player.play_from_queue(speech_queue)

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

def build_initial_queue(dummy_mode, spotify_handler, news_processor=None, dialogue_generator=None):
    """
    Build an initial queue of items to play.
    For now, we hardcode:
    1. Conversation about a random news article from The Verge (if not dummy)
    2. One track from a playlist
    3. Conversation about that track
    4. Another track
    etc.

    Each queue item is a dict:
    { "type": "conversation", "data": [list_of_speeches] }
    or
    { "type": "song", "data": {"uri": spotify_uri, "name":..., "artist":...} }

    In dummy mode, we just load some dummy speeches and alternate with tracks.
    """
    play_queue = []

    if dummy_mode:
        # Load dummy speeches from ./speeches
        speeches_folder = "./speeches"
        if not os.path.isdir(speeches_folder):
            print(f"Speeches folder not found at {speeches_folder}")
            sys.exit(1)

        speech_files = sorted([f for f in os.listdir(speeches_folder) if f.endswith('.mp3')])
        if not speech_files:
            print("No speech files found in the speeches folder.")
            sys.exit(1)

        # Convert them into conversation queue items
        dummy_speeches = []
        for f in speech_files:
            speaker = 'default'
            fname_lower = f.lower()
            if 'matt' in fname_lower:
                speaker = 'matt'
            elif 'mollie' in fname_lower:
                speaker = 'mollie'
            dummy_speeches.append((os.path.join(speeches_folder, f), speaker))

        # We'll put them in one conversation item
        play_queue.append({
            "type": "conversation_pre_recorded",
            "data": dummy_speeches
        })

        # Then add a random top track
        random_song = spotify_handler.get_random_top_song()
        play_queue.append({
            "type": "song",
            "data": random_song
        })

        # Add a conversation about next upcoming track
        # We'll dynamically generate this later when we know the next track
        # For now, just leave two items: conversation, track.
        # We'll loop and add more items as we go if needed.

    else:
        # Normal mode: 
        # Assume user selection and summarisation has happened outside or call it here
        articles = news_processor.get_latest_articles()
        if not articles:
            print("No articles found. Please try again.")
            sys.exit(1)

        # Pick a random article from The Verge (for now)
        # Or let user pick one
        # Let's just pick a random article:
        selected_article = random.choice(articles)
        summarised_article = news_processor.summarise_selected_article(selected_article)
        
        # Pick a random song
        random_song = spotify_handler.get_random_top_song()
        dialogues = dialogue_generator.generate_dialogue(summarised_article, random_song)

        # Add a conversation item
        play_queue.append({
            "type": "conversation",
            "data": dialogues
        })

        # Add the track item
        play_queue.append({
            "type": "song",
            "data": random_song
        })

        # Later we can add end-of-song dialogues and next track dynamically

    return play_queue

def print_queue_status(play_queue, current_index):
    """Helper function to print the current state of the queue."""
    print("\n=== Current Queue Status ===")
    print(f"Current index: {current_index}")
    for i, item in enumerate(play_queue):
        prefix = "→" if i == current_index else " "
        if item["type"] == "song":
            print(f"{prefix} {i}. [{item['type']}] {item['data']['name']} by {item['data']['artist']}")
        else:
            print(f"{prefix} {i}. [{item['type']}] {len(item['data'])} speeches")
    print("========================\n")

def main():
    args = parse_arguments()
    dummy_mode = args.dummy

    visualiser = Visualiser()
    audio_player = AudioPlayer(visualiser=visualiser)
    voice_generator = VoiceGenerator()
    spotify_handler = SpotifyHandler(username="leo.camacho1738")

    if dummy_mode:
        # Dummy mode: no article selection
        play_queue = build_initial_queue(dummy_mode=True, spotify_handler=spotify_handler)
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

        play_queue = build_initial_queue(
            dummy_mode=False, 
            spotify_handler=spotify_handler, 
            news_processor=news_processor, 
            dialogue_generator=dialogue_generator
        )

    

    # Main loop: process items in the queue indefinitely
    # Once we reach near the end of a song, we will add a next conversation and next track
    current_index = 0
    end_dialogue_generated = False
    next_song_info = None

    print_queue_status(play_queue, current_index)

    while True:
        if current_index >= len(play_queue):
            # Rebuild or add more items to the queue if needed
            # For now, just break or re-initialise:
            print("Queue ended. Re-building the queue...")
            # Could add logic to refill or pick new items:
            if dummy_mode:
                # Just pick a new random track and end dialogues
                random_song = spotify_handler.get_random_top_song()
                play_queue.append({"type": "song", "data": random_song})
            else:
                # In normal mode, let's pick a new article and a new track:
                articles = news_processor.get_latest_articles()
                if articles:
                    selected_article = random.choice(articles)
                    summarised_article = news_processor.summarise_selected_article(selected_article)
                    random_song = spotify_handler.get_random_top_song()
                    dialogues = dialogue_generator.generate_dialogue(summarised_article, random_song)
                    play_queue.append({"type": "conversation", "data": dialogues})
                    play_queue.append({"type": "song", "data": random_song})
            current_index = 0
            print_queue_status(play_queue, current_index)

        item = play_queue[current_index]
        current_index += 1

        if item["type"] == "conversation":
            # item["data"] is a list of speeches
            print("\nPlaying conversation:")
            for idx, speech in enumerate(item["data"], start=1):
                print(f"Speaker {idx}: {speech}")
            play_dialogues(item["data"], visualiser, voice_generator, audio_player)
            end_dialogue_generated = False

        elif item["type"] == "conversation_pre_recorded":
            # item["data"] is a list of (file, speaker)
            print("\nPlaying pre-recorded conversation:")
            play_pre_recorded_dialogues(item["data"], visualiser, audio_player)
            end_dialogue_generated = False

        elif item["type"] == "song":
            song = item["data"]
            print(f"\nNow playing: {song['name']} by {song['artist']}")
            spotify_handler.play_track(song['uri'])
            print_queue_status(play_queue, current_index)
            end_dialogue_generated = False
            # Wait for the track to nearly finish, then inject next conversation and track
            while True:
                remaining_time = spotify_handler.get_remaining_time()
                if remaining_time is None:
                    print("Playback stopped unexpectedly.")
                    break

                if remaining_time < 10000 and not end_dialogue_generated:
                    # Time to queue a conversation about this track and a next track
                    next_song = spotify_handler.get_random_top_song()
                    while next_song and next_song['uri'] == song['uri']:
                        next_song = spotify_handler.get_random_top_song()

                    # If not dummy, generate a dialogue about the song:
                    if not dummy_mode:
                        # We have dialogue_generator from above
                        # If we started in dummy mode, no dialogue_generator is available
                        # Just skip if dummy
                        song_dialogue = dialogue_generator.generate_song_dialogue(
                            song['name'], song['artist'],
                            next_song['name'], next_song['artist']
                        )
                        # Insert the conversation and next track after the current index
                        play_queue.insert(current_index, {"type": "song", "data": next_song})
                        play_queue.insert(current_index, {"type": "conversation", "data": song_dialogue})
                        print_queue_status(play_queue, current_index)
                    else:
                        # Dummy mode: just a simple conversation
                        end_speeches = [
                            "That was a great track, wasn't it?",
                            f"Up next, we have {next_song['name']} by {next_song['artist']}"
                        ]
                        play_queue.insert(current_index, {"type": "song", "data": next_song})
                        play_queue.insert(current_index, {"type": "conversation", "data": end_speeches})

                    end_dialogue_generated = True
                    print_queue_status(play_queue, current_index)

                if remaining_time is not None and remaining_time < 1000:
                    # Track finished
                    break

                time.sleep(1)

        else:
            print(f"Unknown queue item type: {item['type']}")

    # End main while True

if __name__ == "__main__":
    main()
