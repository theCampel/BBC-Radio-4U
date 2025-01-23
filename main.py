# main.py

import os
import sys
import json
import time
import queue
import random
import asyncio
import threading
from threading import Thread

from fastapi.concurrency import asynccontextmanager
import websockets
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.staticfiles import StaticFiles
from dotenv import load_dotenv

from src.spotify_handler import SpotifyHandler
from src.news_processor import NewsProcessor
from src.dialogue_generator import DialogueGenerator
from src.voice_generator import VoiceGenerator
from src.audio_player import AudioPlayer
from src.constants import REALTIME_MOLLIE_PROMPT

# Additional imports for streaming TTS:
import base64
import pydub
import tempfile

load_dotenv()

##############################################################################
# GLOBALS
##############################################################################

app = FastAPI()

app.mount("/static", StaticFiles(directory="frontend"), name="static")

PLAYLIST_ID = "0NvNQWJaSUTBTQjhjWbNfL"
SONGS_PER_BLOCK = 3

radio_queue = []
current_index = 0
radio_running = False
radio_thread = None

used_articles = set()
played_songs = []
dummy_mode = False

spotify_handler = None
news_processor = None
dialogue_generator = None
articles_list = []
voice_generator = None
audio_player = None

# NEW: We'll store the uvicorn event loop here so threads can schedule tasks on it
UVICORN_LOOP = None

# Keep track of websockets for host TTS
HOST_WS_CONNECTIONS = set()

##############################################################################
# INIT & LIFESPAN
##############################################################################

@asynccontextmanager
async def lifespan(app: FastAPI):
    global UVICORN_LOOP
    UVICORN_LOOP = asyncio.get_event_loop()  # This is Uvicorn’s running event loop
    init_services()
    yield
    # On shutdown, if needed, do cleanup

def init_services():
    """
    Initialize Spotify, news, dialogue, TTS, etc.
    """
    global spotify_handler, news_processor, dialogue_generator
    global articles_list, dummy_mode, voice_generator, audio_player

    print("Running init_services()...")

    # Attempt setting up Spotify
    try:
        sp = SpotifyHandler(username="leo.camacho1738")
        _ = sp.get_remaining_time()  # test call
        spotify_handler = sp
        print("Spotify ready.")
    except Exception as e:
        print("Cannot init SpotifyHandler:", e)
        dummy_mode = True
        spotify_handler = None

    # Attempt news+dialogue
    if not dummy_mode:
        try:
            np = NewsProcessor()
            arr = np.get_latest_articles()
            if not arr:
                arr = []
                print("No articles found. Using dummy placeholders.")
            dg = DialogueGenerator()
            news_processor = np
            dialogue_generator = dg
            articles_list.extend(arr)
            print(f"Loaded {len(arr)} articles; Dialogue gen ready.")
        except Exception as e:
            print("Error setting up news/dialogue:", e)
            dummy_mode = True
            news_processor = None
            dialogue_generator = None

    voice_generator = VoiceGenerator()
    audio_player = AudioPlayer(visualiser=None)  # HEADLESS
    print("Voice generator + audio player ready (headless).")


##############################################################################
# QUEUE EXPANSION + HELPERS
##############################################################################

def get_unique_random_song(spotify_handler, played_songs):
    song = spotify_handler.get_random_playlist_song(PLAYLIST_ID, played_songs)
    if song is None:
        print("No more unique songs found in the playlist.")
        return None
    played_songs.append(song['uri'])
    return song

