import re
import requests
from bs4 import BeautifulSoup
from celery import current_app
from celery.contrib import rdb
from decouple import config
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
    STATUS_NEW = 1
    STATUS_PENDING = 2
    STATUS_COM = 5
    STATUS_ERROR = 6
    STATUS_CAN = 98
    STATUS_DELETED = 99
    PROCESSING = [STATUS_NEW, STATUS_PENDING]
    SCRAPED = [STATUS_PENDING, STATUS_COM]
    TERMINATED = [STATUS_COM, STATUS_ERROR]

    platform = models.ForeignKey(Platform, on_delete=models.DO_NOTHING)
    url = models.URLField(max_length=500, blank=True)
    title = models.CharField(max_length=250, blank=True)
    pub_date = models.DateTimeField(blank=True)
    status = models.SmallIntegerField()

    @classmethod
    def create(cls, platform, title, url, pub_date, status):
        log = cls(platform=platform, title=title, url=url, pub_date=pub_date, status=status)
        return log

    def is_status(self, *status):
        is_status = any(current_status == self.status for current_status in status)
        return is_status

    def scrape_complete(self):
        page_requests = PageRequest.objects.filter(request=self)
        if page_requests:
            pages = [page_request.page for page_request in page_requests]
            scrape_complete = all(page.is_status(Page.COMPLETED) for page in pages)
            return scrape_complete
        return False

    def update_status(self):
        import time
        if self.is_status(RequestLog.STATUS_NEW):
            print("Checking pages - status: " + str(self.status))
            pages_scraped = False
            while not pages_scraped:
                pages_scraped = self.scrape_complete()
                if not pages_scraped:
                    print('Idle: ' + str(self.status))
                    time.sleep(60)
            print('PEND: ' + self.url)
            self.status = RequestLog.STATUS_PENDING
            self.save()
        elif self.is_status(RequestLog.STATUS_PENDING):
            print('placeholder')

    @staticmethod
    def create_helper_search(request_url, platform, force):
        platform_model = platform
        request_log_model, created = RequestLog.objects.get_or_create(url=request_url,
                                                                      platform=platform_model,
                                                                      defaults={'title': request_url,
                                                                                'pub_date': timezone.now(),
                                                                                'status': RequestLog.STATUS_NEW
                                                                                }
                                                                      )
        playlist_model, created = Playlist.objects.get_or_create(platform=platform,
                                                                 request=request_log_model,
                                                                 )
        if not request_log_model.title == playlist_model.name:
            playlist_model.name = request_log_model.title
            playlist_model.save(update_fields=['name'])
        from .tasks import PROCESS_REQUEST
        current_app.send_task(
            PROCESS_REQUEST,
            args=[request_log_model.pk, force]
        )
        return playlist_model

    def create_search_for_request(self, force):
        request_log_model = self
        request_url = str(request_log_model.url)
        platform = request_log_model.platform
        if force:
            request_log_model.status = RequestLog.STATUS_PENDING
        # if request_log_model.is_status(*RequestLog.PROCESSING):
        if request_log_model.is_status(RequestLog.STATUS_NEW):
            # if created or request_log_model.is_status(RequestLog.PROCESSING):
            print('NEW')
            _response = requests.get(request_url, headers=Page.HEADER_DEFAULT)
            request_html = BeautifulSoup(_response.content, 'html.parser')
            # title = request_html.find('title').get_text()
            title = PageMetaInfo.title_from_html(request_html)
            request_log_model.title = title
            request_log_model.save(update_fields=['title'])
            playlist = Playlist.objects.get(request=request_log_model)
            playlist.name = title
            playlist.save(update_fields=['name'])
            page_meta_list = list()
            if request_url.__contains__('Category') or request_url.__contains__('brand'):
                print('Factory Pages URL setting: ' + platform.name)
                page_meta_list = PageMetaInfo.parse_from_html(platform.name, request_html)
            else:
                print(platform.name + ' page: ' + request_url)
                page_title = PageMetaInfo.title_from_html(request_html)
                page_meta_list.append(PageMetaInfo.factory(title=page_title, url=request_url))
            # page_list = [PageRequest.factory(page_meta, request_log_model) for page_meta in page_meta_list]
            page_list = [Page.repository(page_meta) for page_meta in page_meta_list]
            for page in page_list:
                PageRequest.factory(page_model=page, request_log=request_log_model)

            print(page.url for page in page_list)
            # Page.objects.bulk_create(page_list)
            search_list = list()
            print("PAGES: " + str(len(page_list)))
            from .tasks import REQUEST_STATUS_UPDATE
            current_app.send_task(
                REQUEST_STATUS_UPDATE,
                args=[self.pk]
            )
            for page_model in page_list:
                page_track_list = Search.objects.filter(page=page_model.id)
                if page_track_list:
                    search_list = search_list + list(page_track_list)
                else:
                    mode = request_log_model.platform.name  # rewrite async
                    # name, track_list = Search.factory(mode, page_model)
                    from .tasks import SCRAPE_PAGE_URL
                    current_app.send_task(
                        SCRAPE_PAGE_URL,
                        args=[mode, page_model.url]
                    )
                    # search_list = search_list + track_list
            # request_log_model.status = RequestLog.STATUS_PENDING
            # request_log_model.save()
            # print('PEND: ' + request_url)

        #return request_log_model


