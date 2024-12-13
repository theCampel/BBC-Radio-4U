import pygame
import time
import os

class AudioPlayer:
    def __init__(self, visualiser=None):
        pygame.mixer.init()
        self.visualiser = visualiser
        self.is_playing = False

    def play_from_queue(self, audio_queue):
        """Play audio files as they arrive in the queue."""
        if self.visualiser:
            self.visualiser.init_display()

        while True:
            item = audio_queue.get()
            if item is None:
                # No more audio
                break

            (audio_file, speaker) = item
            self._play_file(audio_file, speaker)

            if self.visualiser:
                self.visualiser.reset()

        if self.visualiser:
            self.visualiser.quit_display()

    def _play_file(self, audio_file, speaker):
        pygame.mixer.music.load(audio_file)
        pygame.mixer.music.play()
        self.is_playing = True

        if self.visualiser:
            self.visualiser.set_current_audio(audio_file, speaker)

        while True:
            pos_ms = pygame.mixer.music.get_pos()
            if pos_ms == -1:
                # Playback finished
                break

            if self.visualiser:
                self.visualiser.update(pos_ms)

            time.sleep(0.01)

        pygame.mixer.music.stop()
        pygame.mixer.music.unload()
        self.is_playing = False
        if audio_file.startswith('/tmp'):
            os.unlink(audio_file)