def expand_queue(play_queue, dummy_mode, spotify_handler, news_processor,
                 dialogue_generator, played_songs, articles_list, used_articles):
    """3 songs -> conversation placeholder -> 3 songs -> conversation placeholder."""
    block1 = []
    for _ in range(3):
        if not dummy_mode and spotify_handler:
            s = get_unique_random_song(spotify_handler, played_songs)
        else:
            s = None
        if not s:
            s = {"name": "Fallback Song", "artist": "Fallback Artist", "uri": None}
        block1.append(s)

    for s in block1:
        play_queue.append({"type": "song", "data": s})
    last_song = block1[-1]
    play_queue.append({
        "type": "conversation_placeholder",
        "data": {
            "type": "song_description",
            "song_name": last_song["name"],
            "artist": last_song["artist"]
        }
    })

    block2 = []
    for _ in range(3):
        if not dummy_mode and spotify_handler:
            s = get_unique_random_song(spotify_handler, played_songs)
        else:
            s = None
        if not s:
            s = {"name": "Fallback Song", "artist": "Fallback Artist", "uri": None}
        block2.append(s)

    for s in block2:
        play_queue.append({"type": "song", "data": s})

    if not dummy_mode and articles_list:
        available = [a for a in articles_list if a['link'] not in used_articles]
        if available:
            sel = random.choice(available)
            used_articles.add(sel['link'])
            play_queue.append({
                "type": "conversation_placeholder",
                "data": {
                    "type": "news_description",
                    "article": sel
                }
            })
        else:
            play_queue.append({
                "type": "conversation_placeholder",
                "data": {
                    "type": "news_description",
                    "article": {
                        "title": "No More Real Articles",
                        "summary": "No more articles left.",
                        "link": "#",
                        "full_text": "None left."
                    }
                }
            })
    else:
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

def build_initial_queue(dummy_mode, spotify_handler, news_processor, played_songs,
                        articles_list, used_articles):
    q = []
    expand_queue(q, dummy_mode, spotify_handler, news_processor, None,
                 played_songs, articles_list, used_articles)
    return q

def generate_conversation_from_placeholder(placeholder_data, dialogue_gen):
    ctype = placeholder_data["type"]
    if ctype == "song_description":
        song_name = placeholder_data["song_name"]
        artist = placeholder_data["artist"]
        if dialogue_gen:
            return dialogue_gen.generate_song_dialogue(song_name, artist)
        else:
            return [
                f"MATT: That was '{song_name}' by {artist}. Always a vibe!",
                "MOLLIE: Definitely. Let’s keep the party going!"
            ]
    elif ctype == "news_description":
        if dialogue_gen:
            art = placeholder_data["article"]
            summary = dialogue_gen.summarise_article_for_dialogue(art)
            return dialogue_gen.generate_dialogue_for_news(summary)
        else:
            return [
                "MATT: Some interesting news out there, apparently!",
                "MOLLIE: Big stuff happening. Next song soon!"
            ]
    else:
        return ["MATT: Not sure what to talk about.", "MOLLIE: Me neither."]

def pre_generate_next_conversation_if_needed(play_queue, current_index, diag_gen, is_dummy):
    if current_index < len(play_queue):
        nxt = play_queue[current_index]
        if nxt["type"] == "conversation_placeholder":
            speeches = (
                generate_conversation_from_placeholder(nxt["data"], diag_gen)
                if not is_dummy else
                ["MATT: Placeholder...", "MOLLIE: Placeholder..."]
            )
            nxt["data_context"] = nxt["data"]
            nxt["type"] = "conversation"
            nxt["data"] = speeches

##############################################################################
# HOST AUDIO STREAMING
##############################################################################

def stream_host_tts(mp3_path: str):
    """
    Generator: yields small raw PCM chunks (~200ms each) from an MP3 file.
    """
    segment = pydub.AudioSegment.from_mp3(mp3_path)
    segment = segment.set_frame_rate(24000).set_channels(1)

    chunk_ms = 200
    pos = 0
    while pos < len(segment):
        chunk = segment[pos : pos + chunk_ms]
        pos += chunk_ms
        yield chunk.raw_data

async def broadcast_host_tts(mp3_path: str, speaker: str):
    """
    Async: base64-encodes the PCM frames and sends them to all clients on /ws/host_audio.
    """
    for raw_pcm in stream_host_tts(mp3_path):
        b64_pcm = base64.b64encode(raw_pcm).decode("utf-8")
        packet = {
            "event": "media",
            "media": {"payload": b64_pcm},
            "speaker": speaker.lower()
        }
        # Send to every connected WS
        dead = []
        for ws in list(HOST_WS_CONNECTIONS):
            try:
                await ws.send_json(packet)
            except:
                dead.append(ws)
        for d in dead:
            HOST_WS_CONNECTIONS.remove(d)

        await asyncio.sleep(0.2)


