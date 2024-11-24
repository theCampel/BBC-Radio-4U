import sounddevice as sd
import numpy as np
import io

class AudioStreamer:
    def __init__(self, sample_rate=24000):
        self.sample_rate = sample_rate

    def stream_dialogue(self, matt_stream, mollie_stream):

        # Convert the audio streams to numpy arrays
        matt_audio = np.frombuffer(matt_stream.content, dtype=np.float32)
        mollie_audio = np.frombuffer(mollie_stream.content, dtype=np.float32)
        
        # Sequential playback
        sd.play(matt_audio, self.sample_rate)
        sd.wait()  # Wait until Matt finished
        sd.play(mollie_audio, self.sample_rate)
        sd.wait()  # Wait until Mollie finished 