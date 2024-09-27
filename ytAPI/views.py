from django.shortcuts import render, redirect
from django.views.generic.edit import FormView
from django.views.generic import TemplateView
from django.http import HttpResponse
from django.urls import reverse
#import json
from ytAPI.YTAPI import YTSource
from ytAPI.spAPI import SPDest
from spotipy import DjangoSessionCacheHandler
from MusicTransferWebApp.settings import PROJECT_DIR

import imghdr
# Create your views here.

class IndexPageView(TemplateView):
    #return home page template
    template_name = 'APIs/index.html'

class ChoosePlatView(TemplateView):
    #return source html template
    template_name = 'APIs/choosePlat.html'

#create a YTSource object
yt_source = YTSource()
def ytAuth(request):
    request.session['source'] = 'YouTube'
#def ytsource(request):
    #initialise the 'flow' with appropriate scopes
    #flow = google_auth_oauthlib.flow.Flow.from_client_secrets_file(
            #'ytAPI/client_secret.json',
            #scopes=['https://www.googleapis.com/auth/youtube.force-ssl'])
    
    #set redirect url after the authorisation process
    #flow.redirect_uri='https://127.0.0.1:8000/ytsourcecallback/'
    #retrieve auth url
    authorization_url, state = yt_source.authorise('https://127.0.0.1:8000/ytsourcecallback/')
    request.session['state'] = state
    #set destination url to google authentication pages
    #res = redirect(authorization_url)
    #redirect the user to authentication pages
    return redirect(authorization_url)

def ytsourcecallback(request):
    if 'source' not in request.session or request.session['source'] != 'YouTube':
        return redirect('https://127.0.0.1:8000/ytAuth/')
    #this view is used to handle/verify the authorisation process
    if 'error' in request.GET:
        return redirect('https://127.0.0.1:8000/ChooseSource/')
    #store state of flow to verify later
    state = request.session['state']
    #return HttpResponse(state)
    #new flow to fetch OAuth tokens
    #flow.redirect_uri = 'https://127.0.0.1:8000/ytsourcecallback/'
    auth_resp = request.build_absolute_uri()
    #store the credentials in the session as a dictionary to make accessing 
    #will make refreshing tokens easier
    credentials = yt_source.validateOAuthResponse(state, 'https://127.0.0.1:8000/ytsourcecallback/', auth_resp)
    request.session['credentials'] = credentials
    return redirect('https://127.0.0.1:8000/ytGetData/')


def ytGetData(request):
    #this checks to see whether the user is authorised before
    #attempting to retrieve their playlists.
    #if they are not authorised, they will be redirected to the Google log-in page
    if 'credentials' not in request.session:
        return redirect('https://127.0.0.1:8000/ytAuth/')

    #code to execute the request to the API using class method
    results = yt_source.getPlaylists(request.session['credentials'])

    request.session['playlists'] = results
    return redirect('https://127.0.0.1:8000/ytChoosePlaylist/')

def ytChoosePlaylist(request):
    if 'playlists' not in request.session or 'source' not in request.session:
        return redirect('https://127.0.0.1:8000/')
    if request.session['source'] == 'YouTube':
        playlist_list = request.session['playlists']
        return render(request, 'APIs/chooseplaylist.html', locals())
    else:
        return redirect('https://127.0.0.1:8000/ytAuth/')

def ytGetSongs(request):
    if 'playlists' not in request.session:
        return redirect('https://127.0.0.1:8000/ytGetData/')
    if request.method == 'POST':
        if 'play_id' not in request.POST:
            playlist_index = int(request.POST.get('playlist', ''))
            request.session['playlist_index'] = playlist_index
            #request.session['playlist_index'] = playlist_index
            play_id = request.session['playlists'][playlist_index]['id']
        else:
            play_id = request.POST.get('play_id')
            name = yt_source.getSingleplaylist(request.session['credentials'], play_id)
            #if there is no playlist with the playlist_id return user back to choosing theplaylist
            if name == None:
                return redirect('https://127.0.0.1:8000/ytChoosePlaylist/')
            #store the name in sessions for later use
            request.session['ytplay_name'] = name
        #implement yt API to get playlist videos
        vids = yt_source.getSongs(request.session['credentials'], play_id)
        print(f'vids = {vids}')
        request.session['video_list'] = vids
        #redirect the user to choose a platform
        return redirect('https://127.0.0.1:8000/ChooseDest/')
        # return redirect('https://127.0.0.1:8000/customisePlaylist/')


