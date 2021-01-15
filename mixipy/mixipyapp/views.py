from django.shortcuts import get_object_or_404, render
from django.http import HttpResponse, Http404
from django.utils import timezone

from django.views.decorators.csrf import csrf_exempt
import json
from rest_framework import viewsets, status, mixins, generics
from rest_framework import permissions

from rest_framework.decorators import api_view, permission_classes
from rest_framework.response import Response
from rest_framework.views import APIView

from .mixipy import Mixipy
from .serializers import *


def index(request):
    request_list = RequestLog.objects.order_by('-pub_date')[:22]
    latest_request_list = request_list
    latest_playlists = []
    for request_model in request_list:
        playlist = Playlist.objects.filter(request=request_model)
        spotify_uri = ''
        if playlist:
            spotify_uri = playlist.first().uri
        latest_playlists.append(spotify_uri)

    # output = ', '.join([q.url for q in latest_request_list])
    # template = loader.get_template('mixipy/index.html')
    # return HttpResponse("Hello, world. You're at the mixipy index.")
    context = {
        'latest_request_list': latest_request_list,
    }
    # return HttpResponse(template.render(context, request))
    return render(request, 'mixipy/index.html', context)


class PlatformList(generics.ListCreateAPIView):
    queryset = Platform.objects.all().order_by('name')
    serializer_class = PlatformSerializer
    permission_classes = [permissions.IsAuthenticated]


class PlatformDetail(generics.RetrieveUpdateDestroyAPIView):
    queryset = Platform.objects.all().order_by('name')
    serializer_class = PlatformSerializer
    permission_classes = [permissions.IsAuthenticated]


class RequestLogList(generics.ListCreateAPIView):
    queryset = RequestLog.objects.all().order_by('id')
    serializer_class = PageSerializer
    permission_classes = [permissions.IsAuthenticated]


class RequestLogDetail(generics.RetrieveUpdateDestroyAPIView):
    queryset = RequestLog.objects.all().order_by('id')
    serializer_class = PageSerializer
    permission_classes = [permissions.IsAuthenticated]


class PageList(generics.ListCreateAPIView):
    queryset = Page.objects.all().order_by('id')
    serializer_class = PageSerializer
    permission_classes = [permissions.IsAuthenticated]


class PageDetail(generics.RetrieveUpdateDestroyAPIView):
    queryset = Page.objects.all()
    serializer_class = PageSerializer
    permission_classes = [permissions.IsAuthenticated]


class PageRequestList(generics.ListCreateAPIView):
    queryset = PageRequest.objects.all().order_by('id')
    serializer_class = PageRequestSerializer
    permission_classes = [permissions.IsAuthenticated]


class PageRequestDetail(generics.RetrieveUpdateDestroyAPIView):
    queryset = PageRequest.objects.all().order_by('id')
    serializer_class = PageRequestSerializer
    permission_classes = [permissions.IsAuthenticated]


class PlaylistList(generics.ListCreateAPIView):
    queryset = Playlist.objects.all().order_by('id')
    serializer_class = PlaylistSerializer
    permission_classes = [permissions.IsAuthenticated]


class PlaylistDetail(generics.RetrieveUpdateDestroyAPIView):
    queryset = Playlist.objects.all()
    serializer_class = PlaylistSerializer
    permission_classes = [permissions.IsAuthenticated]


class SearchList(generics.ListCreateAPIView):
    queryset = Search.objects.all()
    serializer_class = SearchSerializer


class SearchDetail(generics.RetrieveUpdateDestroyAPIView):
    queryset = Search.objects.all()
    serializer_class = SearchSerializer


class TrackList(generics.ListCreateAPIView):
    queryset = Track.objects.all().order_by('id')
    serializer_class = TrackSerializer


class TrackDetail(generics.RetrieveUpdateDestroyAPIView):
    queryset = Track.objects.all().order_by('id')
    serializer_class = TrackSerializer


class Create(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        print("CREATE: " + request.method)
        if request.method == 'POST':
            create_playlist_request = Create.post_helper(request)
            playlist = Create.get_object(create_playlist_request.id)
            serializer = PlaylistSerializer(playlist)
            return Response(serializer.data)
        else:
            return Response({"success": False})

    @staticmethod
    def post_helper(request):
        platform = Create.parse_platform(request)
        url = Create.parse_keywords(request)
        request_log = Mixipy.create_helper_search(url, platform)
        print(request_log.title)
        playlist_model = Mixipy.create_helper_playlist(request=request_log)
        return playlist_model

    @staticmethod
    def get_object(pk):
        try:
            return Playlist.objects.get(pk=pk)
        except Playlist.DoesNotExist:
            raise Http404

    @staticmethod
    def parse_platform(request):
        platform = request.data.get('platform', None)
        platform_model = Platform.objects.get(name=platform)
        return platform_model

    @staticmethod
    def parse_keywords(request):
        url = request.data.get('url', None)
        key_words = request.data.get('key', None)
        if key_words:
            url = 'https://www.mixesdb.com/w/Category:' + str(key_words).replace(' ', '_')
        return url

# def log(request, log_id):
#     try:
#         request_log = RequestLog.objects.get(pk=log_id)
#     except RequestLog.DoesNotExist:
#         raise Http404("request does not exist")
#     return render(request, 'mixipy/request_log.html', {'request_log': request_log})
