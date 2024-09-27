import google_auth_oauthlib.flow
import google.oauth2.credentials
from googleapiclient.discovery import build
import requests
import youtube_dl, yt_dlp
import urllib
import re

class YTSource():
    def __init__(self) -> None:
        self.client_secrets = 'ytAPI/client_secret.json'
        self.scopes = ['https://www.googleapis.com/auth/youtube.force-ssl']
        self.api_name = 'youtube'
        self.api_ver = 'v3'
    
    def authorise(self, redirect_uri):
        #create a flow object using google's python client
        flow = google_auth_oauthlib.flow.Flow.from_client_secrets_file(
            self.client_secrets,
            scopes = self.scopes
        )
        #set a redirect uri
        flow.redirect_uri = redirect_uri
        authorisation_url, state = flow.authorization_url(
            access_type = 'offline',
            include_granted_scopes='true'
        )
        return authorisation_url, state

    def validateOAuthResponse(self, sesh_state, redirect_uri, auth_response):
        #retrieve session state from main program
        state = sesh_state
        #rebuild flow object w/ state
        flow = google_auth_oauthlib.flow.Flow.from_client_secrets_file(
            self.client_secrets,
            scopes = self.scopes,
            state = state
        )
        #set redirect uri after validation of response
        flow.redirect_uri = redirect_uri
        #fetch OAuth tokens
        flow.fetch_token(authorization_response = auth_response)

        #store the response/credentials that are returned
        credentials = self.cred_to_dict(flow.credentials)

        #return the credentials so that they can be stored in the session
        return credentials

    def cred_to_dict(self, credentials):
        #function that retrieves values from the credential object
        #stores them in a dictionary to make it easier to manage
        cred_dict = {
            'token': credentials.token,
            'refresh_token': credentials.refresh_token,
            'token_uri': credentials.token_uri,
            'client_id': credentials.client_id,
            'client_secret': credentials.client_secret,
            'scopes': credentials.scopes
        }
        return cred_dict

    def getSingleplaylist(self, creds, play_id):
        #save the credentials using google's oauth library
        credentials = google.oauth2.credentials.Credentials(
            **creds
        )
        #creates the api request object
        service = build(self.api_name, self.api_ver, credentials=credentials)
        playlists_obj = service.playlists()
        
        #sends request to the server
        api_request = playlists_obj.list(part='contentDetails, localizations, id, snippet', id = play_id, maxResults=1)
        #execute the response
        response = api_request.execute()
        if len(response['items']) !=0:
            #retrieve and return the name of the playlist
            name = response['items'][0]['snippet']['title']
            return name
        else: 
            return None


    def getPlaylists(self, creds):
        #save the credentials using google's oauth library
        credentials = google.oauth2.credentials.Credentials(
            **creds
        )
        #sets up a list to contain all playlists on the user's account
        super_playlists = []
        #set up the service object 
        #in this case, api_name and api_ver are set as 'youtube' and 'v3' respectively when the
        #class obect was initiated
        service = build(self.api_name, self.api_ver, credentials=credentials)
        playlists_obj = service.playlists()
        api_request = playlists_obj.list(part='contentDetails, localizations, id, snippet', mine=True, maxResults=50)
        #the request is executed and the result is filtered for specific information
        response = api_request.execute()

        if 'nextPageToken' in response:
            nextPageToken = response['nextPageToken']

            #creating a loop to retrieve ALL playlists (maximum is 50 per response)
            while 'nextPageToken' in response:
                next_data = playlists_obj.list(
                    part = 'contentDetails, localizations, id, snippet',
                    mine=True,
                    maxResults = 50,
                    pageToken = nextPageToken
                )
                result = next_data.execute()
                #concatanating results into the main response
                response['items'] += result['items']

                if 'nextPageToken' not in result:
                    #breaks loop by removing the nextpagetoken
                    response.pop('nextPageToken', None)
                    break
                else:
                    nextPageToken = result['nextPageToken']

        super_playlists = self.filterPlaylistResponse(response)
        service.close()
        return super_playlists

    def getSongs(self, creds, play_id):
        #create credentials + service object to call the API
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

            #creating a loop to retrieve ALL videos (maximum is 50 per response)
            while 'nextPageToken' in response:
                next_data = play_items.list(
                    part = 'id, snippet, contentDetails, status',
                    maxResults = 5,
                    playlistId=play_id,
                    pageToken = nextPageToken
                )
                result = next_data.execute()
                #concatanating results into the main response
                response['items'] += result['items']

                if 'nextPageToken' not in result:
                    #breaks loop by removing the nextpagetoken
                    response.pop('nextPageToken', None)
                    break
                else:
                    nextPageToken = result['nextPageToken']
        item_list = (self.filterVideoResponse(response))
        service.close()
        #returns a list of videos in the playlist along with their videoId
        return item_list

    #find the track title and artist of each video/song
    def createMusicList(self, video_list):
        unavailable_songs=[]
        available_songs=[]
        #iterate through the list of retrieved videos
        for video in video_list:
            vidId = video[1]
            ydl = yt_dlp.YoutubeDL({'ignoreerrors':True})
            song_info = ydl.extract_info(vidId, download=False)
            #find trackname and artist in response
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
            
        #pass the unavailable songs through another filter method
        extra_filter, unavailable_songs = self.superSongParser(unavailable_songs)
        #append the songs found from the super filter
        available_songs += extra_filter
        #extra filtering for the title names
        #replaces ft. or feat. in artist names with a comma to improve search
        #removes special characters
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
        #attempts to find more valid songs in the unavailable list
        #does this by seraching for keywords such as 'Official Music Video', 'Audio', 'Lyrics Video' to parse the song name and artist from the title
        found_songs = []
        #used to keep track of songs when some removed from unavailable list
        vid_copy = video_list.copy()
        for item in video_list:
            #lowercase title to simplify search
            title = item[0].lower()
            sub_title = None
            #check for keyword 'official' in title
            if title.find('official') != -1:
                if title.find('official audio') !=-1:
                    sub_title = title.split('official audio')[0][:-2]
                elif title.find('official video')!=-1:
                    sub_title = title.split('official video')[0][:-2]
                elif title.find('official music video')!=-1:
                    sub_title = title.split('official music video')[0][:-2]
                elif title.find('official lyric video')!=-1:
                    sub_title = title.split('official lyric video')[0][:-2]

            #checking for MVs (music videos)
            if title.find('m/v')!= -1 or title.find('mv') != -1 and sub_title == None:
                if title.find('official m/v')!=-1:
                    sub_title = title.split('official m/v')[0][:-1]
                elif title.find('official mv')!=-1:
                    sub_title = title.split('official mv')[0][:-1]
                elif title.find(' m/v')!=-1:
                    sub_title = title.split(' m/v')[0]
            #checks for official audio videos
            if title.find('audio')!=-1 and sub_title==None:
                if title.find('(audio)')!=-1 or title.find('[audio]')!=-1:
                    sub_title = title.split('audio')[0][:-2]
            #checks for official lyrics videos
            if title.find('lyric')!=-1 and sub_title==None:
                if title.find('(lyrics)')!=-1 or title.find('[lyrics]')!=-1:
                    sub_title = title.split('lyrics')[0][:-2]
                elif title.find('(lyric video)')!=-1 or title.find('[lyric video]')!=-1:
                    sub_title = title.split('lyric video')[0][:-2]

            #checks through potential artist and song names which are usually separated with 'by' or '-'
            if sub_title != None:
                #if the separator exists in the filtered title, the artist name often comes before the song title
                #however this should not matter too much when searching these items in the destination platform
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
                #some song titles are encased in quotation marks
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
        #returns list of found songs and ones that remain unavailable
        return found_songs, vid_copy

    def filterVideoResponse(self, response):
        videos = []
        for item in response['items']:
            name = item['snippet']['title']
            vidId = item['contentDetails']['videoId']

            #filtering out private/deleted videos that may occur in the playlist
            #if item['status']['privacyStatus'] == 'private' or item['status']['privacyStatus'] !='unlisted':
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
        #set up a credentials object using the google API
        credentials = google.oauth2.credentials.Credentials(
            **creds
        )
        #revoke the credentials of the user by sending request to the api endpoint
        revoke = requests.post('https://oauth2.googleapis.com/revoke',
            params = {'token': credentials.token},
            headers = {'content-type': 'application/x-www-form-urlencoded'})
        
