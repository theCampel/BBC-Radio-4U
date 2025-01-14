# seamless_convo_interrupt.py

import os
import sys
import time
import queue
import threading
import subprocess
import tempfile

import pygame  # for immediate playback stopping
from dotenv import load_dotenv

# Import your existing modules
from src.audio_player import AudioPlayer
from src.voice_generator import VoiceGenerator
from src.visualiser import Visualiser
from src.dialogue_generator import DialogueGenerator

load_dotenv()  # Make sure OPENAI_API_KEY (and others) are loaded

def generate_fake_news_article():
    """
    Returns a hardcoded 'fake' article text for demonstration purposes.
    """
    article = {
        "title": "BREAKING: Sky Painted Green by Gigantic Alien Brush!",
        "summary": "Authorities confirm a bizarre phenomenon in which the sky is now tinted green.",
        "full_text": (
            "In a surreal turn of events, residents woke up to find the entire sky painted bright green. "
            "Government officials claim that an alien craft flew overhead at midnight, using a massive brush. "
            "Social media is in a frenzy, with #GreenSky trending worldwide."
        ),
        "link": "http://example.com/fake_green_sky_news"
    }
    return article

def monitor_for_call(interrupt_event):
    """
    Continuously monitors user input. If user types 'call', set the interrupt event.
    This will abort the current TTS playback immediately.
    """
    while True:
        user_input = input().strip().lower()
        if user_input == "call":
            print("\n[Interrupt Triggered] User typed 'call'!")
            interrupt_event.set()
            break

class InterruptibleAudioPlayer(AudioPlayer):
    """
    Subclass of AudioPlayer that can abort playback immediately if an event is set.
    """
    def __init__(self, visualiser, interrupt_event):
        super().__init__(visualiser=visualiser)
        self.interrupt_event = interrupt_event

    def _play_file(self, audio_file, speaker):
        """
        Overridden version that checks `interrupt_event` and aborts playback if needed.
        """
        pygame.mixer.music.load(audio_file)
        pygame.mixer.music.play()
        self.is_playing = True

        if self.visualiser:
            self.visualiser.set_current_audio(audio_file, speaker)

        while True:
            if self.interrupt_event.is_set():
                # Immediately stop the current track
                pygame.mixer.music.stop()
                break

            pos_ms = pygame.mixer.music.get_pos()
            if pos_ms == -1:
                # Playback finished normally
                break

            if self.visualiser:
                self.visualiser.update(pos_ms)

            time.sleep(0.01)

        pygame.mixer.music.stop()
        pygame.mixer.music.unload()
        self.is_playing = False
        # If it's a temp file in /tmp, remove it
        if audio_file.startswith('/tmp') or "tmp" in audio_file:
            try:
                os.unlink(audio_file)
            except:
                pass

def play_conversation_until_interrupt(speeches, interrupt_event):
    """
    Plays a conversation (text -> TTS -> audio) but stops immediately if `interrupt_event` is set.
    Returns True if finished playback normally, or False if interrupted (i.e., user typed 'call').
    """
    visualiser = Visualiser()
    audio_player = InterruptibleAudioPlayer(visualiser=visualiser, interrupt_event=interrupt_event)
    voice_generator = VoiceGenerator()

    # We generate audio in one thread, while the AudioPlayer consumes it in the current thread.
    # If we detect an interrupt, we break out immediately in the main loop.
    q = queue.Queue()

    def generate_audio():
        for i, speech in enumerate(speeches):
            if interrupt_event.is_set():
                break  # Stop TTS if we are already interrupted

            # Alternate speakers: even = MATT, odd = MOLLIE
            speaker_label = "matt" if (i % 2 == 0) else "mollie"
            response = voice_generator.client.audio.speech.create(
                model="tts-1",
                voice=voice_generator.voice_mapping.get(speaker_label, "nova"),
                input=speech,
            )
            # Store TTS data to a temp file
            temp_file = tempfile.NamedTemporaryFile(delete=False, suffix=f"_{speaker_label}.mp3")
            for chunk in response.iter_bytes():
                temp_file.write(chunk)
            temp_file.flush()
            temp_file.close()
            
            if not interrupt_event.is_set():
                q.put((temp_file.name, speaker_label))

        # Signal no more audio
        q.put(None)

    # Start the TTS generation in a separate thread
    tts_thread = threading.Thread(target=generate_audio, daemon=True)
    tts_thread.start()

    visualiser.init_display()
    while True:
        item = q.get()
        if item is None:
            # No more audio
            break
        audio_file, speaker = item

        # If we have been interrupted, break right now
        if interrupt_event.is_set():
            break

        # Play the file
        audio_player._play_file(audio_file, speaker)

        # If the user typed call in the middle, we might break mid-track
        if interrupt_event.is_set():
            break

    visualiser.quit_display()
    tts_thread.join(timeout=0.5)
    return not interrupt_event.is_set()

