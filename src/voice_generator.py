import os
import tempfile
from openai import OpenAI

class VoiceGenerator:
    def __init__(self):
        self.client = OpenAI(api_key=os.getenv('OPENAI_API_KEY'))
        self.voice_mapping = {
            'matt': 'echo',
            'mollie': 'nova'
        }

    def generate_to_queue(self, speeches, output_queue):
        """Generate audio files from speeches and put them into a queue as they become available."""
        for i, speech in enumerate(speeches):
            voice_type = 'matt' if i % 2 == 0 else 'mollie'
            response = self.client.audio.speech.create(
                model="tts-1",
                voice=self.voice_mapping[voice_type],
                input=speech,
            )

            # Name temp file with speaker info for clarity
            temp_file = tempfile.NamedTemporaryFile(delete=False, suffix=f"_{voice_type}.mp3")
            for chunk in response.iter_bytes():
                temp_file.write(chunk)
            temp_file.flush()
            temp_file.close()

            # Put filename and speaker to queue
            output_queue.put((temp_file.name, voice_type))

        # Signal no more speeches
        output_queue.put(None)
