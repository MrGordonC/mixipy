from django.urls import path, include
from rest_framework import routers
from rest_framework.urlpatterns import format_suffix_patterns

from . import views
from .views import *

app_name = 'mixipy'

# router = routers.DefaultRouter()
# router.register(r'page', PageViewSet)
# router.register(r'platform', PlatformViewSet)
# router.register(r'playlist', PlaylistViewSet)
# router.register(r'requestlog', RequestLogViewSet)
# router.register(r'search', SearchViewSet)
# router.register(r'track', SpotifyTrackViewSet)

urlpatterns = [
    path('', views.index, name='index'),
    path('api-auth/', include('rest_framework.urls', namespace='rest_framework')),
    # path('', include(router.urls)),
    #path('create/<str:url>/', views.create, name='create'),
    # path('playlists/<int:playlist_id>/', views.playlist, name='playlist'),
    # path('platform/<int:platform_id>/', views.platform, name='platform'),
    # path('log/<int:log_id>/', views.log, name='log'),
    # path('page/<int:page_id>/', views.page, name='page'),
]

urltoformat = [
    path('page/', views.PageList.as_view()),
    path('page/<int:pk>', views.PageDetail.as_view()),
    path('pagerequest/', views.PageRequestList.as_view()),
    path('pagerequest/<int:pk>', views.PageRequestDetail.as_view()),
    path('platform/', views.PlatformList.as_view()),
    path('platform/<int:pk>', views.PlatformDetail.as_view()),
    path('playlist/', views.PlaylistList.as_view()),
    path('playlist/<int:pk>', views.PlaylistDetail.as_view()),
    path('request/', views.RequestLogList.as_view()),
    path('request/<int:pk>', views.RequestLogDetail.as_view()),
    path('search/', views.SearchList.as_view()),
    path('search/<int:pk>', views.SearchDetail.as_view()),
    path('track/', views.TrackList.as_view()),
    path('track/<int:pk>', views.TrackDetail.as_view()),
    path('create/', views.Create.as_view()),
    path('scrape/', views.Scrape.as_view())
]

formatted_suffix_patterns = format_suffix_patterns(urltoformat)

urlpatterns = urlpatterns + formatted_suffix_patterns
