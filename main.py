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

PLAYLIST_ID = "0NvNQWJaSUTBTQjhjWbNfL"
SONGS_PER_BLOCK = 3

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

def get_unique_random_song(spotify_handler, played_songs):
    song = spotify_handler.get_random_playlist_song(PLAYLIST_ID, played_songs)
    if song is None:
        print("No more unique songs found in the playlist. Exiting.")
        sys.exit(1)
    played_songs.append(song['uri'])
    return song

def expand_queue(play_queue, dummy_mode, spotify_handler, news_processor, dialogue_generator,
                 played_songs, articles_list, used_articles):
    """
    Expand the queue with the pattern:
    - 3 new songs
    - conversation placeholder about 3rd song
    - 3 new songs
    - conversation placeholder about a new article (not used before)

    Do not generate conversations now, only placeholders.
    """
    # Get 3 songs
    first_3_songs = [get_unique_random_song(spotify_handler, played_songs) for _ in range(3)]
    for s in first_3_songs:
        play_queue.append({"type": "song", "data": s})

    # Placeholder about 3rd song
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
    next_3_songs = [get_unique_random_song(spotify_handler, played_songs) for _ in range(3)]
    for s in next_3_songs:
        play_queue.append({"type": "song", "data": s})

    # Placeholder for a news article
    if not dummy_mode and articles_list:
        # Filter out used articles
        available_articles = [a for a in articles_list if a['link'] not in used_articles]
        if not available_articles:
            print("No more unused articles left.")
            # We can skip adding news placeholder if no articles left
        else:
            selected_article = random.choice(available_articles)
            used_articles.add(selected_article['link'])
            play_queue.append({
                "type": "conversation_placeholder",
                "data": {
                    "type": "news_description",
                    "article": selected_article
                }
            })
    else:
        # Dummy or no articles
        play_queue.append({
            "type": "conversation_placeholder",
            "data": {
                "type": "news_description",
                "article": {
                    "title": "Dummy Article",
                    "summary": "This is a dummy summary",
                    "link": "http://example.com/dummy",
                    "full_text": "This is dummy full text."
                }
            }
        })

def build_initial_queue(dummy_mode, spotify_handler, news_processor, played_songs, articles_list, used_articles):
    """
    Build the initial queue with the specified pattern.
    """
    play_queue = []
    expand_queue(play_queue, dummy_mode, spotify_handler, news_processor, None, played_songs, articles_list, used_articles)
    return play_queue

def print_queue_status(play_queue, current_index):
    """Helper function to print the current state of the queue."""
    # Clear console (works on both Windows and Unix-like systems)
    os.system('cls' if os.name == 'nt' else 'clear')
    
    print("\n=== Current Queue Status ===")
    print(f"Current index: {current_index}")
    for i, item in enumerate(play_queue):
        prefix = "→" if i == current_index-1 else " "
        
        if item["type"] == "song":
            print(f"{prefix} {i+1}. [Song] {item['data']['name']} by {item['data']['artist']}")
        
        elif item["type"] == "conversation":
            # For generated conversations, show what they're talking about
            if 'type' in item.get('data_context', {}):
                if item['data_context']['type'] == 'song_description':
                    song = item['data_context']['song_name']
                    artist = item['data_context']['artist']
                    print(f"{prefix} {i+1}. [Conversation] About '{song}' by {artist}")
                elif item['data_context']['type'] == 'news_description':
                    title = item['data_context']['article']['title']
                    if len(title) > 50:
                        title = title[:47] + "..."
                    print(f"{prefix} {i+1}. [Conversation] About news: {title}")
            else:
                print(f"{prefix} {i+1}. [Conversation] {len(item['data'])} lines of dialogue")
        
        elif item["type"] == "conversation_pre_recorded":
            print(f"{prefix} {i+1}. [Pre-recorded Conversation] {len(item['data'])} files")
        
        elif item["type"] == "conversation_placeholder":
            if item["data"]["type"] == "song_description":
                song_name = item["data"]["song_name"]
                artist = item["data"]["artist"]
                print(f"{prefix} {i+1}. [Upcoming Conversation] About '{song_name}' by {artist}")
            
            elif item["data"]["type"] == "news_description":
                article = item["data"]["article"]
                title = article["title"]
                if len(title) > 50:
                    title = title[:47] + "..."
                print(f"{prefix} {i+1}. [Upcoming Conversation] News: {title}")
        
        else:
            print(f"{prefix} {i+1}. [{item['type']}]")
    
    print("========================\n")

def generate_conversation_from_placeholder(placeholder_data, dialogue_generator):
    """
    Given a placeholder data dict, generate the actual conversation text.
    """
    ctype = placeholder_data["type"]
    if ctype == "song_description":
        # Generate a short dialogue describing the song that just ended.
        song_name = placeholder_data["song_name"]
        artist = placeholder_data["artist"]
        speeches = dialogue_generator.generate_song_dialogue(song_name, artist)
        return speeches

    elif ctype == "news_description":
        # Generate a dialogue about the selected article
        article = placeholder_data["article"]
        summarised_article = dialogue_generator.summarise_article_for_dialogue(article)
        speeches = dialogue_generator.generate_dialogue_for_news(summarised_article)
        return speeches

    else:
        # Fallback
        return ["MATT: I'm not sure what to talk about.", "MOLLIE: Me neither."]

