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
            scope="user-library-read user-modify-playback-state user-read-playback-state user-top-read playlist-read-private"
        ))

    def get_random_playlist_song(self, playlist_id, played_songs):
        """
        Get a random track from a given playlist that has not been played before.
        Args:
            playlist_id (str): Spotify playlist ID.
            played_songs (list): List of track URIs that have already been played.
        Returns:
            dict: Contains name, artist and uri of the randomly selected track, or None if no unique track is found.
        """
        # Fetch playlist tracks
        tracks = []
        results = self.sp.playlist_tracks(playlist_id)
        tracks.extend(results['items'])
        while results['next']:
            results = self.sp.next(results)
            tracks.extend(results['items'])
        
        # Filter only tracks (not episodes, local tracks, etc.)
        tracks = [t for t in tracks if t['track'] and t['track']['type'] == 'track']

        # Filter out tracks that have been played
        available_tracks = [t for t in tracks if t['track']['uri'] not in played_songs]

        if not available_tracks:
            return None

        chosen = random.choice(available_tracks)['track']
        return {
            'name': chosen['name'],
            'artist': chosen['artists'][0]['name'],
            'uri': chosen['uri']
        }

    def play_track(self, track_uri):
        """
        Play a specific track
        Args:
            track_uri (str): Spotify URI of the track to play
        """
        try:
            self.sp.start_playback(uris=[track_uri])
            self.sp.volume(60)
        except Exception as e:
            print(f"Error playing track: {e}")

    def get_remaining_time(self):
        """Returns remaining time in milliseconds, or None if not playing"""
        playback = self.sp.current_playback()
        if not playback or not playback.get('is_playing'):
            return None
        
        progress_ms = playback['progress_ms']
        total_ms = playback['item']['duration_ms']
        return total_ms - progress_ms
