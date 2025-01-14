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
    """
    while True:
        user_input = input().strip().lower()
        if user_input == "call":
            print("\n[Interrupt Triggered] User typed 'call'!")
            interrupt_event.set()
            break

def play_phone_ring(ring_file):
    """
    Plays the specified phone ringing/dialing audio and blocks until it finishes.
    """
    if not os.path.exists(ring_file):
        print(f"Warning: {ring_file} not found!")
        return

    pygame.mixer.init()
    pygame.mixer.music.load(ring_file)
    pygame.mixer.music.play()

    # Wait until ring completes
    while pygame.mixer.music.get_busy():
        time.sleep(0.1)

    pygame.mixer.music.stop()
    pygame.mixer.quit()

class InterruptibleAudioPlayer(AudioPlayer):
    """
    Subclass of AudioPlayer that handles the 'call' interrupt with a 
    0.5s overlap between TTS and phone ring, then forcibly stops TTS.
    """
    def __init__(self, visualiser, interrupt_event):
        super().__init__(visualiser=visualiser)
        self.interrupt_event = interrupt_event
        self.ring_thread = None  # We'll store the ring thread here

    def _play_file(self, audio_file, speaker):
        """
        Overridden to allow a speaker-dependent overlap with the phone ring
        if the user types 'call'. After that overlap, TTS is forcibly stopped.
        """
        # Initialize mixer if not already initialized
        if not pygame.mixer.get_init():
            pygame.mixer.init()
            
        pygame.mixer.music.load(audio_file)
        pygame.mixer.music.play()
        self.is_playing = True

        if self.visualiser:
            self.visualiser.set_current_audio(audio_file, speaker)

        ring_started = False

        while True:
            pos_ms = pygame.mixer.music.get_pos()
            if pos_ms == -1:
                # Playback finished normally
                break

            # If the user typed 'call' AND we haven't started the ring yet:
            if self.interrupt_event.is_set() and not ring_started:
                ring_started = True
                
                # Choose interrupt file and overlap time based on current speaker
                if speaker == "matt":  # echo voice
                    ring_file = "speeches/sage_interrupts.wav"
                    overlap_time = 6.1
                else:  # mollie/nova voice
                    ring_file = "speeches/echo_interrupts.wav"
                    overlap_time = 5.4

                # Start playing ring in background with appropriate file
                self.ring_thread = threading.Thread(
                    target=play_phone_ring, 
                    args=(ring_file,),
                    daemon=True
                )
                self.ring_thread.start()

                # Overlap for specified time
                time.sleep(overlap_time)

                # Now forcibly stop the TTS
                if pygame.mixer.get_init():  # Check if mixer is still initialized
                    pygame.mixer.music.stop()
                break

            if self.visualiser:
                self.visualiser.update(pos_ms)

            time.sleep(0.01)

        # Cleanup
        if pygame.mixer.get_init():  # Check if mixer is still initialized
            pygame.mixer.music.stop()
            pygame.mixer.music.unload()
        self.is_playing = False

        # If it's a temp file in /tmp or has 'tmp' in name, remove it
        if audio_file.startswith('/tmp') or "tmp" in audio_file:
            try:
                os.unlink(audio_file)
            except:
                pass

def play_conversation_until_interrupt(speeches, interrupt_event):
    """
    Plays a TTS conversation. If 'call' is typed, we start the ring (in background),
    wait 0.5s, stop TTS, and exit.
    Returns True if TTS ended normally, False if interrupted.
    """
    visualiser = Visualiser()
    audio_player = InterruptibleAudioPlayer(visualiser=visualiser, interrupt_event=interrupt_event)
    voice_generator = VoiceGenerator()

    # We'll hold the ring_thread reference from the audio player after we finish
    # so we can wait for it in the main function.
    ring_thread_ref = None

    q = queue.Queue()
    

    def generate_audio():
        for i, speech in enumerate(speeches):
            if interrupt_event.is_set():
                break
            # Alternate speakers
            speaker_label = "matt" if (i % 2 == 0) else "mollie"
            response = voice_generator.client.audio.speech.create(
                model="tts-1",
                voice=voice_generator.voice_mapping.get(speaker_label, "nova"),
                input=speech,
            )

            temp_file = tempfile.NamedTemporaryFile(delete=False, suffix=f"_{speaker_label}.mp3")
            for chunk in response.iter_bytes():
                temp_file.write(chunk)
            temp_file.flush()
            temp_file.close()
            
            if not interrupt_event.is_set():
                q.put((temp_file.name, speaker_label))

        q.put(None)  # No more audio

    tts_thread = threading.Thread(target=generate_audio, daemon=True)
    tts_thread.start()

    visualiser.init_display()
    interrupted = False

    while True:
        item = q.get()
        if item is None:
            # No more audio
            break

        audio_file, speaker = item

        # If user typed 'call' before playing next file
        if interrupt_event.is_set():
            interrupted = True
            break

        audio_player._play_file(audio_file, speaker)

        # Check if ring started
        if audio_player.ring_thread is not None:
            # If the ring thread was started, it means we triggered "call"
            interrupted = True
            break

    visualiser.quit_display()
    tts_thread.join(timeout=0.5)

    ring_thread_ref = audio_player.ring_thread
    return (not interrupted), ring_thread_ref

def launch_realtime_convo(context):
    """
    Launches the realtime conversation from `convo.py` 
    (blocking call). 
    """
    new_env = os.environ.copy()
    new_env["CUSTOM_CONTEXT"] = context

    print("\n[Launching Real-time Conversation in a separate subprocess...]\n")
    subprocess.call(["python", "convo.py"], env=new_env)
    print("\n[Real-time conversation ended. Returning to main script.]\n")

def main():
    """
    1) Generate a fake news article & TTS conversation.
    2) If user types 'call':
       - Ring starts in background with 0.5s overlap
       - TTS forcibly stops
       - We wait for ring to fully finish
       - Then launch the realtime conversation
    """
    # 1) Prepare a "fake" news article
    article = generate_fake_news_article()

    # 2) Generate radio-style conversation
    dialogue_generator = DialogueGenerator()
    summarised = dialogue_generator.summarise_article_for_dialogue(article)
    speeches = dialogue_generator.generate_dialogue_for_news(summarised)

    # Real-time context
    context_for_realtime = (
        f"We were discussing a news story: {article['title']}.\n"
        "Now, a listener is calling in to talk to Mollie in real time."
    )

    # Create an event that triggers if user types "call"
    interrupt_event = threading.Event()
    input_thread = threading.Thread(target=monitor_for_call, args=(interrupt_event,), daemon=True)
    input_thread.start()

    # 3) Play conversation
    finished_normally, ring_thread_ref = play_conversation_until_interrupt(speeches, interrupt_event)

    # 4) If interrupted, wait for the ring to complete, then open real-time
    if not finished_normally:
        print("\n[AI conversation interrupted. Waiting for ring to finish...]\n")
        
        # ring_thread_ref is the thread that was playing the ring
        if ring_thread_ref is not None:
            ring_thread_ref.join()  # Wait for phone ring to fully finish

        # Now that ring is done, launch real-time convo
        launch_realtime_convo(context_for_realtime)
    else:
        print("\nNo interruption occurred; conversation finished normally.")

    print("seamless_convo_interrupt.py: All done.")

if __name__ == "__main__":
    main()