def pre_generate_next_conversation_if_needed(play_queue, current_index, dialogue_generator, dummy_mode):
    """
    If the next item after the currently playing song is a conversation_placeholder,
    generate it now (before the song ends), but do not play it yet.
    Just convert it to a 'conversation' item with the speeches ready.
    """
    if current_index < len(play_queue):
        next_item = play_queue[current_index]
        if next_item["type"] == "conversation_placeholder":
            # Generate now
            if not dummy_mode and dialogue_generator:
                speeches = generate_conversation_from_placeholder(next_item["data"], dialogue_generator)
            else:
                # Dummy or no generator
                speeches = ["MATT: Placeholder conversation.", "MOLLIE: Placeholder conversation."]
            
            # Preserve the context of what the conversation is about
            next_item["data_context"] = next_item["data"]
            next_item["type"] = "conversation"
            next_item["data"] = speeches

def main():
    args = parse_arguments()
    dummy_mode = args.dummy

    visualiser = Visualiser()
    audio_player = AudioPlayer(visualiser=visualiser)
    voice_generator = VoiceGenerator()
    spotify_handler = SpotifyHandler(username="leo.camacho1738")

    used_articles = set()  # Keep track of articles we've used
    played_songs = []      # Keep track of songs we've played

    if dummy_mode:
        # Dummy mode: no article selection, no dialogue generation needed
        news_processor = None
        dialogue_generator = None
        articles_list = []
    else:
        # Normal mode
        # In the original, we had a source_selector, but instructions do not show usage now.
        # We'll assume we just get and process sources automatically. 
        # If needed, reintroduce source_selector logic.
        news_processor = NewsProcessor()
        articles_list = news_processor.get_latest_articles()
        if not articles_list:
            print("No articles found. Proceeding with dummy article placeholders.")
            articles_list = []
        dialogue_generator = DialogueGenerator()

    # Build initial queue
    play_queue = build_initial_queue(dummy_mode, spotify_handler, news_processor, played_songs, articles_list, used_articles)
    current_index = 0
    print_queue_status(play_queue, current_index)

    while True:
        if current_index >= len(play_queue):
            print("Queue ended. No more items.")
            break

        # Check if we need to expand the queue soon (when only 2 items left)
        # 2 items left means: if len(play_queue) - current_index < 3
        # Because we are about to play one item and then only 2 remain
        if (len(play_queue) - current_index) < 3:
            # Expand the queue
            expand_queue(play_queue, dummy_mode, spotify_handler, news_processor, dialogue_generator, played_songs, articles_list, used_articles)
            print("Expanded the queue because we were running low on items.")
            print_queue_status(play_queue, current_index)

        item = play_queue[current_index]
        current_index += 1

        if item["type"] == "conversation":
            # Play the conversation
            print("\nPlaying conversation:")
            for idx, speech in enumerate(item["data"], start=1):
                print(f"Speaker {idx}: {speech}")
            play_dialogues(item["data"], visualiser, voice_generator, audio_player)

        elif item["type"] == "conversation_pre_recorded":
            print("\nPlaying pre-recorded conversation:")
            play_pre_recorded_dialogues(item["data"], visualiser, audio_player)

        elif item["type"] == "conversation_placeholder":
            # If we ever hit a placeholder un-generated (which shouldn't happen now),
            # Generate on the fly and play:
            print("Warning: conversation_placeholder reached without pre-generation.")
            if not dummy_mode and dialogue_generator:
                speeches = generate_conversation_from_placeholder(item["data"], dialogue_generator)
            else:
                speeches = ["MATT: Placeholder", "MOLLIE: Placeholder"]
            item["type"] = "conversation"
            item["data"] = speeches
            print("\nPlaying generated conversation:")
            for idx, speech in enumerate(speeches, start=1):
                print(f"Speaker {idx}: {speech}")
            play_dialogues(speeches, visualiser, voice_generator, audio_player)

        elif item["type"] == "song":
            song = item["data"]
            spotify_handler.play_track(song['uri'])
            print_queue_status(play_queue, current_index)
            print(f"\nNow playing: {song['name']} by {song['artist']}")

            # While playing, we check if the next item is a conversation_placeholder
            # If yes, generate it during the last ~10 seconds of the current song.
            conversation_prepared = False

            while True:
                remaining_time = spotify_handler.get_remaining_time()
                if remaining_time is None:
                    print("Playback stopped unexpectedly.")
                    break

                # If close to end of song and next is conversation_placeholder (not yet generated), generate it now
                if remaining_time < 10000 and not conversation_prepared:
                    pre_generate_next_conversation_if_needed(play_queue, current_index, dialogue_generator, dummy_mode)
                    conversation_prepared = True

                if remaining_time < 4000:
                    # Track finished
                    break

                time.sleep(0.5)

        else:
            print(f"Unknown queue item type: {item['type']}")

    print("All done.")

if __name__ == "__main__":
    main()
