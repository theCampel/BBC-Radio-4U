import os
import pygame
import time

class AudioPlayer:
    def __init__(self, visualiser=None):
        pygame.mixer.init()
        self.visualiser = visualiser
        self.is_playing = False

    def play_files(self, audio_files):
        # Initialise the Pygame display if we have a visualiser
        if self.visualiser:
            self.visualiser.init_display()

        for audio_file in audio_files:
            self._play_file(audio_file)
            if self.visualiser:
                self.visualiser.reset()

        # Close display after finished
        if self.visualiser:
            self.visualiser.quit_display()

    def _play_file(self, audio_file):
        pygame.mixer.music.load(audio_file)
        pygame.mixer.music.play()
        self.is_playing = True

        while True:
            pos_ms = pygame.mixer.music.get_pos()
            if pos_ms == -1:
                # Playback finished
                break

            # Update visualiser if present
            if self.visualiser:
                self.visualiser.update(audio_file, pos_ms)

            time.sleep(0.01)

        pygame.mixer.music.stop()
        pygame.mixer.music.unload()
        self.is_playing = False
        # Optionally remove file if they are temporary
        if audio_file.startswith('/tmp'):
            os.unlink(audio_file)
