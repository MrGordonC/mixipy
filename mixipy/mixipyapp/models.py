from django.db import models
from django.utils import timezone


class Platform(models.Model):
    name = models.CharField(max_length=50)
    url = models.URLField(max_length=500, blank=True)

    @classmethod
    def create(cls, name, url):
        platform = cls(name=name, url=url)
        return platform


class RequestLog(models.Model):
    platform = models.ForeignKey(Platform, on_delete=models.DO_NOTHING)
    url = models.URLField(max_length=500, blank=True)
    title = models.CharField(max_length=250, blank=True)
    pub_date = models.DateTimeField(blank=True)
    status = models.SmallIntegerField()

    @classmethod
    def create(cls, platform, title, url, pub_date, status):
        log = cls(platform=platform, title=title, url=url, pub_date=pub_date, status = status)
        return log


class Page(models.Model):
    url = models.URLField(max_length=500)
    title = models.CharField(max_length=250, blank=True)
    created_datetime = models.DateTimeField(default=timezone.now)
    modified_datetime = models.DateTimeField(blank=True, default=timezone.now)

    @classmethod
    def create(cls, url, title, created_datetime, modified_datetime):
        page = cls(url=url, title=title, created_datetime=created_datetime, modified_datetime=modified_datetime)
        return page


class Search(models.Model):
    keywords = models.CharField(max_length=200)
    page = models.ForeignKey(Page, on_delete=models.DO_NOTHING)

    @classmethod
    def create(cls, keywords, page):
        search = cls(keywords=keywords, page=page)
        return search


class Track(models.Model):
    uri = models.CharField(max_length=50)
    search = models.ForeignKey(Search, on_delete=models.DO_NOTHING)

    @classmethod
    def create(cls, uri, search):
        track = cls(uri=uri, search=search)
        return track


class PageRequest(models.Model):
    request = models.ForeignKey(RequestLog, on_delete=models.DO_NOTHING)
    page = models.ForeignKey(Page, on_delete=models.DO_NOTHING)

    @classmethod
    def create(cls, request, page):
        page_request = cls(request=request, page=page)
        return page_request


class Playlist(models.Model):
    request = models.ForeignKey(RequestLog, on_delete=models.DO_NOTHING)
    name = models.CharField(max_length=250)
    platform = models.ForeignKey(Platform, on_delete=models.DO_NOTHING)
    uri = models.CharField(max_length=50, blank=True)
    description = models.CharField(max_length=250, blank=True)

    @classmethod
    def create(cls, request, name, platform, uri=None, description=None):
        playlist = cls(uri, platform, request, name, description)
        return playlist