def play_phone_ring():
    """
    Plays the phone ringing/dialing audio. 
    This blocks until phone_ring.mp3 finishes.
    """
    ring_file = "speeches/phone_ring.wav"  # Adjust path if needed
    if not os.path.exists(ring_file):
        print(f"Warning: {ring_file} not found!")
        return

    # Minimal approach: no visualiser needed for a simple ring
    pygame.mixer.init()
    pygame.mixer.music.load(ring_file)
    pygame.mixer.music.play()

    # Block until it finishes
    while pygame.mixer.music.get_busy():
        time.sleep(0.1)

    pygame.mixer.music.stop()
    pygame.mixer.quit()

def launch_realtime_convo(context):
    """
    Launches the realtime conversation from `convo.py`.
    We'll do it in a separate subprocess. We start it 
    as soon as the phone starts ringing, so that by the
    time the ring finishes, the user can speak.
    
    'context' can be passed along using env var if you like.
    """
    new_env = os.environ.copy()
    new_env["CUSTOM_CONTEXT"] = context  # Not used by default in convo.py, but can be

    print("\n[Launching Real-time Conversation in a separate subprocess...]\n")
    # This will block until convo.py exits.
    subprocess.call(["python", "convo.py"], env=new_env)
    print("\n[Real-time conversation ended. Returning to main script.]\n")

def main():
    """
    1) Generate a conversation from a fake (hardcoded) news article.
    2) Start playing that conversation in TTS.
    3) If user types "call", we:
       - Abort current speech
       - Immediately ring phone (phone_ring.mp3)
       - Open realtime sockets for Mollie in parallel
       - After phone ring, user can talk to Mollie in real time
    """
    # 1) Prepare a "fake" news article
    article = generate_fake_news_article()

    # 2) Generate radio-style conversation
    dialogue_generator = DialogueGenerator()
    summarised = dialogue_generator.summarise_article_for_dialogue(article)
    speeches = dialogue_generator.generate_dialogue_for_news(summarised)

    # This is the "context" we might pass to the real-time conversation
    context_for_realtime = (
        f"We were discussing a news story: {article['title']}.\n"
        "Now, a listener is calling in to talk to Mollie in real time."
    )

    # 3) We'll run the conversation in one thread, and monitor user input in another
    interrupt_event = threading.Event()

    # Start a thread to monitor user typing "call"
    input_thread = threading.Thread(target=monitor_for_call, args=(interrupt_event,), daemon=True)
    input_thread.start()

    # 4) Play the conversation. If user types "call," we interrupt
    finished_normally = play_conversation_until_interrupt(speeches, interrupt_event)

    # 5) If we were interrupted, do the ring & real-time sequence
    if not finished_normally:
        print("\n[Interrupting AI conversation. Initiating phone ring...]\n")

        # We want the real-time sockets to open as soon as the phone starts ringing,
        # so let's spawn that in a background thread
        rt_thread = threading.Thread(target=launch_realtime_convo, args=(context_for_realtime,), daemon=True)
        rt_thread.start()

        # Now play phone ring in the foreground
        play_phone_ring()

        # By the time the ring is done, the user can speak to Mollie in real time.
        # Wait for the real-time conversation to finish
        rt_thread.join()
    else:
        print("\nNo interruption occurred; conversation finished normally.")

    print("seamless_convo_interrupt.py: All done.")

if __name__ == "__main__":
    main()