class Page(models.Model):
    NEW = 1
    PENDING = 2
    SCRAPED = 5
    EMPTY = 6
    RESCRAPE = 7
    CANCELLED = 98
    DELETED = 99
    COMPLETED = [SCRAPED, EMPTY]

    HEADER_DEFAULT = {'User-Agent': 'Mozilla/5.0 (X11; Linux x86_64) '}
    # 'AppleWebKit/537.36 (KHTML, like Gecko) ' \
    #  'Chrome/75.0.3770.80 Safari/537.36'}
    HEADER_MIXESDB = HEADER_DEFAULT

    url = models.URLField(max_length=500)
    title = models.CharField(max_length=250, blank=True)
    created_datetime = models.DateTimeField(default=timezone.now)
    modified_datetime = models.DateTimeField(blank=True, default=timezone.now)
    status = models.SmallIntegerField()

    @classmethod
    def create(cls, url, title, created_datetime, modified_datetime):
        page = cls(url=url, title=title, created_datetime=created_datetime, modified_datetime=modified_datetime)
        return page

    @classmethod
    def repository(cls, page_meta):
        page, created = Page.objects.get_or_create(
            url=page_meta.url,
            title=page_meta.title,
            status=Page.NEW
        )
        return page

    def is_status(self, *status):
        # return self.status == status
        is_status = any(current_status == self.status for current_status in status)
        return is_status

    def bbc_extract_tracklist(self):
        url = self.url
        print("PAGE TITLE: " + str(self.title))
        bbc_sounds_page_html = requests.get(str(url))
        bbc_sounds_soup = BeautifulSoup(bbc_sounds_page_html.content, 'html.parser')
        tracklist_tag = 'sc-u-flex-grow sc-c-basic-tile__text'
        bbc_tracklist = bbc_sounds_soup.find_all('div', class_=tracklist_tag)
        name = lambda track: track.get('title')
        tracklist = [name(track) for track in bbc_tracklist]
        if len(tracklist) == 0:
            print("NO TRACKS FOUND: " + self.url)
            self.status = Page.EMPTY
        else:
            search_list = [Search.create(track, page=self) for track in tracklist]
            Search.objects.bulk_create(search_list)
            self.status = Page.SCRAPED
        # from .tasks import SEARCH_LIST_CREATE
        # current_app.send_task(
        #     SEARCH_LIST_CREATE,
        #     args=[self.pk, tracklist]
        # )
        from .tasks import SEARCH_FOR_TRACK
        current_app.send_task(
            SEARCH_FOR_TRACK,
            args=[self.pk]
        )
        self.save()
        return self.title, []

    def mixesdb_extract_tracklist(self):
        # TODO retrieve any cached tracks once page status field added to model:
        # TODO remove logic that uses the page model directly
        mixesdb_html_page = requests.get(self.url, headers=Page.HEADER_MIXESDB)
        mixesdb_soup = BeautifulSoup(mixesdb_html_page.content, 'html.parser')
        # Mixipy.update_page_title(page_model, mixesdb_soup)
        print("PAGE TITLE: " + str(self.title))
        tracklist_h2_tag = mixesdb_soup.find('h2', id='Tracklist')
        current_page_element = tracklist_h2_tag
        search_raw_list = []
        while current_page_element:
            ol_section_tag = current_page_element.find_next('ol')
            if ol_section_tag:
                li_track_tags = ol_section_tag.find_all('li')
                if li_track_tags:
                    search_raw_list = search_raw_list + li_track_tags
            current_page_element = ol_section_tag
        if len(search_raw_list) == 0:
            print("PAGE " + self.url + " using fallback method")
            current_div_list_tag = mixesdb_soup.find('div', class_='list')
            while current_div_list_tag:
                class_list = ['list-track', 'aff-api-done', 'list-track aff-done aff-api-done',
                              'list-track aff-api-undone-search aff-done aff-api-done']
                div_list_track_tag = current_div_list_tag.find_next('div', {'class': class_list})
                if div_list_track_tag:
                    if div_list_track_tag.find_previous('h2', id='comments'):
                        current_div_list_tag = False
                    else:
                        search_raw_list.append(div_list_track_tag)
                        current_div_list_tag = div_list_track_tag
                else:
                    current_div_list_tag = False
        else:
            print("PAGE " + self.url + " using primary method")
        if len(search_raw_list) == 0:
            print("NO TRACKS FOUND: " + self.url)
            self.status = Page.EMPTY
        else:
            # TODO convert to listcomp
            format = lambda s: re.sub(r'\[[^\]]*\]', '', s.get_text()).strip().lower()
            valid = lambda s: Page.valid_mixesdb_search(s)
            formatted_search_results = [format(search_html_tag) for search_html_tag in search_raw_list]
            tracklist = [search for search in formatted_search_results if valid(search)]
            if len(tracklist) > 0:
                self.status = Page.PENDING
                from .tasks import SEARCH_LIST_CREATE
                # current_app.send_task(
                #     SEARCH_LIST_CREATE,
                #     args=[self.pk, tracklist]
                # )
                search_list = [Search.create(keywords=track, page=self) for track in tracklist]
                Search.objects.bulk_create(search_list)
                self.status = Page.SCRAPED
            else:
                self.status = Page.EMPTY
        self.save(update_fields=['status'])
        from .tasks import SEARCH_FOR_TRACK
        current_app.send_task(
            SEARCH_FOR_TRACK,
            args=[self.pk]
        )
        return self.title, []

    @staticmethod
    def valid_mixesdb_search(search_str):
        filt = ['?', 'intro', 'unknown']
        if filt.__contains__(search_str):
            return False
        else:
            if search_str.__contains__('-'):
                return True
            else:
                return False


