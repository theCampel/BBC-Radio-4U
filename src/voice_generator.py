import os
from openai import OpenAI
import tempfile
import numpy as np
from pydub import AudioSegment
import pygame
import time
import threading
import queue

# Display constants
SCREEN_WIDTH = 600
SCREEN_HEIGHT = 300
BACKGROUND_COLOR = (255, 255, 255)  # White
FPS = 60

# Audio visualisation constants
WINDOW_SIZE_MS = 50
AMPLITUDE_HISTORY_SIZE = 20
AMPLITUDE_SCALING = 500
WAVE_FREQUENCY = 6
WAVE_PHASE_SPEED = 3

# Speaker colors
SPEAKER_COLORS = {
    'matt': (0, 0, 255),
    'mollie': (255, 0, 0),
    'default': (0, 255, 0)
}

class VoiceGenerator:
    def __init__(self):
        self.client = OpenAI(api_key=os.getenv('OPENAI_API_KEY'))
        self.voice_mapping = {
            'matt': 'echo',
            'mollie': 'nova'
        }
        pygame.mixer.init()
        self.audio_queue = queue.Queue()
        self.is_playing = False
        self.stop_signal = threading.Event()
        self.audio_lock = threading.Lock()
        self.current_audio_file = None
        self.current_audio_samples = None
        self.current_sample_rate = None
        self.current_audio_length = None
        self.current_speaker = None
        self.amplitude_history = []

    def generate_and_play(self, speeches):
        """Generate and play speeches with visualisation"""
        # Clear the stop signal to allow re-running this method
        self.stop_signal.clear()

        # Start the audio generation thread
        generator_thread = threading.Thread(target=self._generate_to_queue, args=(speeches,))
        generator_thread.start()

        # Initialize Pygame window for visualisation (fresh start each call)
        pygame.display.init()
        screen = pygame.display.set_mode((SCREEN_WIDTH, SCREEN_HEIGHT))
        pygame.display.set_caption('Audio Visualiser')
        clock = pygame.time.Clock()

        while not self.stop_signal.is_set():
            # Check if there is an audio file to play or currently playing
            if not self.is_playing and not self.audio_queue.empty():
                audio_data = self.audio_queue.get()
                if audio_data is None:
                    # No more audio files: stop and break the loop
                    self.stop_signal.set()
                    continue

                audio_file, voice_type = audio_data
                audio_segment = AudioSegment.from_file(audio_file)
                audio_samples = np.array(audio_segment.get_array_of_samples())
                max_int_value = np.iinfo(audio_samples.dtype).max
                audio_samples = audio_samples.astype(np.float32)
                audio_samples /= max_int_value

                sample_rate = audio_segment.frame_rate
                num_channels = audio_segment.channels
                if num_channels == 2:
                    audio_samples = audio_samples.reshape((-1, 2))
                    audio_samples = audio_samples.mean(axis=1)

                with self.audio_lock:
                    self.current_audio_file = audio_file
                    self.current_audio_samples = audio_samples
                    self.current_sample_rate = sample_rate
                    self.current_audio_length = len(audio_segment)
                    self.current_speaker = voice_type
                    self.amplitude_history = []

                pygame.mixer.music.load(audio_file)
                pygame.mixer.music.play()
                self.is_playing = True

            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    pygame.quit()
                    self.stop_signal.set()
                    return

            screen.fill(BACKGROUND_COLOR)

            if self.is_playing:
                pos_ms = pygame.mixer.music.get_pos()
                if pos_ms == -1 or pos_ms >= self.current_audio_length:
                    # Playback finished
                    pygame.mixer.music.stop()
                    pygame.mixer.music.unload()
                    os.unlink(self.current_audio_file)
                    with self.audio_lock:
                        self.current_audio_file = None
                        self.current_audio_samples = None
                        self.current_sample_rate = None
                        self.current_audio_length = None
                        self.current_speaker = None
                        self.amplitude_history = []
                    self.is_playing = False
                else:
                    with self.audio_lock:
                        audio_samples = self.current_audio_samples
                        sample_rate = self.current_sample_rate
                        current_speaker = self.current_speaker

                    current_sample = int(pos_ms * sample_rate / 1000)
                    window_size_samples = int(sample_rate * WINDOW_SIZE_MS / 1000)
                    start_sample = current_sample
                    end_sample = min(len(audio_samples), current_sample + window_size_samples)
                    window_samples = audio_samples[start_sample:end_sample]

                    amplitude = np.sqrt(np.mean(window_samples ** 2)) if len(window_samples) > 0 else 0
                    self.amplitude_history.append(amplitude)
                    if len(self.amplitude_history) > AMPLITUDE_HISTORY_SIZE:
                        self.amplitude_history.pop(0)

                    smoothed_amplitude = np.mean(self.amplitude_history)
                    smoothed_amplitude *= AMPLITUDE_SCALING

                    x_positions = np.linspace(0, SCREEN_WIDTH, num=SCREEN_WIDTH)
                    phase_shift = time.time() * WAVE_PHASE_SPEED % (2 * np.pi)
                    y_positions = np.sin(2 * np.pi * WAVE_FREQUENCY * x_positions / SCREEN_WIDTH + phase_shift)

                    y_positions *= smoothed_amplitude
                    y_positions = SCREEN_HEIGHT / 2 - y_positions

                    color = SPEAKER_COLORS.get(current_speaker, SPEAKER_COLORS['default'])

                    points = list(zip(x_positions, y_positions))
                    if len(points) > 1:
                        pygame.draw.lines(screen, color, False, points, 1)
            else:
                # No audio playing, just idle
                pass

            pygame.display.flip()
            clock.tick(FPS)

        # Wait for the generator thread to finish
        generator_thread.join()
        pygame.display.quit()  # Close the Pygame display after done

    def _generate_to_queue(self, speeches):
        """Generate audio files and add them to the queue"""
        for i, speech in enumerate(speeches):
            voice_type = 'matt' if i % 2 == 0 else 'mollie'
            response = self.client.audio.speech.create(
                model="tts-1",
                voice=self.voice_mapping[voice_type],
                input=speech,
            )

            temp_file = tempfile.NamedTemporaryFile(delete=False, suffix='.mp3')
            for chunk in response.iter_bytes():
                temp_file.write(chunk)
            temp_file.flush()

            self.audio_queue.put((temp_file.name, voice_type))

        self.audio_queue.put(None)
