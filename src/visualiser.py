import pygame
import time
import numpy as np
from pydub import AudioSegment

SCREEN_WIDTH = 600
SCREEN_HEIGHT = 300
BACKGROUND_COLOR = (255, 255, 255)
FPS = 60

WINDOW_SIZE_MS = 100
AMPLITUDE_HISTORY_SIZE = 20
AMPLITUDE_SCALING = 700
WAVE_FREQUENCY = 1
WAVE_PHASE_SPEED = 2

SPEAKER_COLORS = {
    'matt': (0, 0, 255),
    'mollie': (255, 0, 0),
    'default': (0, 255, 0)
}

class Visualiser:
    def __init__(self):
        self.screen = None
        self.clock = None
        self.current_audio_samples = None
        self.current_sample_rate = None
        self.current_audio_length = None
        self.current_speaker = None
        self.amplitude_history = []

    def init_display(self):
        pygame.display.init()
        self.screen = pygame.display.set_mode((SCREEN_WIDTH, SCREEN_HEIGHT))
        pygame.display.set_caption('Audio Visualiser')
        self.clock = pygame.time.Clock()

    def quit_display(self):
        pygame.display.quit()

    def reset(self):
        self.current_audio_samples = None
        self.current_sample_rate = None
        self.current_audio_length = None
        self.current_speaker = None
        self.amplitude_history = []

    def update(self, audio_file, pos_ms):
        # Check for pygame events (e.g., window close)
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                pygame.quit()

        # If we haven't loaded samples, load now
        if self.current_audio_samples is None:
            self._load_audio_data(audio_file)

        self.screen.fill(BACKGROUND_COLOR)

        if self.current_audio_samples is not None:
            self._draw_wave(pos_ms)

        pygame.display.flip()
        self.clock.tick(FPS)

    def _load_audio_data(self, audio_file):
        audio_segment = AudioSegment.from_file(audio_file)
        audio_samples = np.array(audio_segment.get_array_of_samples(), dtype=np.float32)
        max_int_value = np.iinfo(np.int16).max
        audio_samples = audio_samples / max_int_value
        sample_rate = audio_segment.frame_rate
        num_channels = audio_segment.channels
        if num_channels == 2:
            audio_samples = audio_samples.reshape((-1, 2)).mean(axis=1)

        self.current_audio_samples = audio_samples
        self.current_sample_rate = sample_rate
        self.current_audio_length = len(audio_segment)
        
        # Infer speaker from filename (assuming naming convention)
        # e.g. speech_1_matt.mp3 -> speaker = 'matt'
        speaker_name = 'default'
        if 'matt' in audio_file:
            speaker_name = 'matt'
        elif 'mollie' in audio_file:
            speaker_name = 'mollie'
        self.current_speaker = speaker_name
        self.amplitude_history = []

    def _draw_wave(self, pos_ms):
        pos = pos_ms
        if pos == -1 or pos >= self.current_audio_length:
            return

        current_sample = int(pos * self.current_sample_rate / 1000)
        window_size_samples = int(self.current_sample_rate * WINDOW_SIZE_MS / 1000)
        end_sample = min(len(self.current_audio_samples), current_sample + window_size_samples)
        window_samples = self.current_audio_samples[current_sample:end_sample]

        amplitude = np.sqrt(np.mean(window_samples ** 2)) if len(window_samples) > 0 else 0
        self.amplitude_history.append(amplitude)
        if len(self.amplitude_history) > AMPLITUDE_HISTORY_SIZE:
            self.amplitude_history.pop(0)

        smoothed_amplitude = np.mean(self.amplitude_history) * AMPLITUDE_SCALING

        x_positions = np.linspace(0, SCREEN_WIDTH, num=SCREEN_WIDTH)
        phase_shift = time.time() * WAVE_PHASE_SPEED
        base_wave = np.sin(2 * np.pi * (WAVE_FREQUENCY * (x_positions / SCREEN_WIDTH) - phase_shift))

        color = SPEAKER_COLORS.get(self.current_speaker, SPEAKER_COLORS['default'])
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

            pygame.draw.lines(self.screen, layer_color, False, layer_points, 2)

        # Draw main wave line
        main_y_positions = (SCREEN_HEIGHT / 2) - (smoothed_amplitude * base_wave)
        main_points = list(zip(x_positions, main_y_positions))
        pygame.draw.lines(self.screen, color, False, main_points, 2)