class Search(models.Model):
    keywords = models.CharField(max_length=200)
    page = models.ForeignKey(Page, on_delete=models.DO_NOTHING)

    @classmethod
    def create(cls, keywords, page):
        search = cls(keywords=keywords, page=page)
        return search

    @staticmethod
    def extract_tracklist(mode, page):
        print([mode, page.url])
        name, search_list = '', []
        if mode == 'BBC':
            name, search_list = page.bbc_extract_tracklist()
        elif mode == 'MIXESDB':
            name, search_list = page.mixesdb_extract_tracklist()
        return name, search_list

    @staticmethod
    def create_search_for_page(page, mode):
        page_track_list = Search.objects.filter(page=page.id)
        if page_track_list:
            print("EXISTING TRACKS")
            return list(page_track_list)
        else:
            name, track_list = Search.extract_tracklist(mode, page)
            page.save(update_fields=['status'])
            print("NEW TRACKS")
            return track_list

    def has_been_searched(self):
        pk = self.pk
        page_track_list = Search.objects.filter(keywords=self.keywords).exclude(pk=pk)
        if page_track_list:
            print("ATTEMPTING KEYWORD MATCH")
            for search in list(page_track_list):
                exist_tracks = Track.objects.filter(search=search)
                if exist_tracks:
                    return exist_tracks.first()
        return False


