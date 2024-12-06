# BBC-Radio-4U

A personalised radio station with seemless conversation between _two hosts_. It generates and plays dialogues based on recent news articles and the user's top music tracks.
Uses OpenAI's text-to-speech to generate audio. Made custom visualisation of audio with a dynamic sine wave. 
Made originally on a Sunday.

## Demo:

<div style="position: relative; width: 100%; padding-top: 56.25%; overflow: hidden;">
  <iframe src="https://www.youtube.com/embed/E8vLzDipnew" 
          style="position: absolute; top: 0; left: 0; width: 100%; height: 100%; border: 0;" 
          allow="accelerometer; autoplay; clipboard-write; encrypted-media; gyroscope; picture-in-picture" 
          allowfullscreen>
  </iframe>
</div>

## Features

- **News Article Processing**: Select and process news articles to generate dialogues.
- **Music Integration**: Integrates with Spotify to play random top songs.
- **Dynamic Dialogue Generation**: Uses OpenAI to generate dialogues based on news and music context.
- **Real-time Audio Visualisation**: Visualises audio playback with a dynamic sine wave animation.

## Next Steps:
- Filter out junk articles from the news API using fine-tuned local model (BERT?)
- Reduce costs by being more like a real radio station (minute or so of dialogue, then multiple songs)
- Give user more control over the music (allow them to select songs)
- Give user more control over the topics/style of the dialogue (allow them to select topics/styles)
  - Would be sick to have a juke-box style interface where you can select what's playing next / what they're talking about next.


## Running it yourself

1. Clone the repo
2. Install the dependencies (`pip install -r requirements.txt`)
3. Make sure you have a `.env` file with all relevant keys (OpenAI, Spotify (you'll have to set this up), etc.)
4. Run the script (`python main.py` lol)

## Contributing

This code is far from perfect. If you want to help it grow arms and legs, feel free!
