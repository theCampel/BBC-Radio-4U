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

    def generate_speech_files(self, speeches):
        """Generate audio files from speeches and return list of file paths."""
        generated_files = []
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
            temp_file.close()

            generated_files.append(temp_file.name)
        return generated_files
