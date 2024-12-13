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

def build_initial_queue(dummy_mode, spotify_handler, news_processor=None):
    """
    Build the initial queue of items to play according to the new specification:
    - 3 songs (random from given playlist), 
    - a conversation placeholder for describing the 3rd song,
    - another 3 songs (random from the same playlist, no repeats),
    - a conversation placeholder for describing a random article from The Verge.

    No actual GPT or audio generation here - just placeholders.
    """

    play_queue = []
    played_songs = []  # Keep track of songs played so we don't repeat

    # Hardcoded playlist ID as requested
    playlist_id = "0NvNQWJaSUTBTQjhjWbNfL"

    def get_unique_random_song():
        song = spotify_handler.get_random_playlist_song(playlist_id, played_songs)
        if song is None:
            print("No more unique songs found in the playlist. Exiting.")
            sys.exit(1)
        played_songs.append(song['uri'])
        return song

    # First 3 songs
    first_3_songs = [get_unique_random_song() for _ in range(3)]
    for s in first_3_songs:
        play_queue.append({"type": "song", "data": s})

    # Conversation placeholder about the 3rd song
    # We store the needed info in the placeholder, but do not generate yet.
    third_song = first_3_songs[-1]
    play_queue.append({
        "type": "conversation_placeholder",
        "data": {
            "type": "song_description",
            "song_name": third_song["name"],
            "artist": third_song["artist"]
        }
    })

    # Next 3 songs
    next_3_songs = [get_unique_random_song() for _ in range(3)]
    for s in next_3_songs:
        play_queue.append({"type": "song", "data": s})

    # Conversation placeholder for a random article
    # We pick the article now (random from The Verge or from processed articles),
    # but we won't generate the conversation until it's needed.
    if not dummy_mode and news_processor:
        articles = news_processor.get_latest_articles()
        if not articles:
            print("No articles found for news conversation. Please try again.")
            sys.exit(1)
        selected_article = random.choice(articles)
        play_queue.append({
            "type": "conversation_placeholder",
            "data": {
                "type": "news_description",
                "article": selected_article
            }
        })
    else:
        # Dummy mode or no news_processor: just skip article conversation
        # Or add a dummy placeholder if desired
        play_queue.append({
            "type": "conversation_placeholder",
            "data": {
                "type": "news_description",
                "article": {
                    "title": "Dummy Article",
                    "summary": "This is a dummy summary",
                    "link": "http://example.com",
                    "full_text": "This is dummy full text."
                }
            }
        })

    return play_queue, played_songs

def print_queue_status(play_queue, current_index):
    """Helper function to print the current state of the queue."""
    print("\n=== Current Queue Status ===")
    print(f"Current index: {current_index}")
    for i, item in enumerate(play_queue):
        prefix = "→" if i == current_index - 1 else " "
        if item["type"] == "song":
            print(f"{prefix} {i+1}. [song] {item['data']['name']} by {item['data']['artist']}")
        elif item["type"] == "conversation":
            print(f"{prefix} {i+1}. [conversation] {len(item['data'])} speeches")
        elif item["type"] == "conversation_pre_recorded":
            print(f"{prefix} {i+1}. [conversation_pre_recorded] {len(item['data'])} files")
        elif item["type"] == "conversation_placeholder":
            print(f"{prefix} {i+1}. [conversation_placeholder] {item['data']['type']}")
        else:
            print(f"{prefix} {i+1}. [{item['type']}]")
    print("========================\n")

def generate_conversation_from_placeholder(placeholder_data, dialogue_generator):
    """
    Given a placeholder data dict, generate the actual conversation text.
    This is where we call GPT-4 to create the conversation right before playing.
    """
    ctype = placeholder_data["type"]
    if ctype == "song_description":
        # Generate a short dialogue describing the song that just ended.
        song_name = placeholder_data["song_name"]
        artist = placeholder_data["artist"]
        # Generate a very short conversation about the song
        speeches = dialogue_generator.generate_song_dialogue(song_name, artist)
        return speeches

    elif ctype == "news_description":
        # Generate a dialogue about the selected article
        article = placeholder_data["article"]
        summarised_article = dialogue_generator.summarise_article_for_dialogue(article)
        # We'll pass no next song here, just a generic news chat
        speeches = dialogue_generator.generate_dialogue_for_news(summarised_article)
        return speeches

    else:
        # Should never get here
        return ["MATT: I'm not sure what to talk about.", "MOLLIE: Me neither."]

