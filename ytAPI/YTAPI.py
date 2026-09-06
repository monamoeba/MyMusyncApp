import os

import google_auth_oauthlib.flow
import google.oauth2.credentials
from googleapiclient.discovery import build
import requests
import yt_dlp
import re

class YTSource():
    def __init__(self) -> None:
        #built from env vars rather than a client_secret.json file on disk,
        #so there's no credential file that can accidentally end up in git
        self.client_config = {
            'web': {
                'client_id': os.environ['GOOGLE_OAUTH_CLIENT_ID'],
                'client_secret': os.environ['GOOGLE_OAUTH_CLIENT_SECRET'],
                'auth_uri': 'https://accounts.google.com/o/oauth2/auth',
                'token_uri': 'https://oauth2.googleapis.com/token',
            }
        }
        self.scopes = ['https://www.googleapis.com/auth/youtube.force-ssl']
        self.api_name = 'youtube'
        self.api_ver = 'v3'

    def authorise(self, redirect_uri):
        flow = google_auth_oauthlib.flow.Flow.from_client_config(
            self.client_config,
            scopes = self.scopes
        )
        flow.redirect_uri = redirect_uri
        authorisation_url, state = flow.authorization_url(
            access_type = 'offline',
            include_granted_scopes='true'
        )
        return authorisation_url, state

    def validateOAuthResponse(self, sesh_state, redirect_uri, auth_response):
        flow = google_auth_oauthlib.flow.Flow.from_client_config(
            self.client_config,
            scopes = self.scopes,
            state = sesh_state
        )
        flow.redirect_uri = redirect_uri
        flow.fetch_token(authorization_response = auth_response)
        return self.cred_to_dict(flow.credentials)

    def cred_to_dict(self, credentials):
        return {
            'token': credentials.token,
            'refresh_token': credentials.refresh_token,
            'token_uri': credentials.token_uri,
            'client_id': credentials.client_id,
            'client_secret': credentials.client_secret,
            'scopes': credentials.scopes
        }

    def getSingleplaylist(self, creds, play_id):
        credentials = google.oauth2.credentials.Credentials(
            **creds
        )
        service = build(self.api_name, self.api_ver, credentials=credentials)
        playlists_obj = service.playlists()

        api_request = playlists_obj.list(part='contentDetails, localizations, id, snippet', id = play_id, maxResults=1)
        response = api_request.execute()
        if len(response['items']) !=0:
            name = response['items'][0]['snippet']['title']
            return name
        else:
            return None


    def getPlaylists(self, creds):
        credentials = google.oauth2.credentials.Credentials(
            **creds
        )
        super_playlists = []
        service = build(self.api_name, self.api_ver, credentials=credentials)
        playlists_obj = service.playlists()
        api_request = playlists_obj.list(part='contentDetails, localizations, id, snippet', mine=True, maxResults=50)
        response = api_request.execute()

        if 'nextPageToken' in response:
            nextPageToken = response['nextPageToken']

            #the YouTube API caps each response at 50 items, so paginate
            #until there's no nextPageToken left
            while 'nextPageToken' in response:
                next_data = playlists_obj.list(
                    part = 'contentDetails, localizations, id, snippet',
                    mine=True,
                    maxResults = 50,
                    pageToken = nextPageToken
                )
                result = next_data.execute()
                response['items'] += result['items']

                if 'nextPageToken' not in result:
                    response.pop('nextPageToken', None)
                    break
                else:
                    nextPageToken = result['nextPageToken']

        super_playlists = self.filterPlaylistResponse(response)
        service.close()
        return super_playlists

    def getSongs(self, creds, play_id):
        credentials = google.oauth2.credentials.Credentials(
            **creds)
        service = build(self.api_name, self.api_ver, credentials=credentials)
        play_items = service.playlistItems()
        api_request = play_items.list(
            part='id, snippet, contentDetails, status',
            maxResults=5,
            playlistId=play_id
            )

        response = api_request.execute()

        if 'nextPageToken' in response:
            nextPageToken = response['nextPageToken']

            #paginate until there's no nextPageToken left
            while 'nextPageToken' in response:
                next_data = play_items.list(
                    part = 'id, snippet, contentDetails, status',
                    maxResults = 5,
                    playlistId=play_id,
                    pageToken = nextPageToken
                )
                result = next_data.execute()
                response['items'] += result['items']

                if 'nextPageToken' not in result:
                    response.pop('nextPageToken', None)
                    break
                else:
                    nextPageToken = result['nextPageToken']
        item_list = (self.filterVideoResponse(response))
        service.close()
        return item_list

    def createMusicList(self, video_list):
        unavailable_songs=[]
        available_songs=[]
        for video in video_list:
            vidId = video[1]
            ydl = yt_dlp.YoutubeDL({'ignoreerrors':True})
            song_info = ydl.extract_info(vidId, download=False)
            try:
                if song_info != None:
                    song_name = song_info['track']
                    song_artist = song_info['artist']
                    available_songs.append({
                        'title':song_name,
                        'artist':song_artist,
                    })
                    print(f'{song_name} - {song_artist}')
                else:
                    unavailable_songs.append(video)
                    print(f'unavailable - {video[0]}')
            except (KeyError, yt_dlp.DownloadError):
                unavailable_songs.append(video)
                print(f'unavailable - {video[0]}')

        extra_filter, unavailable_songs = self.superSongParser(unavailable_songs)
        available_songs += extra_filter
        #normalise the title/artist so they match better against Spotify's search:
        #"ft."/"feat." isn't part of the artist name Spotify indexes on, and
        #punctuation in a title often prevents an exact match
        for track in available_songs:
            if ' ft.' in track['artist']:
                track['artist'] = track['artist'].replace(' ft.', ',')
            elif ' feat.' in track['artist']:
                track['artist'] = track['artist'].replace(' feat.', ',')
            if track['title'].isalnum() == False:
                track['title'] = re.sub(r'[-()\/"#/@;:<>{}`+=~|.!?,]',r'',track['title'])
                track['chars_removed'] = True
        print(f'available: {available_songs}')
        return available_songs, unavailable_songs

    def superSongParser(self, video_list):
        #yt_dlp couldn't resolve official track metadata for these videos, so
        #fall back to guessing artist/title from common YouTube title
        #conventions, e.g. "Artist - Song (Official Music Video)"
        found_songs = []
        vid_copy = video_list.copy()
        for item in video_list:
            title = item[0].lower()
            sub_title = None
            if title.find('official') != -1:
                if title.find('official audio') !=-1:
                    sub_title = title.split('official audio')[0][:-2]
                elif title.find('official video')!=-1:
                    sub_title = title.split('official video')[0][:-2]
                elif title.find('official music video')!=-1:
                    sub_title = title.split('official music video')[0][:-2]
                elif title.find('official lyric video')!=-1:
                    sub_title = title.split('official lyric video')[0][:-2]

            if title.find('m/v')!= -1 or title.find('mv') != -1 and sub_title == None:
                if title.find('official m/v')!=-1:
                    sub_title = title.split('official m/v')[0][:-1]
                elif title.find('official mv')!=-1:
                    sub_title = title.split('official mv')[0][:-1]
                elif title.find(' m/v')!=-1:
                    sub_title = title.split(' m/v')[0]
            if title.find('audio')!=-1 and sub_title==None:
                if title.find('(audio)')!=-1 or title.find('[audio]')!=-1:
                    sub_title = title.split('audio')[0][:-2]
            if title.find('lyric')!=-1 and sub_title==None:
                if title.find('(lyrics)')!=-1 or title.find('[lyrics]')!=-1:
                    sub_title = title.split('lyrics')[0][:-2]
                elif title.find('(lyric video)')!=-1 or title.find('[lyric video]')!=-1:
                    sub_title = title.split('lyric video')[0][:-2]

            if sub_title != None:
                if sub_title.find(' - ')!=-1:
                    artist,song = sub_title.split(' - ')
                    found_songs.append({
                        'title':song,
                        'artist':artist
                    })
                    vid_copy.remove(item)
                elif sub_title.find(' — ')!=-1:
                    artist,song = sub_title.split(' — ')
                    found_songs.append({
                        'title':song,
                        'artist':artist
                    })
                    vid_copy.remove(item)
                elif sub_title.find(' by ')!=-1:
                    song,artist = sub_title.split(' by ')
                    found_songs.append({
                        'title':song,
                        'artist':artist
                    })
                    vid_copy.remove(item)
                elif sub_title.find('"')!=-1:
                    split_title= sub_title.split('"')
                    artist, song = split_title[0], split_title[1]
                    artist = artist.strip()
                    found_songs.append({
                        'title':song,
                        'artist':artist
                    })
                    vid_copy.remove(item)
                elif sub_title.find("'")!=-1:
                    split_title= sub_title.split('"')
                    artist, song = split_title[0], split_title[1]
                    artist = artist.strip()
                    found_songs.append({
                        'title':song,
                        'artist':artist
                    })
                    vid_copy.remove(item)
        return found_songs, vid_copy

    def filterVideoResponse(self, response):
        videos = []
        for item in response['items']:
            name = item['snippet']['title']
            vidId = item['contentDetails']['videoId']

            if item['status']['privacyStatus'] == 'public':
                if (name != 'Private video' or name !='Deleted video'):
                    vid_info = [name, vidId]
                    videos.append(vid_info)
        return videos


    def filterPlaylistResponse(self,response):
        playlists = []
        for element in response['items']:
            sub_playlist = {}
            sub_playlist['name'] = element['snippet']['title']
            sub_playlist['id'] = element['id']
            sub_playlist['no_vids'] = element['contentDetails']['itemCount']
            playlists.append(sub_playlist)
        return playlists

    def revokeToken(self, creds):
        credentials = google.oauth2.credentials.Credentials(
            **creds
        )
        requests.post('https://oauth2.googleapis.com/revoke',
            params = {'token': credentials.token},
            headers = {'content-type': 'application/x-www-form-urlencoded'})
