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
            print(page.url for page in page_list)
            # Page.objects.bulk_create(page_list)
            # page_map = list(map(lambda page_meta_info: Mixipy.page_factory(page_meta_info, request_log_model), all_urls))
            search_list = list()
            print("PAGES: " + str(len(page_list)))
            # print("PAGES: " + str(len(list(page_map))))
            # mode = request_log_model.platform.name
            # search_map = list(map(lambda page_model: Mixipy.create_search_for_page(page_model, mode), page_map))
            # search_list = [Search.objects.filter(page=page.id) for page in page_list]
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
            return []

    @staticmethod
    def category_extract_page_urls(mixesdb_html):
        page_urls = []
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
        # urls = list()
        ul_cat_mixes_list_tag = mixesdb_html.find('ul', id='catMixesList')
        li_cat_mixes_list = ul_cat_mixes_list_tag.find_all('li')
        # for li_page_tag in li_cat_mixes_list:
        #     mixlink = li_page_tag.find('a')
        #     page_title = mixlink.get_text()
        #     href = mixlink.get('href')
        #     mix_url = 'https://www.mixesdb.com' + href
        #     urls.append(PageMetaInfo.factory(title=page_title, url=mix_url))
        mixlink_list = [mix_link.find('a') for mix_link in li_cat_mixes_list]
        mix_url = 'https://www.mixesdb.com'
        factory = lambda m: PageMetaInfo.factory(title=m.get_text(), url=mix_url + m.get('href'))
        # page_meta_list = [PageMetaInfo.factory(title=mix.get_text(), url=mix_url + mix.get('href')) for mix in mixlink_list]
        page_meta_list = [factory(mix) for mix in mixlink_list]
        [print(pm) for pm in page_meta_list]
        return page_meta_list

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
        name, search_list = '', []
        if mode == 'BBC':
            name, search_list = Mixipy.bbc_page_extract_tracklist(page_model=page)
        elif mode == 'MIXESDB':
            name, search_list = Mixipy.mixesdb_page_extract_tracklist(page_model=page)
        return name, search_list

    @staticmethod
    def bbc_page_extract_tracklist(page_model):
        print(page_model.url)
        url = page_model.url
        # tracklist = list()
        bbc_sounds_page_html = requests.get(url)
        bbc_sounds_soup = BeautifulSoup(bbc_sounds_page_html.content, 'html.parser')
        # Mixipy.update_page_title(page_model, bbc_sounds_soup)
        tracklist_tag = 'sc-u-flex-grow sc-c-basic-tile__text'
        bbc_tracklist = bbc_sounds_soup.find_all('div', class_=tracklist_tag)
        name = lambda track: track.get('title')
        tracklist = [name(track) for track in bbc_tracklist]
        search_create = lambda s: Search.create(keywords=s, page=page_model)
        search_list = [search_create(track) for track in tracklist]
        # for track_id in bbc_tracklist:
        #     track = track_id.get('title')
        #     search_terms = Search.create(keywords=track, page=page_model)
        #     search_terms.save()
        #     tracklist.append(search_terms)
        Search.objects.bulk_create(search_list)
        return page_model.title, search_list

    @staticmethod
    def mixesdb_page_extract_tracklist(page_model):
        # TODO retrieve any cached tracks once page status field added to model:
        tracklist = list()
        headers = {'User-Agent': 'Mozilla/5.0 (X11; Linux x86_64) '}  # \
        # 'AppleWebKit/537.36 (KHTML, like Gecko) ' \
        #  'Chrome/75.0.3770.80 Safari/537.36'}
        mixesdb_html_page = requests.get(page_model.url, headers=headers)
        mixesdb_soup = BeautifulSoup(mixesdb_html_page.content, 'html.parser')
        # Mixipy.update_page_title(page_model, mixesdb_soup)
        print("PAGE TITLE: " + page_model.title)
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
            print("PAGE " + page_model.url + " using fallback method")
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
            print("PAGE " + page_model.url + " using primary method")
        if len(search_raw_list) == 0:
            print("NO TRACKS FOUND: " + page_model.url)
            return page_model.title, []
        else:
            # TODO convert to listcomp
            format = lambda s: re.sub(r'\[[^\]]*\]', '', s.get_text()).strip().lower()
            valid = lambda s: Mixipy.valid_mixesdb_search(s)
            formatted_search_results = [format(search_html_tag) for search_html_tag in search_raw_list]
            tracklist = [Search.create(search, page_model) for search in formatted_search_results if valid(search)]
            Search.objects.bulk_create(tracklist)
            # for search_html_tag in search_raw_list:
            #     search_str_raw = search_html_tag.get_text()
            #     search_str = re.sub(r'\[[^\]]*\]', '', search_str_raw).strip()
            #     if Mixipy.valid_mixesdb_search(search_str):
            #         search_terms = Search.create(keywords=search_str, page=page_model)
            #         search_terms.save()
            #         tracklist.append(search_terms)
            return page_model.title, tracklist

    @staticmethod
    def valid_mixesdb_search(search_str):
        filt = ['?', 'intro', 'unknown']
        if filt.__contains__(search_str):
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
            print('UPDATE PAGE TITLE: ' + page_model.title)
            page_name = html.find('title').get_text()
            page_model.title = page_name
            page_model.save(update_fields=['title'])

    @staticmethod
    def create_helper_playlist(request):
        # existing_playlist = Playlist.objects.filter(request_id=request)
        playlist, created = Playlist.objects.get_or_create(request=request,
                                                           defaults={'name': request.title,
                                                                     'platform': request.platform
                                                                     }
                                                           )
        # uri = playlist_uri,
        # description = 'TEST')
        # defaults = {'title': 'DefaultTitle',
        #             'pub_date': timezone.now(),
        #             'status': 1
        #             }
        # if existing_playlist and Mixipy.REQUEST_STATUS_COM:
        if not created and request.status == Mixipy.REQUEST_STATUS_COM:
            # return existing_playlist.first()
            print("RETURNED COMPLETED EXISTING")
            return playlist
        elif request.status == Mixipy.REQUEST_STATUS_PENDING:
            # TODO ONLY 100 tracks can be added at a time - batch api calls so that we search and add in chunks of 100
            linked_pages = PageRequest.objects.filter(request_id=request)
            page_id_list = [page_request.page_id for page_request in linked_pages]
            # track_list = set()
            # for page_id in page_id_list:
            #     page_model = Page.objects.get(pk=page_id)
            #     if page_model.title == '':
            #         Mixipy.update_page_title(page_model)
            #     page_tracks = Search.objects.filter(page=page_model)
            #     track_list = track_list | set(page_tracks)
            #     if len(page_tracks) == 0:
            #         print(page_model.url)
            page_models = [Page.objects.get(pk=page_id) for page_id in page_id_list]
            page_search = [set(Search.objects.filter(page=page)) for page in page_models]
            track_list = list(set().union(*page_search))
            search_chunks = [track_list[x: x + 100]
                             for x
                             in range(0, len(track_list), 100)]
            playlist_uri = playlist.uri
            spotipy_search = Mixipy.spotipy_search_track()
            spotipy_playlist = Mixipy.spotipy_playlist_modify()
            track_batch = []
            search_chunks_iter = iter(search_chunks)
            complete = False
            while not complete:
                next_batch = track_batch
                search_chunk = None
                if len(next_batch) < 100:
                    search_chunk = next(search_chunks_iter, None)
                    if search_chunk:
                        spotify_track_uri_list = Mixipy.find_spotify_tracklist(spotipy_search, search_chunk)
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
                if not playlist_uri:
                    play_list_obj = Mixipy.init_spotify_playlist(spotipy_playlist, playlist.name)
                    playlist_uri = play_list_obj['uri']
                    playlist.uri = playlist_uri
                    playlist.save()
                if playlist.uri and next_batch:
                    ready_batch = [track.uri for track in next_batch]
                    print('READY: ' + str(len(ready_batch)) + ' TRACKBATCH: ' + str(len(track_batch)))
                    Mixipy.post_tracks_to_playlist(spotipy_playlist, playlist_uri, ready_batch)
            # for search_chunk in search_chunks:
            #     spotify_track_uri_list = Mixipy.find_spotify_tracklist(spotipy_search, search_chunk)
            #     track_batch = track_batch + spotify_track_uri_list
            #     if not playlist_uri:
            #         play_list_obj = Mixipy.init_spotify_playlist(spotipy_playlist, playlist.name)
            #         playlist_uri = play_list_obj['uri']
            #         playlist.uri = playlist_uri
            #         playlist.save()
            #     next_batch = track_batch
            #     # if > 100, add to next iteration. If last iteration, commit.
            #     if playlist.uri:
            #         if len(next_batch) >= 100:
            #             track_batch = track_batch[100:]
            #             next_batch = [track.uri for track in track_batch[0:99]]
            #             print(len(next_batch))
            #         else:
            #             print('hi')
            #         Mixipy.post_tracks_to_playlist(spotipy_playlist, playlist_uri, next_batch)
            #         # track_uri_list = [track.uri for track in track_uri_list][0:99]

            request.status = Mixipy.REQUEST_STATUS_COM
            request.save()
            print("COM - Playlist: " + str(playlist.id))
            return playlist
        else:
            print('ERR - Request Status: ' + request.status)

    @staticmethod
    def mixipy_spotipy(scope):
        spotipy_instance = spotipy.Spotify(auth_manager=SpotifyOAuth(client_id=Mixipy.client_id,
                                                                     client_secret=Mixipy.client_secret,
                                                                     redirect_uri=Mixipy.redirect_uri,
                                                                     scope=scope))
        return spotipy_instance

    @staticmethod
    def spotipy_search_track():
        return Mixipy.mixipy_spotipy("user-library-read")

    @staticmethod
    def spotipy_playlist_modify():
        return Mixipy.mixipy_spotipy("playlist-modify-public")

    @staticmethod
    def find_spotify_tracklist(spotipy_instance, search_list):
        track_model_list = []
        spotipy_api = spotipy_instance
        db_track_list = []
        for search_item in search_list:
            existing_track = Track.objects.filter(search=search_item)
            if existing_track:
                track_model_list.append(existing_track.first())
            else:
                spotify_track_matches = Mixipy.search_spotify_track(search_item, spotipy_api, 1)
                spotify_track = next((track for track in spotify_track_matches), None)
                if spotify_track:
                    # nprint(spotify_track)
                    uri = spotify_track.uri
                    if uri:
                        track_model = Mixipy.track_factory(uri=uri, search_model=search_item)
                        # track_model.save()
                        # track_model_list.add(track_model)
                        # track_model_list.append(track_model)
                        db_track_list.append(track_model)
        new_tracklist = Track.objects.bulk_create(db_track_list)
        track_model_list = track_model_list + new_tracklist
        print('TRACKS FOUND: ' + str(len(track_model_list)) + '/' + str(len(search_list)))
        # existing = Track.objects.filter(search=[search_list])
        # api_search = lambda s: Mixipy.search_spotify_track(s, spotipy_api)
        # first_from_api = lambda s: next((track for track in api_search(s)), None)
        # filter_none = lambda s: [search.uri for search in s if first_from_api(s) is not None]
        # track_new = lambda u, s: Mixipy.track_factory(uri=u, search_model=s)
        # new_tracks = lambda s: [track_new(track, )for track in filter_none(s)]
        # existing_tracks = [Track.objects.filter(search=search_item) for search_item in search_list]
        # new, exist = set(), set()
        # for search_item in search_list:
        #    (exist, new)[search_item in ]

        return track_model_list

    @staticmethod
    def track_factory(uri, search_model):
        return Track.create(uri=uri, search=search_model)

    @staticmethod
    def create_add_tracks_to_playlist(title, spotify_uri, spotipy_api, play_list):
        spotipy_api, play_list = Mixipy.init_spotify_playlist(title)
        playlist_uri = str(play_list['uri'])
        # convert from track to uri
        # spotify_map = map(lambda x: x.uri, spotify_uri)
        spotify_map = [track.uri for track in spotify_uri]
        playlist = list(spotify_map)
        # only 100 tracks can be added per api request
        # TODO chunk elsewhere
        playlist_chunks = [playlist[x: x + 100]
                           for x
                           in range(0, len(playlist), 100)]
        for chunk in playlist_chunks:
            Mixipy.post_tracks_to_playlist(spotipy_api, playlist_uri, chunk)
            # spotipy_api.playlist_add_items(playlist_id=playlist_uri, items=chunk, position=None)
        # for chunk in playlist_chunks]
        return playlist_uri

    @staticmethod
    def init_spotify_playlist(spotipy_api, title):
        user_id = spotipy_api.me()['id']
        playlist_obj = spotipy_api.user_playlist_create(user_id, title)
        return playlist_obj

    @staticmethod
    def post_tracks_to_playlist(spotipy_instance, playlist_uri, tracks):
        spotipy_instance.playlist_add_items(playlist_id=playlist_uri, items=tracks, position=None)

    @staticmethod
    def search_spotify_track(search, sp, limit=10):
        if search:
            kw = search.keywords.lower()
            results = sp.search(q=kw, limit=limit)
            # for idx, track in enumerate(results['tracks']['items']):
            #     if str(search.keywords.lower()).__contains__(track['artists'][0].get('name').lower()):
            #         uri = track['uri']
            #         return SpotifyTrack.factory(spotify_track=track, uri=uri)
            search_result = [track for idx, track in enumerate(results['tracks']['items'])]
            validate = lambda s: kw.__contains__(s['artists'][0].get('name').lower())
            factory = lambda t: SpotifyTrack.factory(spotify_track=t, uri=t['uri'])
            filtered_search = [factory(track) for track in search_result if validate(track)]
            return filtered_search
            # else:
            # TODO log near-matches
            #    print([search, track['artists'][0].get('name')])


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


class SpotifyTrack:

    def __init__(self, spotify_track, uri):
        self.spotify_track = spotify_track
        self.uri = uri

    def __str__(self):
        return str({**{'uri': self.uri}, **self.spotify_track})

    @classmethod
    def factory(cls, spotify_track, uri):
        return cls(spotify_track, uri)
