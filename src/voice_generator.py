import os
import queue
import tempfile
import threading
import time

import numpy as np
import pygame
from openai import OpenAI
from pydub import AudioSegment

# Display constants
SCREEN_WIDTH = 600
SCREEN_HEIGHT = 300
BACKGROUND_COLOR = (255, 255, 255)  # White background
FPS = 60

# Audio visualisation constants
WINDOW_SIZE_MS = 100
AMPLITUDE_HISTORY_SIZE = 20
AMPLITUDE_SCALING = 700
WAVE_FREQUENCY = 1       # One full cycle across screen width
WAVE_PHASE_SPEED = 2      # Speed at which the wave travels horizontally

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
        """Generate and play the given speeches with a visualisation."""
        
        self.stop_signal.clear()

        # Start audio generation in a separate thread
        # This allows both speeches to play sequentially without any delay
        generator_thread = threading.Thread(target=self._generate_to_queue, args=(speeches,))
        generator_thread.start()

        # Initialise Pygame window for visualisation
        pygame.display.init()
        screen = pygame.display.set_mode((SCREEN_WIDTH, SCREEN_HEIGHT))
        pygame.display.set_caption('Audio Visualiser')
        clock = pygame.time.Clock()

        # Main loop
        while not self.stop_signal.is_set():
            # Load next audio from queue if not playing
            if not self.is_playing and not self.audio_queue.empty():
                audio_data = self.audio_queue.get()
                if audio_data is None:
                    # No more audio files: stop playback
                    self.stop_signal.set()
                    continue

                audio_file, voice_type = audio_data
                self._load_audio(audio_file, voice_type)

            # Handle Pygame events
            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    pygame.quit()
                    self.stop_signal.set()
                    return

            screen.fill(BACKGROUND_COLOR)

            if self.is_playing:
                self._update_visualisation(screen)
            else:
                # No audio playing
                # If you have time, render a nice idle animation here.
                pass

            pygame.display.flip()
            clock.tick(FPS)

        # Wait for generation thread to finish
        generator_thread.join()
        pygame.display.quit()

    def _load_audio(self, audio_file, voice_type):
        """Load and prepare audio data for playback and visualisation."""
        audio_segment = AudioSegment.from_file(audio_file)
        
        # Check obsidian notes on audio samples
        audio_samples = np.array(audio_segment.get_array_of_samples())
        
        # Convert to float32 and normalise (as you may get diff types of audio samples)
        max_int_value = np.iinfo(audio_samples.dtype).max
        audio_samples = audio_samples.astype(np.float32)
        audio_samples /= max_int_value

        sample_rate = audio_segment.frame_rate
        num_channels = audio_segment.channels
        if num_channels == 2:
            audio_samples = audio_samples.reshape((-1, 2)).mean(axis=1)

        # Store audio data to self (allows threading)
        with self.audio_lock:
            self.current_audio_file = audio_file
            self.current_audio_samples = audio_samples
            self.current_sample_rate = sample_rate
            self.current_audio_length = len(audio_segment)
            self.current_speaker = voice_type
            self.amplitude_history = []

        # Actually load and start playing audio
        pygame.mixer.music.load(audio_file)
        pygame.mixer.music.play()
        self.is_playing = True

    def _update_visualisation(self, screen):
        """Update the wave visualisation based on current audio playback."""
        pos_ms = pygame.mixer.music.get_pos()

        # Check if playback finished
        if pos_ms == -1 or pos_ms >= self.current_audio_length:
            self._cleanup_after_playback()
            return

        # Compute amplitude
        with self.audio_lock:
            audio_samples = self.current_audio_samples
            sample_rate = self.current_sample_rate
            current_speaker = self.current_speaker

        # Read obsidian notes on audio samples
        # Basically, take average amplitude of sliding window of audio samples
        current_sample = int(pos_ms * sample_rate / 1000)
        window_size_samples = int(sample_rate * WINDOW_SIZE_MS / 1000)
        end_sample = min(len(audio_samples), current_sample + window_size_samples)
        window_samples = audio_samples[current_sample:end_sample]

        amplitude = np.sqrt(np.mean(window_samples ** 2)) if len(window_samples) > 0 else 0
        self.amplitude_history.append(amplitude)
        if len(self.amplitude_history) > AMPLITUDE_HISTORY_SIZE:
            self.amplitude_history.pop(0)

        smoothed_amplitude = np.mean(self.amplitude_history) * AMPLITUDE_SCALING

        # Compute wave positions
        x_positions = np.linspace(0, SCREEN_WIDTH, num=SCREEN_WIDTH)
        phase_shift = time.time() * WAVE_PHASE_SPEED
        base_wave = np.sin(2 * np.pi * (WAVE_FREQUENCY * (x_positions / SCREEN_WIDTH) - phase_shift))

        # Draw layered "shadow" waves
        color = SPEAKER_COLORS.get(current_speaker, SPEAKER_COLORS['default'])
        R, G, B = color
        num_layers = 4
        for i in range(num_layers):
            alpha = (i + 1) / (num_layers + 1)
            layer_R = int(R + (255 - R) * alpha)
            layer_G = int(G + (255 - G) * alpha)
            layer_B = int(B + (255 - B) * alpha)
            layer_color = (layer_R, layer_G, layer_B)

            scale = 1.0 - (i * 0.25)
            layer_amp = smoothed_amplitude * scale
            layer_y_positions = (SCREEN_HEIGHT / 2) - (layer_amp * base_wave)
            layer_points = list(zip(x_positions, layer_y_positions))

            pygame.draw.lines(screen, layer_color, False, layer_points, 2)

        # Draw main wave line
        main_y_positions = (SCREEN_HEIGHT / 2) - (smoothed_amplitude * base_wave)
        main_points = list(zip(x_positions, main_y_positions))
        pygame.draw.lines(screen, color, False, main_points, 2)

    def _cleanup_after_playback(self):
        """Reset state after an audio segment finishes playing."""
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

    def _generate_to_queue(self, speeches):
        """Generate audio files from speeches and add them to the playback queue."""
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
