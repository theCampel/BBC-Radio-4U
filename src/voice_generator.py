from openai import OpenAI
import tempfile
import os
os.environ['PYGAME_HIDE_SUPPORT_PROMPT'] = "hide"
import pygame
import time
import threading
import queue

class VoiceGenerator:
    def __init__(self):
        self.client = OpenAI(api_key=os.getenv('OPENAI_API_KEY'))
        self.voice_mapping = {
            'matt': 'echo',  # Best male voice (out of a bad bunch lol)
            'mollie': 'nova'  # She's quite energetic
        }
        pygame.mixer.init()
        self.audio_queue = queue.Queue()
        self.is_playing = False
        
    def generate_and_play(self, speeches):
        """Start both generation and playback in parallel"""
        # Start the player thread
        player_thread = threading.Thread(target=self._play_from_queue)
        player_thread.start()
        
        # Generate and add to queue
        generator_thread = threading.Thread(target=self._generate_to_queue, args=(speeches,))
        generator_thread.start()
        
        # Wait for both threads to complete
        generator_thread.join()
        self.audio_queue.put(None)  # Signal end of generation
        player_thread.join()

    def _generate_to_queue(self, speeches):
        """Generate audio files and add them to the queue"""
        for i, speech in enumerate(speeches):
            voice_type = 'matt' if i % 2 == 0 else 'mollie'
            response = self.client.audio.speech.create(
                model="tts-1",
                voice=self.voice_mapping[voice_type],
                input=speech,
            )
            
            # Create a temporary file
            temp_file = tempfile.NamedTemporaryFile(delete=False, suffix='.mp3')
            for chunk in response.iter_bytes():
                temp_file.write(chunk)
            temp_file.flush()
            
            # Add to queue
            self.audio_queue.put(temp_file.name)
            print(f"Generated {'Matt' if i % 2 == 0 else 'Mollie'}'s line")

    def _play_from_queue(self, gap=0.3):
        """Play audio files as they become available in the queue"""
        while True:
            # Wait for a file to be available
            audio_file = self.audio_queue.get()
            
            # Check for end signal
            if audio_file is None:
                break
                
            print("Playing next line...")
            pygame.mixer.music.load(audio_file)
            pygame.mixer.music.play()
            
            while pygame.mixer.music.get_busy():
                pygame.time.Clock().tick(10)
            
            # Add a small gap between speakers
            time.sleep(gap)
            
            # Clean up
            pygame.mixer.music.unload()
            os.unlink(audio_file)