class Track(models.Model):
    uri = models.CharField(max_length=50)
    search = models.ForeignKey(Search, on_delete=models.DO_NOTHING)

    @classmethod
    def create(cls, uri, search):
        track = cls(uri=uri, search=search)
        return track

    @classmethod
    def factory(cls, uri, search_model):
        return Track.create(uri=uri, search=search_model)

    @staticmethod
    def get_bulk(search_list):
        track_list = []
        for search_item in search_list:
            existing_track = Track.objects.filter(search=search_item)
            if existing_track:
                track_list.append(existing_track.first())
        print('TRACKS FOUND: ' + str(len(track_list)) + '/' + str(len(search_list)))  # TODO MOVE
        return track_list


class PageRequest(models.Model):
    request = models.ForeignKey(RequestLog, on_delete=models.DO_NOTHING)
    page = models.ForeignKey(Page, on_delete=models.DO_NOTHING)

    @classmethod
    def create(cls, request, page):
        page_request = cls(request=request, page=page)
        return page_request

    @classmethod
    def factory(cls, page_model, request_log):
        page_request = PageRequest.objects.get_or_create(page=page_model,
                                                         request=request_log)
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

    @staticmethod
    def facade(request, playlist, force):
        # rdb.set_trace()
        request.create_search_for_request(force)
        print(request.url + " STATUS " + str(request.status))
        playlist.add_available_tracks(force=force)
        return playlist

    def add_available_tracks(self, force):
        playlist = self
        request = self.request
        if force and request.is_status(RequestLog.STATUS_COM):
            request.status = RequestLog.STATUS_PENDING
        if request.is_status(RequestLog.STATUS_COM):
            print("RETURNED COMPLETED EXISTING")
            return playlist
        elif request.is_status(RequestLog.STATUS_PENDING):
            print("REQUEST IS PENDING: " + str(request.status))
            # TODO ONLY 100 tracks can be added at a time - batch api calls so that we search and add in chunks of 100
            linked_pages = PageRequest.objects.filter(request_id=playlist.request)
            page_id_list = [page_request.page_id for page_request in linked_pages]
            page_models = [Page.objects.get(pk=page_id) for page_id in page_id_list]
            page_search = set([Search.objects.filter(page=page) for page in page_models if
                               page.is_status(Page.SCRAPED)])
            track_list = list(set().union(*page_search))
            track_batch = []
            initial_trackList = track_list[0:100]
            remaining_tracks = []
            if len(initial_trackList) >= 100:
                remaining_tracks = track_list[100:]
                print("MORE THAN 100 tracks!")
            else:
                print("TRACKS: " + str(len(initial_trackList)))
            tracklist = Track.get_bulk(initial_trackList)
            playlist_pool = SpotipyPlaylistPool.getInstance()
            # playlist_endpoint = Spotipy.playlist_modify()
            playlist_endpoint = playlist_pool.getResource()
            playlist_uri = playlist.uri
            if not playlist_uri:
                # TODO add a link the playlist as viewed in Mixipy to the Spotify playlist
                request.refresh_from_db()
                title = request.title
                play_list_obj = playlist_endpoint.create_spotify_playlist(title)
                playlist_uri = play_list_obj['uri']
                playlist.uri = playlist_uri
                playlist.save()
            if len(tracklist) > 0:
                ready_batch = [track.uri for track in tracklist]
                print('READY: ' + str(len(ready_batch)) + ' TRACK BATCH: ' + str(len(track_batch)))
                ready_batch = set(ready_batch)
                # TODO we can only have a few of these at a time, maybe need to move to singleton task
                playlist_endpoint.post_tracks_to_playlist(playlist_uri, ready_batch)
            playlist_pool.returnResource(playlist_endpoint)
            if len(remaining_tracks) > 0:
                async_tracklist = [search.pk for search in remaining_tracks]
                from .tasks import TRACKS_TO_PLAYLIST
                current_app.send_task(
                    TRACKS_TO_PLAYLIST,
                    args=(playlist_uri, async_tracklist)
                )
            request.status = RequestLog.STATUS_COM
            request.save()
            print("COM - Playlist: " + str(playlist.id))
            return playlist
        else:
            print('ERR - Request Status: ' + str(request.status))

    def tracks_to_playlist(self, search_list):
        track_list = [Search.objects.get(pk=search_pk) for search_pk in search_list]
        search_chunks = [track_list[x: x + 100]
                         for x
                         in range(0, len(track_list), 100)]
        search_chunks_iter = iter(search_chunks)
        complete = False
        pool = SpotipyPlaylistPool.getInstance()
        spotipy_playlist = pool.getResource()
        print(spotipy_playlist.scope)
        # spotipy_playlist = Spotipy.playlist_modify()
        track_batch = []
        uri_cache = set()
        while not complete:
            next_batch = track_batch
            search_chunk = None
            if len(next_batch) < 100:
                search_chunk = next(search_chunks_iter, None)
                if search_chunk:
                    # TODO we can do the search elsewhere
                    spotify_track_uri_list = Track.get_bulk(search_chunk)
                    next_batch = next_batch + spotify_track_uri_list
            if len(next_batch) >= 100:
                track_batch = next_batch[100:]
                next_batch = next_batch[0:100]
            elif len(next_batch) < 100:
                if search_chunk:
                    track_batch = next_batch
                    next_batch = None
                else:
                    complete = True
            if next_batch:
                batch = [track.uri for track in next_batch]
                ready_batch = set(batch).difference(uri_cache)
                # print(ready_batch)
                print('READY: ' + str(len(ready_batch)) + ' TRACK BATCH: ' + str(len(track_batch)))
                spotipy_playlist.post_tracks_to_playlist(self.uri, ready_batch)
                uri_cache = uri_cache.union(ready_batch)
        pool.returnResource(spotipy_playlist)