sp_dest = SPDest()

def spAuth(request):
    if 'credentials' not in request.session:
            return redirect('https://127.0.0.1:8000/ytAuth/')
    
    authorisation_url = sp_dest.spAuthorise()
    return redirect(authorisation_url)
    #remember to register this in urls!!!!!

def spdestcallback(request):
    if 'error' in request.GET:
        #handle revoked response
        return redirect('https://127.0.0.1:8000/ChooseDest/')
    #parse the returned url to get the authorisation code
    else:
        code = request.GET.get('code', '')
        #creating an instance of the 
        cache_handler = DjangoSessionCacheHandler(request)
        #call the class method to validate the response
        token = sp_dest.spValidateResponse(code)
        #save the token/credentials into the session using the cache handler
        cache_handler.save_token_to_cache(token)
        request.session['spCredentials'] = token
        return redirect('https://127.0.0.1:8000/customisePlaylist/')

def customisePlaylist(request):
    if 'spCredentials' not in request.session:
        return redirect('https://127.0.0.1:8000/ChooseDest/')
    #retrieve the index of the chosen playlist
    if 'ytplay_name' not in request.session:
        index = int(request.session['playlist_index'])
        default_playlist = request.session['playlists'][index]['name']
    else:
        default_playlist = request.session['ytplay_name']
    #create a context to allow variables to be passed into the templates
    context ={
        'fill_name':default_playlist
    }
    #return the rendered template
    return render(request, 'APIs/customiseplaylist.html', context)

def spCreatePlaylist(request):
    if 'spCredentials' not in request.session:
        return redirect('https://127.0.0.1:8000/ChooseDest/')
    if request.method == 'POST':
        #retrieve the data from the form response
        play_name = request.POST.get('play_name','MyMusync playlist')
        play_desc = request.POST.get('play_description', '')
        if 'play_setting' not in request.POST:
            play_setting = False
        else:
            play_setting = True
        #retrieve the spotify tokens stored in the session
        token = request.session['spCredentials']
        #call the method to create a new playlist
        new_playlist = sp_dest.spCreatePlaylist(token, play_name, play_desc, play_setting)
        request.session['playlist_id'] = new_playlist
        return redirect('https://127.0.0.1:8000/spTransfer/')

def spTransfer(request):
    if 'spCredentials' not in request.session or 'playlist_id' not in request.session:
        return redirect('https://127.0.0.1:8000/ChooseDest/')
    
    song_list, unavailable_list = yt_source.createMusicList(request.session['video_list'])
    print(f'Song_list main views: {song_list}')
    song_uri, unavailable_list2 = sp_dest.transferSongs(request.session['spCredentials'],song_list,request.session['playlist_id'])
    unavailable_list += unavailable_list2
    request.session['unavailable_songs'] = unavailable_list
    return redirect('https://127.0.0.1:8000/spTransferFinish/')

def spTransferFinish(request):
    #retrieve the list of the videos and songs that could not be transferred
    context = {
        'unavailable_list' : request.session['unavailable_songs'],
    }
    #render the 
    return render(request, 'APIs/transferFinish.html', context)

def spWebLoop(request):
    return render(request,'APIs/webLoop.html')

def Finish(request):
    #clear all data
    #revoke yt token
    if 'credentials' in request.session:
        yt_source.revokeToken(request.session['credentials'])
    #spotify token will automatically be revoked in an hour
    #delete session
    request.session.flush()
    #redirect to main page
    return redirect('https://127.0.0.1:8000/')

def ChangePlatforms(request):
    #clear session data + cache + session data
    if 'credentials' in request.session:
        yt_source.revokeToken(request.session['credentials'])
    request.session.flush()
    #return user to the choose platform page
    return redirect('https://127.0.0.1:8000/ChooseSource/')

### maybe make separate pages for yt source and spot source
# because scopes will be different for each cases

#Add back in later if needed
    #def yt_auth(self):
        #flow = google_auth_oauthlib.flow.Flow.from_client_secrets_file(
        #    f'{PROJECT_DIR}\ytAPI\client_secret.json',
        #    scopes=['https://www.googleapis.com/auth/youtube.force-ssl']
        #)
        #flow.redirect_uri='http://127.0.0.1:8000/'
        #authorization_url, state = flow.authorization_url(
        #    access_type='offline',
        #    include_granted_scopes='true'
        #)
        #pass