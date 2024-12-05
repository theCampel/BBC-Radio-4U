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

# Audio visualization constants
WINDOW_SIZE_MS = 50  # Sample window size in milliseconds
AMPLITUDE_HISTORY_SIZE = 20
AMPLITUDE_SCALING = 500  # Amplification factor for visualisation
WAVE_FREQUENCY = 6  # Number of wave cycles fit into screen
WAVE_PHASE_SPEED = 3  # Speed of horizontal wave movement

# Speaker colors
SPEAKER_COLORS = {
    'matt': (0, 0, 255),    # Blue
    'mollie': (255, 0, 0),  # Red
    'default': (0, 255, 0)  # Green
}

class VoiceGenerator:
    def __init__(self):
        self.client = OpenAI(api_key=os.getenv('OPENAI_API_KEY'))
        self.voice_mapping = {
            'matt': 'echo',   # Best male voice (of a bad bunch)
            'mollie': 'nova'  # Energetic female voice
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
        self.current_speaker = None  # Track the current speaker
        self.amplitude_history = []

    def generate_and_play(self, speeches):
        """Generate and play speeches with visualisation"""
        # Start the audio generation thread
        generator_thread = threading.Thread(target=self._generate_to_queue, args=(speeches,))
        generator_thread.start()

        # Initialize Pygame window for visualisation
        pygame.display.init()
        screen = pygame.display.set_mode((SCREEN_WIDTH, SCREEN_HEIGHT))
        pygame.display.set_caption('Audio Visualiser')
        clock = pygame.time.Clock()

        while not self.stop_signal.is_set():
            # Check if there is an audio file to play or currently playing
            if not self.is_playing and not self.audio_queue.empty():
                # Get the next audio data
                audio_data = self.audio_queue.get()
                if audio_data is None:
                    # No more audio files
                    self.stop_signal.set()
                    continue

                ### SETUP ###
                audio_file, voice_type = audio_data  # Unpack tuple

                # Weird structure - look into this
                audio_segment = AudioSegment.from_file(audio_file)
                audio_samples = np.array(audio_segment.get_array_of_samples())
                
                # Get the maximum integer value based on the data type
                # Different types of audio files can be 16bits or 32bits
                max_int_value = np.iinfo(audio_samples.dtype).max
                
                # Convert to float32 regardless of the data type
                audio_samples = audio_samples.astype(np.float32)
                
                # Normalize audio samples to [-1, 1]
                # We need this to plug into sine wave.
                audio_samples /= max_int_value


                sample_rate = audio_segment.frame_rate
                num_channels = audio_segment.channels
                # For stereo audio, take the mean of the two channels
                if num_channels == 2:
                    audio_samples = audio_samples.reshape((-1, 2))
                    audio_samples = audio_samples.mean(axis=1)

                # Store current audio data to be used in the visualisation
                with self.audio_lock:
                    self.current_audio_file = audio_file
                    self.current_audio_samples = audio_samples
                    self.current_sample_rate = sample_rate
                    self.current_audio_length = len(audio_segment)
                    self.current_speaker = voice_type  # Store the current speaker
                    self.amplitude_history = []  # Reset amplitude history for new audio

                # Load and play audio with Pygame
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
                # Get current playback position
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
                    # Let it continue playing and visualise it. 
                    with self.audio_lock:
                        audio_samples = self.current_audio_samples
                        sample_rate = self.current_sample_rate
                        current_speaker = self.current_speaker

                    # Sound is split into "samples" (measure of amplitude), this is getting a sliding window of samples.
                    current_sample = int(pos_ms * sample_rate / 1000)
                    window_size_samples = int(sample_rate * WINDOW_SIZE_MS / 1000)  # Convert ms to samples
                    start_sample = current_sample
                    end_sample = min(len(audio_samples), current_sample + window_size_samples)
                    window_samples = audio_samples[start_sample:end_sample]

                    # Compute average amplitude (RMS)
                    if len(window_samples) > 0:
                        amplitude = np.sqrt(np.mean(window_samples ** 2))
                    else:
                        amplitude = 0

                    # Append to amplitude history
                    self.amplitude_history.append(amplitude)
                    if len(self.amplitude_history) > AMPLITUDE_HISTORY_SIZE:
                        self.amplitude_history.pop(0)

                    # Apply smoothing to amplitude history, otherwise too noisy.
                    smoothed_amplitude = np.mean(self.amplitude_history)

                    # Amplify the amplitude variance
                    smoothed_amplitude *= AMPLITUDE_SCALING

                    # Use smoothed_amplitude to animate sine wave
                    x_positions = np.linspace(0, SCREEN_WIDTH, num=SCREEN_WIDTH)
                    phase_shift = time.time() * WAVE_PHASE_SPEED % (2 * np.pi)
                    y_positions = np.sin(2 * np.pi * WAVE_FREQUENCY * x_positions / SCREEN_WIDTH + phase_shift)

                    # Scale y_positions with the amplitude
                    y_positions *= smoothed_amplitude

                    # Center y_positions
                    y_positions = SCREEN_HEIGHT / 2 - y_positions

                    # Choose color based on speaker
                    color = SPEAKER_COLORS.get(current_speaker, SPEAKER_COLORS['default'])

                    # Draw the sine wave with a thinner line
                    points = list(zip(x_positions, y_positions))
                    if len(points) > 1:
                        pygame.draw.lines(screen, color, False, points, 1)  # Line width of 1
            else:
                # No audio is playing
                pass  # You can add idle animations here if desired

            # Update display
            pygame.display.flip()

            # Tick clock
            clock.tick(FPS)

        # Wait for the generator thread to finish
        generator_thread.join()
        # Quit Pygame display
        pygame.display.quit()

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

            # Add to queue with voice type
            self.audio_queue.put((temp_file.name, voice_type))

        # Signal that no more audio files will be added
        self.audio_queue.put(None)
