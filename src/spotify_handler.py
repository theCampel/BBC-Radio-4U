import os
import random
import spotipy
from spotipy.oauth2 import SpotifyOAuth

class SpotifyHandler:
    def __init__(self, username):
        """Initialise Spotify client with OAuth"""
        self.sp = spotipy.Spotify(auth_manager=SpotifyOAuth(
            username=username,
            client_id=os.getenv('SPOTIFY_CLIENT_ID'),
            client_secret=os.getenv('SPOTIFY_CLIENT_SECRET'),
            redirect_uri="http://www.example.com",
            scope="user-library-read user-modify-playback-state user-read-playback-state user-top-read"
        ))

    def get_random_top_song(self, limit=5):
        """
        Get user's top tracks and return a random one with artist and song name
        Args:
            limit (int): Number of top tracks to choose from
        Returns:
            dict: Contains name, artist and uri of the randomly selected track
        """
        top_tracks = self.sp.current_user_top_tracks(time_range='short_term', limit=limit)
        
        if not top_tracks['items']:
            return None
        
        random_track = random.choice(top_tracks['items'])
        return {
            'name': random_track['name'],
            'artist': random_track['artists'][0]['name'],
            'uri': random_track['uri']
        }

    def play_track(self, track_uri):
        """
        Play a specific track
        Args:
            track_uri (str): Spotify URI of the track to play
        """
        try:
            self.sp.start_playback(uris=[track_uri])
        except Exception as e:
            print(f"Error playing track: {e}") 