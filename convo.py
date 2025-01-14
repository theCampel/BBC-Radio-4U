import os
import json
import base64
import signal
import sys
import time
import threading
import numpy as np
import pyaudio
import websocket  # pip install websocket-client
from src import constants
from dotenv import load_dotenv

################################################################################
# Settings
################################################################################

load_dotenv()
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
REALTIME_MODEL = "gpt-4o-mini-realtime-preview-2024-12-17"

VOICE_NAME = "alloy"

SAMPLE_RATE = 24000
CHANNELS = 1
CHUNK_MS = 50
CHUNK = int(SAMPLE_RATE * CHUNK_MS / 1000)

################################################################################
# Audio Setup
################################################################################
pya = pyaudio.PyAudio()

mic_stream = pya.open(
    format=pyaudio.paInt16,
    channels=CHANNELS,
    rate=SAMPLE_RATE,
    input=True,
    frames_per_buffer=CHUNK
)

speaker_stream = pya.open(
    format=pyaudio.paInt16,
    channels=CHANNELS,
    rate=SAMPLE_RATE,
    output=True
)

################################################################################
# Connection Tracking
################################################################################
connected_event = threading.Event()
should_run = True  # allows us to exit gracefully if the socket closes
ws_app = None

################################################################################
# WebSocket callbacks
################################################################################

def on_open(ws):
    print("WebSocket connection opened.")
    # Send session update
    session_update = {
        "type": "session.update",
        "session": {
            "modalities": ["audio", "text"],
            "instructions": (
                constants.REALTIME_MOLLIE_PROMPT
            ),
            "voice": VOICE_NAME,
            "input_audio_format": "pcm16",
            "output_audio_format": "pcm16",
            # Server-side VAD
            "turn_detection": {
                "type": "server_vad",
                "threshold": 0.9,
                "prefix_padding_ms": 300,
                "silence_duration_ms": 700
            },
            "temperature": 0.7,
        }
    }
    ws.send(json.dumps(session_update))

    # Signal that the connection is ready
    connected_event.set()

def on_message(ws, message):
    try:
        data = json.loads(message)
    except json.JSONDecodeError:
        print("Received non-JSON data:", message)
        return

    event_type = data.get("type")
    if not event_type:
        return

    if event_type == "response.audio.delta" and "delta" in data:
        audio_chunk_b64 = data["delta"]
        audio_chunk = base64.b64decode(audio_chunk_b64)
        speaker_stream.write(audio_chunk)

    elif event_type == "response.text.delta":
        partial_text = data.get("delta", "")
        sys.stdout.write(partial_text)
        sys.stdout.flush()

    elif event_type == "response.text.done":
        print()  # end the line

    elif event_type == "response.audio_transcript.delta":
        # This is a partial transcript of the user’s speech.
        # Uncomment to see partial transcripts:
        # sys.stdout.write("\r[User partial] " + data["delta"])
        # sys.stdout.flush()
        pass

def on_error(ws, error):
    print("WebSocket error:", error)

def on_close(ws, close_status_code, close_msg):
    global should_run
    print(f"WebSocket closed: {close_status_code} {close_msg}")
    should_run = False
    connected_event.set()  # in case we were still waiting

################################################################################
# Signal handler for Ctrl+C
################################################################################

def signal_handler(sig, frame):
    global should_run
    print("\nShutting down gracefully...")
    should_run = False
    if ws_app and ws_app.sock and ws_app.sock.connected:
        ws_app.close()
    mic_stream.stop_stream()
    mic_stream.close()
    speaker_stream.stop_stream()
    speaker_stream.close()
    pya.terminate()
    sys.exit(0)

signal.signal(signal.SIGINT, signal_handler)

################################################################################
# Main function
################################################################################

def main():
    global ws_app

    url = f"wss://api.openai.com/v1/realtime?model={REALTIME_MODEL}"
    headers = [
        f"Authorization: Bearer {OPENAI_API_KEY}",
        "OpenAI-Beta: realtime=v1"
    ]

    ws_app = websocket.WebSocketApp(
        url,
        header=headers,
        on_open=on_open,
        on_message=on_message,
        on_error=on_error,
        on_close=on_close
    )

    def run_ws():
        # ping_interval helps keep the connection alive
        ws_app.run_forever(ping_interval=30)

    ws_thread = threading.Thread(target=run_ws, daemon=True)
    ws_thread.start()

    print("Recording from microphone. Speak to the AI co-hosts!")
    print("Press Ctrl+C to exit.\n")

    # Wait until we know the connection is open or it closed on error
    connected_event.wait()
    if not ws_app.sock or not ws_app.sock.connected:
        print("Connection was never established or was closed prematurely.")
        return

    # Now continuously read mic audio & send to the WS
    while should_run and ws_app.sock and ws_app.sock.connected:
        audio_data = mic_stream.read(CHUNK, exception_on_overflow=False)
        audio_b64 = base64.b64encode(audio_data).decode("utf-8")

        message_obj = {
            "type": "input_audio_buffer.append",
            "audio": audio_b64
        }

        # If the server or local code closed the socket, we'll catch an exception
        try:
            ws_app.send(json.dumps(message_obj))
        except websocket.WebSocketConnectionClosedException:
            print("Socket closed while sending audio.")
            break

        # Tiny sleep to avoid a busy loop
        time.sleep(0.001)

    print("Main loop finished; cleaning up.")
    # Cleanup happens in signal_handler or after loop
    if ws_app and ws_app.sock and ws_app.sock.connected:
        ws_app.close()
    mic_stream.stop_stream()
    mic_stream.close()
    speaker_stream.stop_stream()
    speaker_stream.close()
    pya.terminate()

if __name__ == "__main__":
    main()