def play_dialogues(speeches, voice_generator, audio_player):
    """
    1) Generate TTS into MP3 files (via voice_generator).
    2) For each file => 
       - schedule an async broadcast to push PCM to /ws/host_audio 
         on the *UVICORN_LOOP*
       - block & play via PyGame 
    """
    q = queue.Queue()
    gen_thread = Thread(target=voice_generator.generate_to_queue, args=(speeches, q))
    gen_thread.start()

    while True:
        item = q.get()
        if item is None:
            break
        audio_file, speaker = item

        # The key fix: schedule the streaming on the uvicorn event loop
        if UVICORN_LOOP:
            asyncio.run_coroutine_threadsafe(
                broadcast_host_tts(audio_file, speaker),
                UVICORN_LOOP
            )

        # Play locally (blocking)
        audio_player._play_file(audio_file, speaker)

##############################################################################
# RADIO LOOP
##############################################################################

def radio_loop():
    global radio_running, radio_queue, current_index
    global dummy_mode, spotify_handler, voice_generator, audio_player

    print("Radio loop started.")

    while radio_running:
        if current_index >= len(radio_queue):
            print("[Radio] queue ended or empty, expanding for continuity.")
            expand_queue(radio_queue, dummy_mode, spotify_handler, news_processor,
                         dialogue_generator, played_songs, articles_list, used_articles)

        if current_index >= len(radio_queue):
            print("[Radio] still no items after expansion, stopping.")
            radio_running = False
            break

        item = radio_queue[current_index]
        current_index += 1

        if item["type"] == "song":
            sdata = item["data"]
            print(f"[Radio] Now playing: {sdata['name']} by {sdata['artist']}")
            if sdata.get("uri"):
                spotify_handler.play_track(sdata["uri"])

            conversation_prepared = False
            while radio_running:
                remaining = (spotify_handler.get_remaining_time()
                             if sdata.get("uri") else None)
                if remaining is None:
                    print("[Radio] Song ended or no playback device. Moving on.")
                    break
                if remaining < 10000 and not conversation_prepared:
                    pre_generate_next_conversation_if_needed(radio_queue, current_index,
                                                             dialogue_generator, dummy_mode)
                    conversation_prepared = True
                if remaining < 4000:
                    break
                time.sleep(0.5)

        elif item["type"] == "conversation_placeholder":
            print("[Radio] conversation_placeholder not pre-generated. Doing now.")
            speeches = generate_conversation_from_placeholder(item["data"], dialogue_generator)
            item["type"] = "conversation"
            item["data"] = speeches
            print("[Radio] Now playing conversation.")
            play_dialogues(speeches, voice_generator, audio_player)

        elif item["type"] == "conversation":
            print(f"[Radio] Playing conversation: {item['data']}")
            play_dialogues(item["data"], voice_generator, audio_player)

        else:
            print(f"[Radio] Unknown item type: {item['type']}. Skipping.")

    radio_running = False
    print("Radio loop finished.")


##############################################################################
# FASTAPI ROUTES
##############################################################################

@app.post("/api/start_radio")
def start_radio():
    global radio_queue, current_index, used_articles, played_songs
    global radio_running, radio_thread

    radio_queue.clear()
    used_articles.clear()
    played_songs.clear()
    current_index = 0

    radio_queue.extend(build_initial_queue(dummy_mode, spotify_handler, news_processor,
                                          played_songs, articles_list, used_articles))
    radio_running = True

    radio_thread = threading.Thread(target=radio_loop, daemon=True)
    radio_thread.start()

    return {"status": "ok", "message": "Radio started. queue built."}

@app.get("/api/queue")
def get_queue():
    return {
        "queue": radio_queue,
        "currentIndex": current_index
    }

@app.get("/")
def index():
    return {"status": "Radio Station API running"}


##############################################################################
# CALLER REALTIME WS
##############################################################################

@app.websocket("/ws/realtime-convo")
async def realtime_convo_endpoint(websocket: WebSocket):
    await websocket.accept()
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        print("No OPENAI_API_KEY -> local echo.")
        await handle_local_echo(websocket)
    else:
        await handle_openai_realtime(websocket, api_key)
    print("[WebSocket] connection open")

