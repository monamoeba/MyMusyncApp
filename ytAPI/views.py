from django.conf import settings
from django.shortcuts import render, redirect
from django.views.generic import TemplateView
from django.urls import reverse

from ytAPI.YTAPI import YTSource
from ytAPI.spAPI import SPDest
from spotipy import DjangoSessionCacheHandler


class IndexPageView(TemplateView):
    template_name = 'APIs/index.html'

class ChoosePlatView(TemplateView):
    template_name = 'APIs/choosePlat.html'

yt_source = YTSource()

def ytAuth(request):
    request.session['source'] = 'YouTube'
    redirect_uri = settings.SITE_BASE_URL + reverse('ytAPI:YToauth2callback')
    authorization_url, state = yt_source.authorise(redirect_uri)
    request.session['state'] = state
    return redirect(authorization_url)

def ytsourcecallback(request):
    if 'source' not in request.session or request.session['source'] != 'YouTube':
        return redirect('ytAPI:YTAuth')
    if 'error' in request.GET:
        return redirect('ytAPI:chooseSource')
    state = request.session['state']
    redirect_uri = settings.SITE_BASE_URL + reverse('ytAPI:YToauth2callback')
    auth_resp = request.build_absolute_uri()
    credentials = yt_source.validateOAuthResponse(state, redirect_uri, auth_resp)
    request.session['credentials'] = credentials
    return redirect('ytAPI:ytGetData')


def ytGetData(request):
    if 'credentials' not in request.session:
        return redirect('ytAPI:YTAuth')

    results = yt_source.getPlaylists(request.session['credentials'])

    request.session['playlists'] = results
    return redirect('ytAPI:ytChoosePlaylist')

def ytChoosePlaylist(request):
    if 'playlists' not in request.session or 'source' not in request.session:
        return redirect('ytAPI:index')
    if request.session['source'] == 'YouTube':
        playlist_list = request.session['playlists']
        return render(request, 'APIs/chooseplaylist.html', locals())
    else:
        return redirect('ytAPI:YTAuth')

def ytGetSongs(request):
    if 'playlists' not in request.session:
        return redirect('ytAPI:ytGetData')
    if request.method == 'POST':
        if 'play_id' not in request.POST:
            playlist_index = int(request.POST.get('playlist', ''))
            request.session['playlist_index'] = playlist_index
            play_id = request.session['playlists'][playlist_index]['id']
        else:
            play_id = request.POST.get('play_id')
            name = yt_source.getSingleplaylist(request.session['credentials'], play_id)
            if name == None:
                return redirect('ytAPI:ytChoosePlaylist')
            request.session['ytplay_name'] = name
        vids = yt_source.getSongs(request.session['credentials'], play_id)
        print(f'vids = {vids}')
        request.session['video_list'] = vids
        return redirect('ytAPI:chooseDest')


sp_dest = SPDest()

def spAuth(request):
    if 'credentials' not in request.session:
        return redirect('ytAPI:YTAuth')

    authorisation_url = sp_dest.spAuthorise()
    return redirect(authorisation_url)

def spdestcallback(request):
    if 'error' in request.GET:
        return redirect('ytAPI:chooseDest')
    else:
        code = request.GET.get('code', '')
        cache_handler = DjangoSessionCacheHandler(request)
        token = sp_dest.spValidateResponse(code)
        cache_handler.save_token_to_cache(token)
        request.session['spCredentials'] = token
        return redirect('ytAPI:custPlaylist')

def customisePlaylist(request):
    if 'spCredentials' not in request.session:
        return redirect('ytAPI:chooseDest')
    if 'ytplay_name' not in request.session:
        index = int(request.session['playlist_index'])
        default_playlist = request.session['playlists'][index]['name']
    else:
        default_playlist = request.session['ytplay_name']
    context = {
        'fill_name': default_playlist
    }
    return render(request, 'APIs/customiseplaylist.html', context)

def spCreatePlaylist(request):
    if 'spCredentials' not in request.session:
        return redirect('ytAPI:chooseDest')
    if request.method == 'POST':
        play_name = request.POST.get('play_name', 'MyMusync playlist')
        play_desc = request.POST.get('play_description', '')
        if 'play_setting' not in request.POST:
            play_setting = False
        else:
            play_setting = True
        token = request.session['spCredentials']
        new_playlist = sp_dest.spCreatePlaylist(token, play_name, play_desc, play_setting)
        request.session['playlist_id'] = new_playlist
        return redirect('ytAPI:spTransfer')

def spTransfer(request):
    if 'spCredentials' not in request.session or 'playlist_id' not in request.session:
        return redirect('ytAPI:chooseDest')

    song_list, unavailable_list = yt_source.createMusicList(request.session['video_list'])
    print(f'Song_list main views: {song_list}')
    song_uri, unavailable_list2 = sp_dest.transferSongs(request.session['spCredentials'], song_list, request.session['playlist_id'])
    unavailable_list += unavailable_list2
    request.session['unavailable_songs'] = unavailable_list
    return redirect('ytAPI:spTransferFinish')

def spTransferFinish(request):
    context = {
        'unavailable_list': request.session['unavailable_songs'],
    }
    return render(request, 'APIs/transferFinish.html', context)

def spWebLoop(request):
    return render(request, 'APIs/webLoop.html')

def Finish(request):
    if 'credentials' in request.session:
        yt_source.revokeToken(request.session['credentials'])
    #the Spotify token isn't explicitly revoked here - it expires on its own
    #after an hour
    request.session.flush()
    return redirect('ytAPI:index')

def ChangePlatforms(request):
    if 'credentials' in request.session:
        yt_source.revokeToken(request.session['credentials'])
    request.session.flush()
    return redirect('ytAPI:chooseSource')