class PageMetaInfo:

    def __init__(self, title, url):
        self.title = title
        self.url = url

    def __str__(self):
        return self.title + ', ' + self.url

    @classmethod
    def factory(cls, title, url):
        return cls(title, url)

    @staticmethod
    def title_from_html(html):
        return html.find('title').get_text()

    @staticmethod
    def html_from_url(url):
        return BeautifulSoup(requests.get(url, headers=Page.HEADER_DEFAULT).content, 'html.parser')

    def html(self):
        return BeautifulSoup(requests.get(self.url, headers=Page.HEADER_DEFAULT).content, 'html.parser')

    @staticmethod
    def parse_from_html(mode, html):
        if mode == 'BBC':
            return PageMetaInfo.bbc_brand_extract_page_urls(html)
        elif mode == 'MIXESDB':
            return PageMetaInfo.category_extract_page_urls(html)
        else:
            return []

    @staticmethod
    def bbc_brand_extract_page_urls(bbc_sounds_html):
        print("brand_extract_page_urls")
        bbc_brand = bbc_sounds_html.find_all('article')
        bbc_url = 'https://www.bbc.co.uk'
        title_tag = "sc-c-metadata__secondary gel-long-primer gs-u-mt-"
        url_tag = "sc-c-playable-list-card__link sc-o-link sc-u-flex-grow"
        # desc_tag = "sc-c-metadata__synopsis gel-brevier gs-u-mt- gs-u-mb"
        page_title = lambda e: e.find('p', class_=title_tag).get_text()
        url = lambda e: bbc_url + e.find('a', class_=url_tag).get('href')
        factory = lambda f: PageMetaInfo.factory(page_title(f), url(f))
        page_urls = [factory(mix_link) for mix_link in bbc_brand]
        return page_urls

    @staticmethod
    def category_extract_page_urls(mixesdb_html):
        page_urls = []
        page_html = mixesdb_html
        mixesdb_url = 'https://www.mixesdb.com'
        while page_html:
            urls = PageMetaInfo.mixesdb_extract_page_url_helper(page_html)
            page_urls = page_urls + urls
            # Find next page to parse
            pagination_links = page_html.find('div', class_='listPagination')
            if pagination_links:
                next200_pagination_element = pagination_links.find('a', string='next 200')
                if next200_pagination_element:
                    next200_hyperlink = next200_pagination_element.get('href')
                    next200_url = mixesdb_url + next200_hyperlink
                    next200_request = requests.get(next200_url, headers=Page.HEADER_MIXESDB)
                    print(next200_url)
                    page_html = BeautifulSoup(next200_request.content, 'html.parser')
                else:
                    page_html = ''
            else:
                page_html = ''
        return page_urls

    @staticmethod
    def mixesdb_extract_page_url_helper(mixesdb_html):
        ul_cat_mixes_list_tag = mixesdb_html.find('ul', id='catMixesList')
        page_meta_list = []
        if ul_cat_mixes_list_tag:
            li_cat_mixes_list = ul_cat_mixes_list_tag.find_all('li')
            if li_cat_mixes_list:
                mixlink_list = [mix_link.find('a') for mix_link in li_cat_mixes_list]
                mix_url = 'https://www.mixesdb.com'
                factory = lambda m: PageMetaInfo.factory(title=m.get_text(), url=mix_url + m.get('href'))
                page_meta_list = [factory(mix) for mix in mixlink_list]
        else:
            print("NONE FOUND")
        return page_meta_list