async def handle_local_echo(websocket: WebSocket):
    try:
        while True:
            data = await websocket.receive_text()
            parsed = json.loads(data)
            if parsed.get("event") == "media" and "media" in parsed:
                b64audio = parsed["media"]["payload"]
                await websocket.send_json({
                    "event": "media",
                    "media": {"payload": b64audio},
                    "speaker": "caller"
                })
    except WebSocketDisconnect:
        print("Local echo: client disconnected.")
    except Exception as e:
        print("Local echo error:", e)
    finally:
        await websocket.close()

async def handle_openai_realtime(websocket: WebSocket, api_key: str):
    openai_headers = [
        ("Authorization", f"Bearer {api_key}"),
        ("OpenAI-Beta", "realtime=v1"),
    ]
    instructions = REALTIME_MOLLIE_PROMPT.format(custom_context="(Server-based conversation)")
    model = "gpt-4o-realtime-preview-2024-10-01"
    endpoint_url = f"wss://api.openai.com/v1/realtime?model={model}"

    try:
        async with websockets.connect(endpoint_url, headers=openai_headers, ping_interval=30) as openai_ws:
            session_update = {
                "type": "session.update",
                "session": {
                    "modalities": ["text", "audio"],
                    "instructions": instructions,
                    "voice": "nova",
                    "input_audio_format": "pcm16",
                    "output_audio_format": "pcm16",
                    "turn_detection": {
                        "type": "server_vad",
                        "threshold": 0.5,
                        "prefix_padding_ms": 300,
                        "silence_duration_ms": 1000,
                        "create_response": True
                    },
                    "temperature": 0.4
                }
            }
            await openai_ws.send(json.dumps(session_update))

            async def from_client_to_openai():
                try:
                    while True:
                        msg = await websocket.receive_text()
                        msg_data = json.loads(msg)
                        if msg_data.get("event") == "media":
                            b64audio = msg_data["media"]["payload"]
                            await openai_ws.send(json.dumps({
                                "type": "input_audio_buffer.append",
                                "audio": b64audio
                            }))
                except WebSocketDisconnect:
                    print("Realtime call client disconnected.")
                except Exception as e:
                    print("from_client_to_openai error:", e)

            async def from_openai_to_client():
                try:
                    async for msg_str in openai_ws:
                        try:
                            d = json.loads(msg_str)
                        except:
                            continue
                        if d.get("type") == "response.audio.delta" and "delta" in d:
                            chunk_b64 = d["delta"]
                            await websocket.send_json({
                                "event": "media",
                                "media": {"payload": chunk_b64},
                                "speaker": "caller"
                            })
                        elif d.get("type") == "response.text.delta":
                            delta_text = d.get("delta", "")
                            await websocket.send_json({
                                "event": "text_delta",
                                "delta": delta_text
                            })
                        elif d.get("type") == "response.text.done":
                            await websocket.send_json({"event": "text_done"})
                except Exception as e:
                    print("from_openai_to_client error:", e)

            await asyncio.gather(
                from_client_to_openai(),
                from_openai_to_client()
            )

    except Exception as e:
        print("Error connecting to OpenAI Realtime:", e)
        await websocket.send_text(f"Error connecting to OpenAI Realtime: {str(e)}")
    finally:
        await websocket.close()
        print("[WS] closed openai realtime")

##############################################################################
# HOST TTS WEBSOCKET
##############################################################################

@app.websocket("/ws/host_audio")
async def host_audio_endpoint(websocket: WebSocket):
    """
    We'll push PCM data for Matt/Mollie to these connections in broadcast_host_tts().
    """
    await websocket.accept()
    HOST_WS_CONNECTIONS.add(websocket)
    print("[WebSocket] client joined /ws/host_audio for host TTS")
    try:
        while True:
            _ = await websocket.receive_text()  
            # Not expecting data from client, 
            # but must read to keep connection alive.
    except WebSocketDisconnect:
        pass
    finally:
        HOST_WS_CONNECTIONS.remove(websocket)
        print("[WebSocket] client left /ws/host_audio")


##############################################################################
# UVICORN ENTRY POINT
##############################################################################
if __name__ == "__main__":
    import uvicorn
    # We rely on the lifespan to set up UVICORN_LOOP
    uvicorn.run(app, host="0.0.0.0", port=8000)
