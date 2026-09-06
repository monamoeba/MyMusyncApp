import os

import spotipy
from spotipy.oauth2 import SpotifyOAuth
import requests

from django.conf import settings
from django.urls import reverse

class SPDest:
    def __init__(self):
        self.client_id = os.environ['SPOTIFY_CLIENT_ID']
        self.client_secret = os.environ['SPOTIFY_CLIENT_SECRET']
        self.scopes = 'playlist-read-private,playlist-modify-private,playlist-read-collaborative,playlist-modify-public,user-read-private'

    @property
    def redirect_uri(self):
        #computed lazily (not in __init__) because SPDest is instantiated at
        #import time in views.py, before the URLconf has finished loading -
        #calling reverse() any earlier would be a circular import
        return settings.SITE_BASE_URL + reverse('ytAPI:SPoauth2callback')

    def spAuthorise(self):
        sp_auth = SpotifyOAuth(
            scope = self.scopes,
            client_id=self.client_id,
            client_secret=self.client_secret,
            redirect_uri=self.redirect_uri
        )
        authorisation_url = sp_auth.get_authorize_url()
        return authorisation_url

    def spValidateResponse(self, code, cache=None):
        sp_auth = SpotifyOAuth(
            scope = self.scopes,
            client_id=self.client_id,
            client_secret=self.client_secret,
            redirect_uri=self.redirect_uri,
            cache_handler=cache
        )
        if sp_auth.get_cached_token() == None:
            token = sp_auth.get_access_token(code=code)
            return token
        else:
            return sp_auth.get_cached_token()

    def spCreatePlaylist(self,token, play_name, play_desc, play_setting,cache=None):
        sp= spotipy.Spotify(auth=token['access_token'])
        user_id = sp.me()['id']
        try:
            new_playlist = sp.user_playlist_create(user=user_id, name=play_name, description=play_desc, public=play_setting)
        except spotipy.exceptions.SpotifyException:
            sp_auth = SpotifyOAuth(
            scope = self.scopes,
            client_id=self.client_id,
            client_secret=self.client_secret,
            redirect_uri=self.redirect_uri,
            cache_handler=cache
            )
            new_token = sp_auth.refresh_access_token(token['refresh_token'])
            sp = spotipy.Spotify(auth=new_token['access_token'])
            new_playlist = sp.user_playlist_create(user=user_id, name=play_name, description=play_desc, public=play_setting)
        play_id = new_playlist['id']
        return play_id

    def searchForURI(self, token, track_name, track_artist,char_removed=None, cache=None):
        sp = spotipy.Spotify(auth=token['access_token'])

        #Spotify's `artist:`/`track:` field search only works reliably for
        #ASCII text, so fall back to a plain keyword search for non-Latin titles
        if track_artist.isascii() == False or track_name.isascii() == False or char_removed == True:
            query = f'{track_name} {track_artist}'
        else:
            query = f'artist:{track_artist} track:{track_name}'
        try:
            response = sp.search(q=query,limit=2, type='track')
        except spotipy.exceptions.SpotifyException:
            sp_auth = SpotifyOAuth(
            scope = self.scopes,
            client_id=self.client_id,
            client_secret=self.client_secret,
            redirect_uri=self.redirect_uri,
            cache_handler=cache
            )
            new_token = sp_auth.refresh_access_token(token['refresh_token'])
            sp = spotipy.Spotify(auth=new_token['access_token'])
            response = sp.search(q=query,limit=2, type='track')
        if response['tracks']['total'] == 0:
            #retry with track/artist swapped in case they were misidentified
            query = f'artist:{track_name} track:{track_artist}'
            response = sp.search(q = query, limit=2, type='track')
            if response['tracks']['total'] == 0:
                return None
            else:
                song_uri = response['tracks']['items'][0]['uri']
        else:
            song_uri = response['tracks']['items'][0]['uri']

        return song_uri

    def transferSongs(self, token, song_list, playlist_id):
        uri_list = []
        transfer_unavailable = []
        for item in song_list:
            if 'chars_removed' in item:
                song_uri_request = self.searchForURI(token, item['title'], item['artist'],True)
            else:
                song_uri_request = self.searchForURI(token, item['title'], item['artist'])
            if song_uri_request == None:
                transfer_unavailable.append(item)
            else:
                uri_list.append(song_uri_request)
        sp = spotipy.Spotify(auth = token['access_token'])
        if len(uri_list) != 0:
            addToPlaylist = sp.playlist_add_items(playlist_id=playlist_id, items=uri_list)
            print(addToPlaylist)
        return uri_list, transfer_unavailable


    def refreshTokenCheck(self, token):
        sp = spotipy.SpotifyOAuth(
            client_id= self.client_id,
            client_secret = self.client_secret
            )
        pass
