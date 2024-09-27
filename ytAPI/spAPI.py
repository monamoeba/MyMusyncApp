import spotipy
from spotipy.oauth2 import SpotifyOAuth
import requests
import time
class SPDest:
    def __init__(self):
        self.client_id = '5817c0bb6f1647a4ab2e1be3292b1f92'
        self.client_secret = '5a4b7714bd7a4111a0263332ebca1857'
        self.scopes = 'playlist-read-private,playlist-modify-private,playlist-read-collaborative,playlist-modify-public,user-read-private'
    

    def spAuthorise(self):
        #creating a spotify object that will begin the auth process
        sp_auth = SpotifyOAuth(
            #setting the scopes, information and redirect uri for the process
            scope = self.scopes,
            client_id=self.client_id,
            client_secret=self.client_secret,
            redirect_uri='https://127.0.0.1:8000/spdestcallback/'
        )
        #retrieving the url to direct users to 
        authorisation_url = sp_auth.get_authorize_url()
        return authorisation_url

    def spValidateResponse(self, code, cache=None):
        #setting up the spotify object again
        sp_auth = SpotifyOAuth(
            #setting the scopes, information and redirect uri for the process
            scope = self.scopes,
            client_id=self.client_id,
            client_secret=self.client_secret,
            redirect_uri='https://127.0.0.1:8000/spdestcallback/',
            cache_handler=cache

        )
        #retrieve the token
        #code is passed in from main code where the request url is parsed
        #the request url will contain the code as a parameter
        #token = sp_auth.get_cached_token()
        if sp_auth.get_cached_token() == None:
            token = sp_auth.get_access_token(code=code)
            #return the token so that it can be stored in a session
            return token
        else:
            return sp_auth.get_cached_token()

    def spCreatePlaylist(self,token, play_name, play_desc, play_setting,cache=None):
        #create object for API
        sp= spotipy.Spotify(auth=token['access_token'])

        #get the user's userID
        user_id = sp.me()['id']
        #format of API request
        #user_playlist_create(user, name, public=True, collaborative=False, description='')
        try:
            new_playlist = sp.user_playlist_create(user=user_id, name=play_name, description=play_desc, public=play_setting)
        except spotipy.exceptions.SpotifyException:
            sp_auth = SpotifyOAuth(
            #setting the scopes, information and redirect uri for the process
            scope = self.scopes,
            client_id=self.client_id,
            client_secret=self.client_secret,
            redirect_uri='https://127.0.0.1:8000/spdestcallback/',
            cache_handler=cache
            )
            new_token = sp_auth.refresh_access_token(token['refresh_token'])
            sp = spotipy.Spotify(auth=new_token['access_token'])
            new_playlist = sp.user_playlist_create(user=user_id, name=play_name, description=play_desc, public=play_setting)
        #get the playlistID from the response
        play_id = new_playlist['id']
        return play_id
    
    def searchForURI(self, token, track_name, track_artist,char_removed=None, cache=None):
        #creates spotify api object
        sp = spotipy.Spotify(auth=token['access_token'])
        
        #creates query for the search
        #checks if the title/artist name contains foreign characters
        if track_artist.isascii() == False or track_name.isascii() == False or char_removed == True:
            #allows the query to show results if foreign chars present
            query = f'{track_name} {track_artist}'
        else:
            #if both are in english, normal query structure applies
            query = f'artist:{track_artist} track:{track_name}'
        #executes the search request using the API
        try:
            response = sp.search(q=query,limit=2, type='track')
        except spotipy.exceptions.SpotifyException:
            sp_auth = SpotifyOAuth(
            #setting the scopes, information and redirect uri for the process
            scope = self.scopes,
            client_id=self.client_id,
            client_secret=self.client_secret,
            redirect_uri='https://127.0.0.1:8000/spdestcallback/',
            cache_handler=cache
            )
            new_token = sp_auth.refresh_access_token(token['refresh_token'])
            sp = spotipy.Spotify(auth=new_token['access_token'])
            response = sp.search(q=query,limit=2, type='track')
        if response['tracks']['total'] == 0:
            #retry query with the track and artist swapped in case
            #they were filtered wrongly
            query = f'artist:{track_name} track:{track_artist}'
            response = sp.search(q = query, limit=2, type='track')
            #if this result is empty, it suggests the song doesn't exist
            #therefore return None
            if response['tracks']['total'] == 0:
                return None
            else:
                #retrieving the song_uri if the result is not empty
                song_uri = response['tracks']['items'][0]['uri']
        else:
            song_uri = response['tracks']['items'][0]['uri']

        return song_uri
        
    def transferSongs(self, token, song_list, playlist_id):
        #create a list to store spotify track URIs and unavaiable songs
        uri_list = []
        transfer_unavailable = []
        for item in song_list:
            if 'chars_removed' in item:
                song_uri_request = self.searchForURI(token, item['title'], item['artist'],True)
            else:
                song_uri_request = self.searchForURI(token, item['title'], item['artist'])
            if song_uri_request == None:
                #if the song doesn't exist in spotify append to unavailable list
                transfer_unavailable.append(item)
            else:
                #add to list of song_uris to be transferred in the next step
                uri_list.append(song_uri_request)
        #create sp object
        sp = spotipy.Spotify(auth = token['access_token'])
        #add transfer the songs to the new playlist
        if len(uri_list) != 0:
            addToPlaylist = sp.playlist_add_items(playlist_id=playlist_id, items=uri_list)
        #print the response
            print(addToPlaylist)
        return uri_list, transfer_unavailable
                

    def refreshTokenCheck(self, token):
        sp = spotipy.SpotifyOAuth(
            client_id= self.client_id,
            client_secret = self.client_secret
            )
        pass