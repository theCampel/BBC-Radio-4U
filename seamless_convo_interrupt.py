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

def monitor_for_input(call_event, end_event):
    """
    Monitors user input in a loop. 
    - If user types 'call', sets call_event.
    - If user types 'end', sets end_event and breaks (ends program).
    """
    while True:
        user_input = input().strip().lower()

        if user_input == "call":
            print("\n[Interrupt Triggered] User typed 'call'!")
            call_event.set()

        elif user_input == "end":
            print("\n[End Triggered] User typed 'end'!")
            end_event.set()
            break

def play_end_call_sound():
    """
    Plays echo_ends_call.wav in blocking mode, then quits the mixer.
    """
    if not os.path.exists("speeches/echo_ends_call.wav"):
        print("Warning: echo_ends_call.wav not found!")
        return

    pygame.mixer.init()
    sound = pygame.mixer.Sound("speeches/echo_ends_call.wav")
    channel = pygame.mixer.Channel(9)  # Arbitrary separate channel for end-call sound
    channel.play(sound)

    while channel.get_busy():
        time.sleep(0.05)
    pygame.mixer.quit()

class InterruptibleAudioPlayer(AudioPlayer):
    """
    Subclass of AudioPlayer that handles the 'call' interrupt with a 
    0.5s overlap between TTS and phone ring, then forcibly stops TTS.
    """
    def __init__(self, visualiser, call_event, end_event):
        super().__init__(visualiser=visualiser)
        self.call_event = call_event
        self.end_event = end_event

    def _play_file(self, audio_file, speaker):
        """
        Overridden to:
          - Use a dedicated channel (0) for TTS
          - If user types 'call', start ring on channel (1) with 0.5s overlap
          - Stop TTS channel, but do NOT stop ring
        """
        # Initialize pygame mixer if not yet initialized
        if not pygame.mixer.get_init():
            pygame.mixer.init()

        # Load TTS as a pygame Sound
        tts_sound = pygame.mixer.Sound(audio_file)
        tts_channel = pygame.mixer.Channel(0)  # TTS on channel 0

        # Start playing TTS
        tts_channel.play(tts_sound)
        self.is_playing = True

        if self.visualiser:
            self.visualiser.set_current_audio(audio_file, speaker)

        ring_started = False
        ring_channel = None

        while True:
            # If TTS finished on its own, break
            if not tts_channel.get_busy():
                break

            # If 'end' is typed, we break ASAP
            if self.end_event.is_set():
                break

            # If 'call' is typed and ring hasn't started yet
            if self.call_event.is_set() and not ring_started:
                ring_started = True

                # Choose correct ring audio based on current speaker
                if speaker == "matt":  # Matt's voice
                    ring_file = "speeches/nova_interrupts.wav"
                    self.interrupt_wait_time = 5.5
                else:  # Nova/Mollie's voice
                    ring_file = "speeches/echo_interrupts.wav"
                    self.interrupt_wait_time = 5.8

                if os.path.exists(ring_file):
                    # Load ring audio and play on channel 1
                    ring_sound = pygame.mixer.Sound(ring_file)
                    ring_channel = pygame.mixer.Channel(1)
                    ring_channel.play(ring_sound)

                # Overlap for 0.5s so it isn't jarring
                time.sleep(0.5)

                # Forcibly stop TTS
                tts_channel.stop()
                break

            # Update visualiser if any
            if self.visualiser:
                pos_ms = 0  # We don't have a direct pos in ms here, so set 0 or skip
                self.visualiser.update(pos_ms)

            time.sleep(0.01)

        # Cleanup TTS
        tts_channel.stop()

        # If it's a temp file, remove it
        if audio_file.startswith('/tmp') or "tmp" in audio_file:
            try:
                os.unlink(audio_file)
            except:
                pass

        self.is_playing = False

