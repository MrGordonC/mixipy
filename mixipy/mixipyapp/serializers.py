from rest_framework import serializers
from .models import *


class PlatformSerializer(serializers.HyperlinkedModelSerializer):
    class Meta:
        model = Platform
        fields = ['id', 'name', 'url']


class RequestLogSerializer(serializers.HyperlinkedModelSerializer):
    platform = PlatformSerializer(many=False, read_only=True)

    class Meta:
        model = RequestLog
        fields = ['id', 'title', 'url', 'platform']


class PageSerializer(serializers.HyperlinkedModelSerializer):
    request_log = RequestLogSerializer(many=False, read_only=True)

    class Meta:
        model = Page
        fields = ['id', 'title', 'url', 'request_log']


class PageRequestSerializer(serializers.HyperlinkedModelSerializer):
    page = PageSerializer(many=False, read_only=True)
    request = RequestLogSerializer(many=False, read_only=True)

    class Meta:
        model = PageRequest
        fields = ['id', 'request', 'page']


class SearchSerializer(serializers.HyperlinkedModelSerializer):
    page = PageSerializer(many=False, read_only=True)

    class Meta:
        model = Search
        fields = ['id', 'keywords', 'page']


class TrackSerializer(serializers.HyperlinkedModelSerializer):
    search = SearchSerializer(many=False, read_only=True)

    class Meta:
        model = Track
        fields = ['id', 'uri', 'search']


class PlaylistSerializer(serializers.HyperlinkedModelSerializer):
    platform = PlatformSerializer(many=False, read_only=True)
    request = RequestLogSerializer(many=False, read_only=True)

    class Meta:
        model = Playlist
        fields = ['id', 'name', 'description', 'uri', 'platform', 'request']