class Spotipy:
    client_id = config('SPOTIFY_CLIENT_ID')
    client_secret = config('SPOTIFY_CLIENT_SECRET')
    redirect_uri = config('REDIRECT_URI')
    search_port = config('REDIRECT_URI_SEARCH')
    playlist_port = config('REDIRECT_URI_PLAYLIST')

    def __init__(self, scope, instance):
        self.scope = scope
        self.instance = instance

    @staticmethod
    def factory(scope):
        if scope == "user-library-read":
            return Spotipy.search_instance()
        elif scope == "playlist-modify-public":
            return Spotipy.playlist_modify()
        elif scope == "playlist-modify-no-cred":
            return Spotipy.playlist_modify_test()
        else:
            print('ERR: OPTION NEEDED')

    @staticmethod
    def create_instance(scope):
        from spotipy import Spotify, SpotifyOAuth
        from spotipy.oauth2 import SpotifyClientCredentials
        if scope == "user-library-read":
            client_credentials_manager = SpotifyClientCredentials(client_id=Spotipy.client_id,
                                                                  client_secret=Spotipy.client_secret)
            return Spotify(client_credentials_manager=client_credentials_manager)
        elif scope == "playlist-modify-public":
            return Spotify(auth_manager=SpotifyOAuth(client_id=Spotipy.client_id,
                                                     client_secret=Spotipy.client_secret,
                                                     redirect_uri=Spotipy.redirect_uri,
                                                     scope="playlist-modify-public"))
        elif scope == 'playlist-modify-second':
            return Spotify(auth_manager=SpotifyOAuth(client_id=Spotipy.client_id,
                                                     client_secret=Spotipy.client_secret,
                                                     redirect_uri=Spotipy.playlist_port,
                                                     scope="playlist-modify-public"))
        elif scope == "playlist-modify-no-cred":
            client_credentials_manager = SpotifyClientCredentials(client_id=Spotipy.client_id,
                                                                  client_secret=Spotipy.client_secret,
                                                                  )
            return Spotify(client_credentials_manager=client_credentials_manager)

    def reset(self):
        self.instance = Spotipy.create_instance(scope=self.scope)

    @classmethod
    def search_instance(cls):
        return cls("user-library-read", Spotipy.create_instance("user-library-read"))

    @classmethod
    def playlist_modify(cls):
        return cls("playlist-modify-public", Spotipy.create_instance("playlist-modify-public"))

    @classmethod
    def playlist_second(cls):
        return cls("playlist-modify-second", Spotipy.create_instance("playlist-modify-second"))

    @classmethod
    def playlist_modify_test(cls):
        return cls("playlist-modify-no-cred", Spotipy.create_instance("playlist-modify-no-cred"))

    # TODO investigate: creating the playlist is a user action, but maybe we can use cred-manage for adding?
    def create_spotify_playlist(self, title):
        user_id = self.instance.me()['id']
        instance = self.instance
        playlist_obj = instance.user_playlist_create(user_id, title)
        return playlist_obj

    def post_tracks_to_playlist(self, playlist_uri, tracks):
        self.instance.playlist_add_items(playlist_id=playlist_uri, items=tracks, position=None)

    # @staticmethod
    # def search_spotify_track(search, sp, limit=10):
    #     if search:
    #         kw = search.keywords.lower()
    #         results = sp.search(q=kw, limit=limit)
    #         # for idx, track in enumerate(results['tracks']['items']):
    #         #     if str(search.keywords.lower()).__contains__(track['artists'][0].get('name').lower()):
    #         #         uri = track['uri']
    #         #         return SpotifyTrack.factory(spotify_track=track, uri=uri)
    #         search_result = [track for idx, track in enumerate(results['tracks']['items'])]
    #         validate = lambda s: kw.__contains__(s['artists'][0].get('name').lower())
    #         factory = lambda t: SpotifyTrack.factory(spotify_track=t, uri=t['uri'])
    #         filtered_search = [factory(track) for track in search_result if validate(track)]
    #         return filtered_search
    #         # else:
    #         # TODO log near-matches
    #         #    print([search, track['artists'][0].get('name')])

    def create_tracks_for_page(self, search_list):
        db_track_list = []
        for search_item in search_list:
            spotify_track_matches = self.search_track(search_item, 1)
            spotify_track = next((track for track in spotify_track_matches), None)
            if spotify_track:
                uri = spotify_track.uri
                if uri:
                    track_model = Track.factory(uri=uri, search_model=search_item)
                    db_track_list.append(track_model)
        Track.objects.bulk_create(db_track_list)

    def search_track(self, search, limit=10):
        if search:
            kw = search.keywords.lower()
            results = self.instance.search(q=kw, limit=limit)
            search_result = [track for idx, track in enumerate(results['tracks']['items'])]
            validate = lambda s: kw.__contains__(s['artists'][0].get('name').lower())
            factory = lambda t: SpotifyTrack.factory(spotify_track=t, uri=t['uri'])
            filtered_search = [factory(track) for track in search_result if validate(track)]
            return filtered_search