def play_conversation_until_interrupt(speeches, call_event, end_event, audio_player):
    """
    Plays a TTS conversation in sequence.
      - If 'call' is typed, ring starts on a separate channel for 0.5s overlap,
        TTS is forcibly stopped, and we exit early.
      - If 'end' is typed, exit immediately.

    Returns:
        (finished_normally [bool]) 
        True if conversation ended with no 'call' interrupt,
        False if it was interrupted by 'call'.
    """
    voice_generator = VoiceGenerator()

    # Queue for TTS audio
    q = queue.Queue()

    def generate_audio():
        for i, speech in enumerate(speeches):
            if end_event.is_set():
                break
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

            if end_event.is_set():
                break
            q.put((temp_file.name, speaker_label))

        q.put(None)  # End of TTS

    tts_thread = threading.Thread(target=generate_audio, daemon=True)
    tts_thread.start()

    audio_player.visualiser.init_display()
    interrupted_by_call = False

    while True:
        if end_event.is_set():
            # 'end' typed => stop everything
            interrupted_by_call = False
            break

        item = q.get()
        if item is None:
            # No more TTS in queue
            break

        audio_file, speaker = item
        audio_player._play_file(audio_file, speaker)

        # If user typed 'call' during playback, we've forcibly stopped TTS
        if call_event.is_set():
            interrupted_by_call = True
            break

    audio_player.visualiser.quit_display()
    tts_thread.join(timeout=0.5)

    return not interrupted_by_call

def launch_realtime_convo(context):
    """
    Launches the realtime conversation from `convo.py` (blocking call). 
    """
    new_env = os.environ.copy()
    print(f"Launching real-time conversation with context: {context}")
    new_env["CUSTOM_CONTEXT"] = context

    print("\n[Launching Real-time Conversation in a separate subprocess...]\n")
    subprocess.call(["python", "convo.py"], env=new_env)
    print("\n[Real-time conversation ended. Returning to main script.]\n")

def main():
    """
    1) Generate a fake radio-style conversation about a news story.
    2) Play it until user possibly types 'call'.
       - If 'call': ring plays on a separate channel with 0.5s overlap. 
         Then TTS is cut off, ring continues. 
       - Wait ~5–6s, then open the mic.
    3) If user types 'end' at any time, end the program after playing echo_ends_call.wav.
    """
    # Two events: one for 'call' interrupt, one for 'end'
    call_event = threading.Event()
    end_event = threading.Event()

    # Initialize audio components
    visualiser = Visualiser()
    audio_player = InterruptibleAudioPlayer(
        visualiser=visualiser, 
        call_event=call_event,
        end_event=end_event
    )

    # Monitor user input in a background thread
    input_thread = threading.Thread(
        target=monitor_for_input,
        args=(call_event, end_event),
        daemon=True
    )
    input_thread.start()

    # 1) Prepare fake article
    article = generate_fake_news_article()

    # 2) Generate the conversation
    dialogue_generator = DialogueGenerator()
    summarised = dialogue_generator.summarise_article_for_dialogue(article)
    speeches = dialogue_generator.generate_dialogue_for_news(summarised)

    # Context for the real-time call
    context_for_realtime = (
        f"We were discussing a news story: {article['title']}.\n"
        f"The following is the full text of the story: {article['full_text']}\n"
        "Now, a listener is calling in to talk to host Mollie in real time."
    )

    # 3) Play conversation
    finished_normally = play_conversation_until_interrupt(speeches, call_event, end_event, audio_player)

    # If user typed 'end' at any point, we handle that now
    if end_event.is_set():
        print("\nUser ended the program. Playing end call sound and exiting.")
        play_end_call_sound()
        sys.exit(0)

    # If user typed 'call', the conversation was interrupted
    if not finished_normally:
        print("\n[TTS was interrupted by 'call'. Ring continues in background if it's still playing.]")
        # Get the wait time that was set during interrupt
        wait_time = audio_player.interrupt_wait_time
        print(f"[Waiting {wait_time} seconds before opening the mic...]\n")
        time.sleep(wait_time)

        # Check again if user ended during that wait
        if end_event.is_set():
            print("User ended the program before real-time convo started.")
            play_end_call_sound()
            sys.exit(0)

        # Now launch real-time conversation
        launch_realtime_convo(context_for_realtime)

        # Once real-time convo returns, we assume user ends
        play_end_call_sound()
        sys.exit(0)

    else:
        # No 'call' interruption
        print("\nNo interruption by 'call'. Conversation finished normally.")
        # If user typed 'end' after TTS ended
        if end_event.is_set():
            play_end_call_sound()
        print("seamless_convo_interrupt.py: All done.")

if __name__ == "__main__":
    main()
