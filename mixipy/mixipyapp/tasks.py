import time
from contextlib import contextmanager
from hashlib import md5

from celery.utils.log import logger
from django.core.cache import cache
from mixipy.celery import app
from .models import Page, PageMetaInfo, Search, Spotipy, SpotipyPlaylistPool, Playlist, RequestLog

PROCESS_REQUEST = "process_request"
SCRAPE_PAGE_URL = "scrape_page_url"
EXTRACT_PAGES = "extract_pages"
REQUEST_STATUS_UPDATE = "request_status_update"
SEARCH_LIST_CREATE = "search_list_create"
SEARCH_FOR_TRACK = "search_for_track"
TRACKS_TO_PLAYLIST = "tracks_to_playlist"

LOCK_EXPIRE = 60 * 10  # Lock expires in 10 minutes


@contextmanager
def memcache_lock(lock_id, oid):
    timeout_at = time.monotonic() + LOCK_EXPIRE - 3
    # cache.add fails if the key already exists
    status = cache.add(lock_id, oid, LOCK_EXPIRE)
    try:
        yield status
    finally:
        # memcache delete is very slow, but we have to use it to take
        # advantage of using add() for atomic locking
        if time.monotonic() < timeout_at and status:
            # don't release the lock if we exceeded the timeout
            # to lessen the chance of releasing an expired lock
            # owned by someone else
            # also don't release the lock if we didn't acquire it
            cache.delete(lock_id)


@app.task(name=PROCESS_REQUEST)
def process_request(request_id, force):
    request = RequestLog.objects.get(pk=request_id)
    playlist = Playlist.objects.get(request=request)
    Playlist.facade(request, playlist, force)


@app.task(name=SCRAPE_PAGE_URL, bind=True)
def scrape_page_url(self, mode, url):
    page = Page.objects.filter(url=url)
    self.update_state(state='PROGRESS')
    if page:
        print("EXISTING: " + page.first().url)
        page = page.first()
    else:
        page_meta = PageMetaInfo.factory(title='Default', url=url)
        html = page_meta.html()
        page_meta.title = PageMetaInfo.title_from_html(html)
        page = Page.repository(page_meta)
    Search.extract_tracklist(mode, page)


@app.task(name=EXTRACT_PAGES, bind=True)
def scrape_aggregate_url(self, mode, url):
    self.update_state(state='PROGRESS')
    page_meta = PageMetaInfo.factory('scrape_aggregate_url', url)
    page_meta_list = []
    html = page_meta.html()
    if mode == 'MIXESDB':
        page_meta_list = PageMetaInfo.category_extract_page_urls(html)
    elif mode == 'BBC':
        page_meta_list = PageMetaInfo.bbc_brand_extract_page_urls(html)
    for meta in page_meta_list:
        scrape_page_url.apply_async(args=(mode, meta.url))


@app.task(name=REQUEST_STATUS_UPDATE, bind=True)
def request_status(self, request_id):
    self.update_state(state='PROGRESS')
    request = RequestLog.objects.get(pk=request_id)
    request.update_status


@app.task(name=SEARCH_LIST_CREATE, bind=True)
def create_search_using_tracklist(self, page_id, tracklist):
    self.update_state(state='PROGRESS')
    page = Page.objects.get(pk=page_id)
    search_list = [Search.create(keywords=track, page=page) for track in tracklist]
    Search.objects.bulk_create(search_list)
    page.status = Page.SCRAPED
    page.save()


@app.task(name=SEARCH_FOR_TRACK, bind=True, concurrency=1)
def search_for_track(self, page_id):
    self.update_state(state='PROGRESS')
    page = Page.objects.get(pk=page_id)
    if page.is_status(Page.SCRAPED):
        searchlist = Search.objects.filter(page=page)
        sp = Spotipy.search_instance()
        sp.create_tracks_for_page(searchlist)
        # The cache key consists of the task name and the MD5 digest
        # of the feed URL.
        # feed_url_hexdigest = md5(page.url.encode('utf-8')).hexdigest()
        # lock_id = '{0}-lock-{1}'.format(self.name, feed_url_hexdigest)
        # logger.debug('Searching for tracks: %s', page.url.encode('utf-8'))
        # with memcache_lock(lock_id, self.app.oid) as acquired:
        #     if acquired:
        #         sp = Spotipy.search_instance()
        #         sp.create_tracks_for_page(searchlist)
        # logger.debug(
        #     'Url %s is already being imported by another worker', page.url)


@app.task(name=TRACKS_TO_PLAYLIST, bind=True, task_started=False)
def tracks_to_playlist(self, playlist_uri, search_list):
    self.update_state(state='PROGRESS')
    if len(search_list) > 100:
        search_chunks = [search_list[x: x + 100]
                         for x
                         in range(0, len(search_list), 100)]
        for ch in search_chunks:
            tracks_to_playlist.apply_async(args=(playlist_uri, ch))
    else:
        playlist = Playlist.objects.get(uri=playlist_uri)
        playlist.tracks_to_playlist(search_list)