class SpotipyPlaylistPool:
    from queue import Queue
    __instance = None
    __resources = Queue()
    __resources.put(Spotipy.playlist_modify())
    __resources.put(Spotipy.playlist_second())

    def __init__(self):
        if SpotipyPlaylistPool.__instance is not None:
            raise NotImplemented("singleton class")

    @staticmethod
    def getInstance():
        if SpotipyPlaylistPool.__instance is None:
            SpotipyPlaylistPool.__instance = SpotipyPlaylistPool()

        return SpotipyPlaylistPool.__instance

    def getResource(self):
        if not self.__resources.empty():
            print("Using existing resource")
            return self.__resources.get(True)
        else:
            print("Waiting for new resource indefinitely")

    def returnResource(self, resource):
        resource.reset()
        self.__resources.put(resource)


# class SpotipyQueue:
#     _q = None
#     o = None
#
#     def __init__(self, dQ, autoGet=False):
#         self._q = dQ
#
#         if autoGet:
#             self.o == self._q.get()
#
#     def __enter__(self):
#         if self.o == None:
#             self.o = self._q.get()
#             return self.o
#         else:
#             return self.o
#
#     def __exit__(self, type, value, traceback):
#         if self.o is None:
#             self._q.put(self.o)
#             self.o = None
#
#     def __del__(self):
#         if self.o is None:
#             self._q.put(self.o)
#             self.o = None


class SpotifyTrack:

    def __init__(self, spotify_track, uri):
        self.spotify_track = spotify_track
        self.uri = uri

    def __str__(self):
        return str({**{'uri': self.uri}, **self.spotify_track})

    @classmethod
    def factory(cls, spotify_track, uri):
        return cls(spotify_track, uri)


class SearchQuery(models.Model):
    key = models.CharField(max_length=200, primary_key=True)
