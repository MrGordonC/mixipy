import requests
import spotipy
from decouple import config
import re
from bs4 import BeautifulSoup
from spotipy.oauth2 import SpotifyOAuth
from .models import *
from itertools import chain


class Mixipy:
    REQUEST_STATUS_NEW = 1
    REQUEST_STATUS_PENDING = 2
    REQUEST_STATUS_COM = 5
    REQUEST_STATUS_ERROR = 6
    REQUEST_STATUS_CAN = 98
    REQUEST_STATUS_DELETED = 99

    client_id = config('SPOTIFY_CLIENT_ID')
    client_secret = config('SPOTIFY_CLIENT_SECRET')
    redirect_uri = config('REDIRECT_URI')

    @staticmethod
    def create_helper_search(request_url, platform):
        headers = {'User-Agent': 'Mozilla/5.0 (X11; Linux x86_64) '}
        platform_model = platform
        request_log_model, created = RequestLog.objects.get_or_create(url=request_url,
                                                                      platform=platform_model,
                                                                      defaults={'title': 'DefaultTitle',
                                                                                'pub_date': timezone.now(),
                                                                                'status': 1
                                                                                }
                                                                      )
        if created or request_log_model.status < Mixipy.REQUEST_STATUS_COM:
            print('NEW')
            _response = requests.get(request_url, headers=headers)
            request_html = BeautifulSoup(_response.content, 'html.parser')
            title = request_html.find('title').get_text()
            request_log_model.title = title
            request_log_model.save(update_fields=['title'])
            all_urls = list()
            if request_url.__contains__('Category') or request_url.__contains__('brand'):
                print('Factory Pages URL setting: ' + platform.name)
                all_urls = Mixipy.pages_url_factory(platform.name, request_html)
            else:
                print(platform.name + ' page: ' + request_url)
                page_title = PageMetaInfo.title_from_html(request_html)
                all_urls.append(PageMetaInfo.factory(title=page_title, url=request_url))
            # page_list = list()
            # for url in all_urls:
            #     page = Mixipy.page_factory(url, request_log_model)
            #     page_list.append(page)
            page_list = [Mixipy.page_factory(url, request_log_model) for url in all_urls]
            # page_map = list(map(lambda page_meta_info: Mixipy.page_factory(page_meta_info, request_log_model), all_urls))
            search_list = list()
            print("PAGES: " + str(len(page_list)))
            # print("PAGES: " + str(len(list(page_map))))
            # mode = request_log_model.platform.name
            # search_map = list(map(lambda page_model: Mixipy.create_search_for_page(page_model, mode), page_map))
            for page_model in page_list:
                page_track_list = Search.objects.filter(page=page_model.id)
                if page_track_list:
                    search_list = search_list + list(page_track_list)
                else:
                    mode = request_log_model.platform.name
                    name, track_list = Mixipy.search_factory(mode, page_model)
                    search_list = search_list + track_list
            request_log_model.status = Mixipy.REQUEST_STATUS_PENDING
            request_log_model.save()
            print('PEND: ' + request_url)
        return request_log_model

    @staticmethod
    def create_search_for_page(page_model, mode):
        page_track_list = Search.objects.filter(page=page_model.id)
        if page_track_list:
            print("EXISTING TRACKS")
            return list(page_track_list)
        else:
            name, track_list = Mixipy.search_factory(mode, page_model)
            print("NEW TRACKS")
            return track_list


    @staticmethod
    def pages_url_factory(mode, html):
        if mode == 'BBC':
            return Mixipy.bbc_brand_extract_page_urls(html)
        elif mode == 'MIXESDB':
            return Mixipy.category_extract_page_urls(html)
        else:
            return list()

    @staticmethod
    def category_extract_page_urls(mixesdb_html):
        page_urls = list()
        page_html = mixesdb_html
        mixesdb_url = 'https://www.mixesdb.com'
        while page_html:
            urls = Mixipy.mixesdb_extract_page_url_helper(page_html)
            page_urls = page_urls + urls
            # Find next page to parse
            pagination_links = page_html.find('div', class_='listPagination')
            if pagination_links:
                next200_pagination_element = pagination_links.find('a', string='next 200')
                if next200_pagination_element:
                    # print(next200)
                    next200_hyperlink = next200_pagination_element.get('href')
                    next200_url = mixesdb_url + next200_hyperlink
                    # print(next200_url)
                    headers = {'User-Agent': 'Mozilla/5.0 (X11; Linux x86_64) '}
                    next200_request = requests.get(next200_url, headers=headers)
                    page_html = BeautifulSoup(next200_request.content, 'html.parser')
                else:
                    page_html = ''
            else:
                page_html = ''
        return page_urls

    @staticmethod
    def mixesdb_extract_page_url_helper(mixesdb_html):
        urls = list()
        ul_cat_mixes_list_tag = mixesdb_html.find('ul', id='catMixesList')
        li_cat_mixes_list = ul_cat_mixes_list_tag.find_all('li')
        for li_page_tag in li_cat_mixes_list:
            mixlink = li_page_tag.find('a')
            page_title = mixlink.get_text()
            href = mixlink.get('href')
            mix_url = 'https://www.mixesdb.com' + href
            # urls.append(mix_url)
            urls.append(PageMetaInfo.factory(title=page_title, url=mix_url))
        return urls

    @staticmethod
    def bbc_brand_extract_page_urls(bbc_sounds_html):
        print("brand_extract_page_urls")
        brand_urls = list()
        bbc_brand = bbc_sounds_html.find_all('article')
        for episode in bbc_brand:
            url = episode.find('a', class_="sc-c-playable-list-card__link sc-o-link sc-u-flex-grow").get('href')
            page_title = episode.find('p', class_="sc-c-metadata__secondary gel-long-primer gs-u-mt-").get_text()
            desc = episode.find('p', class_="sc-c-metadata__synopsis gel-brevier gs-u-mt- gs-u-mb").get_text()
            url = 'https://www.bbc.co.uk' + url
            brand_urls.append(PageMetaInfo.factory(title=page_title, url=url))
            # brand_urls.append(url)
        return brand_urls

    @staticmethod
    def page_factory(page_meta, request_log):
        page_model, created = Page.objects.get_or_create(
            url=page_meta.url,
            title=page_meta.title,
        )
        PageRequest.objects.get_or_create(page=page_model,
                                          request=request_log)
        return page_model

    @staticmethod
    def search_factory(mode, page):
        print([mode, page.url])
        name, search_list = '', list()
        if mode == 'BBC':
            name, search_list = Mixipy.bbc_page_extract_tracklist(page_model=page)
        elif mode == 'MIXESDB':
            name, search_list = Mixipy.mixesdb_page_extract_tracklist(page_model=page)
        return name, search_list

    @staticmethod
    def bbc_page_extract_tracklist(page_model):
        print(page_model.url)
        url = page_model.url
        tracklist = list()
        bbc_sounds_page_html = requests.get(url)
        bbc_sounds_soup = BeautifulSoup(bbc_sounds_page_html.content, 'html.parser')
        # Mixipy.update_page_title(page_model, bbc_sounds_soup)
        bbc_tracklist = bbc_sounds_soup.find_all('div', class_='sc-u-flex-grow sc-c-basic-tile__text')
        for track_id in bbc_tracklist:
            track = track_id.get('title')
            search_terms = Search.create(keywords=track, page=page_model)
            search_terms.save()
            tracklist.append(search_terms)
        return page_model.title, tracklist

    @staticmethod
    def mixesdb_page_extract_tracklist(page_model):
        # TODO retrieve any cached tracks once page status field added to model:
        tracklist = list()
        headers = {'User-Agent': 'Mozilla/5.0 (X11; Linux x86_64) '}  # \
        # 'AppleWebKit/537.36 (KHTML, like Gecko) ' \
        #  'Chrome/75.0.3770.80 Safari/537.36'}
        mixesdb_html_page = requests.get(page_model.url, headers=headers)
        mixesdb_soup = BeautifulSoup(mixesdb_html_page.text, 'html.parser')
        # Mixipy.update_page_title(page_model, mixesdb_soup)
        print("PAGE TITLE: " + page_model.title)
        tracklist_h2_tag = mixesdb_soup.find('h2', id='Tracklist')
        current_page_element = tracklist_h2_tag
        search_raw_list = list()
        while current_page_element:
            ol_section_tag = current_page_element.find_next('ol')
            if ol_section_tag:
                li_track_tags = ol_section_tag.find_all('li')
                if li_track_tags:
                    search_raw_list = search_raw_list + li_track_tags
            current_page_element = ol_section_tag
        if len(search_raw_list) == 0:
            print("PAGE " + page_model.url + " using fallback method")
            current_div_list_tag = mixesdb_soup.find('div', class_='list')
            while current_div_list_tag:
                div_list_track_tag = current_div_list_tag.find_next('div', {
                    'class': ['list-track', 'aff-api-done', 'list-track aff-done aff-api-done',
                              'list-track aff-api-undone-search aff-done aff-api-done']})
                if div_list_track_tag:
                    if div_list_track_tag.find_previous('h2', id='comments'):
                        current_div_list_tag = False
                    else:
                        search_raw_list.append(div_list_track_tag)
                        current_div_list_tag = div_list_track_tag
                else:
                    current_div_list_tag = False
        else:
            print("PAGE " + page_model.url + " using primary method")
        if len(search_raw_list) == 0:
            print("NO TRACKS FOUND: " + page_model.url)
            return page_model.title, list()
        else:
            # TODO convert to listcomp
            for search_html_tag in search_raw_list:
                search_str_raw = search_html_tag.get_text()
                search_str = re.sub(r'\[[^\]]*\]', '', search_str_raw).strip()
                if Mixipy.valid_mixesdb_search(search_str):
                    search_terms = Search.create(keywords=search_str, page=page_model)
                    search_terms.save()
                    tracklist.append(search_terms)
            return page_model.title, tracklist

    @staticmethod
    def valid_mixesdb_search(search_str):
        filt = list(['?', 'intro', 'unknown'])
        if filt.__contains__(str(search_str).lower()):
            return False
        else:
            if search_str.__contains__('-'):
                return True
            else:
                # print("FILTERED: " + search_str)
                return False

    @staticmethod
    def update_page_title(page_model, html):
        if page_model.title is None or '' or 'PageDefault':
            print('Updating title')
            page_name = html.find('title').get_text()
            page_model.title = page_name
            page_model.save(update_fields=['title'])

    @staticmethod
    def create_helper_playlist(request):
        existing_playlist = Playlist.objects.filter(request_id=request)
        if existing_playlist and Mixipy.REQUEST_STATUS_COM:
            return existing_playlist.first()
        elif request.status == Mixipy.REQUEST_STATUS_PENDING:
            linked_pages = PageRequest.objects.filter(request_id=request)
            pages_map = map(lambda page_request: page_request.page_id, linked_pages)
            page_id_list = list(pages_map)
            track_list = set()
            for page_id in page_id_list:
                page_model = Page.objects.get(pk=page_id)
                if page_model.title == '':
                    Mixipy.update_page_title(page_model)
                page_tracks = Search.objects.filter(page=page_model)
                track_list = track_list | set(page_tracks)
                if len(page_tracks) == 0:
                    print(page_model.url)
            spotify_track_uri_list = Mixipy.find_spotify_tracklist(track_list)
            playlist_uri = Mixipy.create_playlist_add_tracks(request.title, spotify_track_uri_list)
            playlist_model = Playlist(name=request.title, platform=request.platform, request=request, uri=playlist_uri,
                                      description='TEST')
            request.status = Mixipy.REQUEST_STATUS_COM
            request.save()
            playlist_model.save()
            print("COM - Playlist: " + str(playlist_model.id))
            return playlist_model
        else:
            print('ERR - Request Status: ' + request.status)

    @staticmethod
    def find_spotify_tracklist(search_list):
        track_model_set = set()
        spotipy_api = spotipy.Spotify(auth_manager=SpotifyOAuth(client_id=Mixipy.client_id,
                                                                client_secret=Mixipy.client_secret,
                                                                redirect_uri=Mixipy.redirect_uri,
                                                                scope="user-library-read"))
        for search_item in search_list:
            existing_track = Track.objects.filter(search=search_item)
            if existing_track:
                track_model_set.add(existing_track.first())
            else:
                spotify_track = Mixipy.search_spotify_track(search_item, spotipy_api)
                if spotify_track:
                    uri = spotify_track.uri
                    if uri:
                        track_model = Mixipy.track_factory(uri=uri, search_model=search_item)
                        track_model.save()
                        track_model_set.add(track_model)
        print('TRACKS FOUND: ' + str(len(track_model_set)) + '/' + str(len(search_list)))
        return track_model_set

    @staticmethod
    def track_factory(uri, search_model):
        return Track.create(uri=uri, search=search_model)

    @staticmethod
    def create_playlist_add_tracks(title, spotify_uri):
        spotipy_api, play_list = Mixipy.init_spotify_playlist(title)
        playlist_uri = str(play_list['uri'])
        # convert from track to uri
        spotify_map = map(lambda x: x.uri, spotify_uri)
        playlist = list(spotify_map)
        # only 100 tracks can be added per api request
        playlist_chunks = [playlist[x: x + 100] for x in range(0, len(playlist), 100)]
        for chunk in playlist_chunks:
            spotipy_api.playlist_add_items(playlist_id=playlist_uri, items=chunk, position=None)
        return playlist_uri

    @staticmethod
    def init_spotify_playlist(title):
        scope = "playlist-modify-public"
        spotify_api = spotipy.Spotify(auth_manager=SpotifyOAuth(client_id=Mixipy.client_id,
                                                                client_secret=Mixipy.client_secret,
                                                                redirect_uri=Mixipy.redirect_uri,
                                                                scope=scope))
        user_id = spotify_api.me()['id']
        playlist_uri = spotify_api.user_playlist_create(user_id, title)
        return spotify_api, playlist_uri

    @staticmethod
    def search_spotify_track(search, sp):
        if search:
            results = sp.search(q=search.keywords, limit=10)
            for idx, track in enumerate(results['tracks']['items']):
                if str(search.keywords.lower()).__contains__(track['artists'][0].get('name').lower()):
                    uri = track['uri']
                    return SpotifyTrack.factory(spotify_track=track, uri=uri)
                # else:
                # TODO log near-matches
                #    print([search, track['artists'][0].get('name')])


class PageMetaInfo:

    def __init__(self, title, url):
        self.title = title
        self.url = url

    @classmethod
    def factory(cls, title, url):
        return cls(title, url)

    @staticmethod
    def title_from_html(html):
        return html.find('title').get_text()


class SpotifyTrack:

    def __init__(self, spotify_track, uri):
        self.spotify_track = spotify_track
        self.uri = uri

    @classmethod
    def factory(cls, spotify_track, uri):
        return cls(spotify_track, uri)