def main():
    args = parse_arguments()
    dummy_mode = args.dummy

    visualiser = Visualiser()
    audio_player = AudioPlayer(visualiser=visualiser)
    voice_generator = VoiceGenerator()
    spotify_handler = SpotifyHandler(username="leo.camacho1738")

    if dummy_mode:
        # Dummy mode: no article selection
        # We still need to build initial queue as per instructions
        play_queue, played_songs = build_initial_queue(dummy_mode=True, spotify_handler=spotify_handler, news_processor=None)
        dialogue_generator = None
    else:
        # Normal mode
        news_processor = NewsProcessor()
        dialogue_generator = DialogueGenerator()

        play_queue, played_songs = build_initial_queue(
            dummy_mode=False,
            spotify_handler=spotify_handler,
            news_processor=news_processor
        )

    current_index = 0
    print_queue_status(play_queue, current_index)

    # When a conversation_placeholder is reached, we generate the conversation
    # right there. When a song is about to finish, we may dynamically add more items.
    # However, the instructions now only say we have the initial queue as described.
    # We can still handle end-of-song logic if needed, but let's focus on the requested initialization.

    while True:
        if current_index >= len(play_queue):
            print("Queue ended. No more items.")
            break

        item = play_queue[current_index]
        current_index += 1

        if item["type"] == "conversation":
            # Already generated conversation (if any)
            print("\nPlaying conversation:")
            for idx, speech in enumerate(item["data"], start=1):
                print(f"Speaker {idx}: {speech}")
            play_dialogues(item["data"], visualiser, voice_generator, audio_player)

        elif item["type"] == "conversation_pre_recorded":
            # item["data"] is a list of (file, speaker)
            print("\nPlaying pre-recorded conversation:")
            play_pre_recorded_dialogues(item["data"], visualiser, audio_player)

        elif item["type"] == "conversation_placeholder":
            # Generate the conversation now
            if not dummy_mode and dialogue_generator:
                speeches = generate_conversation_from_placeholder(item["data"], dialogue_generator)
            else:
                # Dummy or no generator
                # Just a dummy conversation
                speeches = ["MATT: This is a placeholder.", "MOLLIE: Indeed, a placeholder conversation."]
            # Replace this item in the queue with a generated conversation
            item["type"] = "conversation"
            item["data"] = speeches

            # Play it immediately (since we are at this index)
            print("\nPlaying generated conversation:")
            for idx, speech in enumerate(speeches, start=1):
                print(f"Speaker {idx}: {speech}")
            play_dialogues(speeches, visualiser, voice_generator, audio_player)

        elif item["type"] == "song":
            song = item["data"]
            print(f"\nNow playing: {song['name']} by {song['artist']}")
            spotify_handler.play_track(song['uri'])
            print_queue_status(play_queue, current_index)

            # Monitor the song playback until it finishes
            # In the instructions, generating conversation and audio at the end of the preceding 
            # song is required for transitions. 
            # Since we already have placeholders set up, we just let the song play.
            # If needed, we could do advanced logic here to generate next items dynamically,
            # but the instructions only specified the initial queue structure.
            
            while True:
                remaining_time = spotify_handler.get_remaining_time()
                if remaining_time is None:
                    print("Playback stopped unexpectedly.")
                    break

                if remaining_time < 4000: # Milliseconds
                    # Track finished
                    break

                time.sleep(0.5)

        else:
            print(f"Unknown queue item type: {item['type']}")

    print("All done.")

if __name__ == "__main__":
    main()
