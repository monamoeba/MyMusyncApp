from django.conf import settings
from django.conf.urls.static import static
from django.urls import path

#from .views import IndexPageView, ChooseSourceView, ytsource, ytsourcecallback
from .views import *
urlpatterns = [
    path('', IndexPageView.as_view(), name='index'),
    path('ChooseSource/', ChoosePlatView.as_view(), name='chooseSource'),
    path('ChooseDest/', ChoosePlatView.as_view(), name='chooseDest'),
    path('ytAuth/', ytAuth, name='YTAuth'),
    path('ytsourcecallback/', ytsourcecallback, name='YToauth2callback'),
    path('ytGetData/', ytGetData, name='ytGetData'),
    path('spdestcallback/', spdestcallback, name='SPoauth2callback'),
    path('spAuth/', spAuth, name='SPAuth'),
    path('ytChoosePlaylist/', ytChoosePlaylist, name='ytChoosePlaylist'),
    path('ytGetSongs/', ytGetSongs, name='ytGetSongs'),
    path('customisePlaylist/', customisePlaylist, name='custPlaylist'),
    path('spCreatePlaylist/', spCreatePlaylist, name='spCreatePlaylist'),
    path('spTransfer/', spTransfer, name='spTransfer'),
    path('spTransferFinish/', spTransferFinish, name='spTransferFinish'),
    path('spLoop/', spWebLoop, name='spWebLoop'),
    path('Finish', Finish, name='Finish'),
    path('changePlatforms', ChangePlatforms, name='changePlatforms')
]