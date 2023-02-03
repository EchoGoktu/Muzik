import json

from time import (strftime, gmtime)
from .gigya import GigyaBaseIE
from ..compat import compat_HTTPError
from ..utils import (
    parse_iso8601,
    ExtractorError,
    int_or_none,
    float_or_none,
    str_or_none,
    url_or_none,
    urlencode_postdata
)


class VRTIE(GigyaBaseIE):
    IE_DESC = 'VRT'
    _VALID_URL = r'https?://(?:www\.)?vrt\.be/vrtnu/a-z/(?:[^/]+/){2}(?P<id>[^/?#&]+)'
    _TESTS = [{
        'url': 'https://www.vrt.be/vrtnu/a-z/de-ideale-wereld/2023-vj/de-ideale-wereld-d20230116/',
        'info_dict': {
            'id': 'pbs-pub-855b00a8-6ce2-4032-ac4f-1fcf3ae78524$vid-d2243aa1-ec46-4e34-a55b-92568459906f',
            'title': 'Tom Waes',
            'thumbnail': 'https://images.vrt.be/orig/2023/01/10/1bb39cb3-9115-11ed-b07d-02b7b76bf47f.jpg',
            'ext': 'mp4',
            'duration': 1939.0,
            'release_date': '20230116',
            'description': 'Satirisch actualiteitenmagazine met Ella Leyers. Tom Waes is te gast.',
            'display_id': 'de-ideale-wereld-d20230116',
            'episode_number': 1,
            'timestamp': 1673905125,
            'series': 'De ideale wereld',
            'upload_date': '20230116',
            'channel': 'VRT',
            'season_id': '1672830988794',
            'episode_id': '1672830988861',
            'release_timestamp': 1673905125,
            'episode': 'Aflevering 1'
        },
    }]
    _NETRC_MACHINE = 'vrtnu'
    _APIKEY = '3_0Z2HujMtiWq_pkAjgnS2Md2E11a1AwZjYiBETtwNE-EoEHDINgtnvcAOpNgmrVGy'
    _CONTEXT_ID = 'R3595707040'
    _REST_API_BASE_TOKEN = 'https://media-services-public.vrt.be/vualto-video-aggregator-web/rest/external/v2'
    _REST_API_BASE_VIDEO = 'https://media-services-public.vrt.be/media-aggregator/v2'
    _HLS_ENTRY_PROTOCOLS_MAP = {
        'HLS': 'm3u8_native',
        'HLS_AES': 'm3u8_native',
    }

    _authenticated = False

    def _perform_login(self, username, password):
        auth_info = self._gigya_login({
            'APIKey': self._APIKEY,
            'targetEnv': 'jssdk',
            'loginID': username,
            'password': password,
            'authMode': 'cookie',
        })

        if auth_info.get('errorDetails'):
            raise ExtractorError('Unable to login: VrtNU said: ' + auth_info.get('errorDetails'), expected=True)

        # Sometimes authentication fails for no good reason, retry
        login_attempt = 1
        while login_attempt <= 3:
            try:
                self._request_webpage('https://token.vrt.be/vrtnuinitlogin',
                                      None, note='Requesting XSRF Token', errnote='Could not get XSRF Token',
                                      query={'provider': 'site', 'destination': 'https://www.vrt.be/vrtnu/'})

                post_data = {
                    'UID': auth_info['UID'],
                    'UIDSignature': auth_info['UIDSignature'],
                    'signatureTimestamp': auth_info['signatureTimestamp'],
                    '_csrf': self._get_cookies('https://login.vrt.be').get('OIDCXSRF').value,
                }

                self._request_webpage(
                    'https://login.vrt.be/perform_login',
                    None, note='Performing login', errnote='perform login failed',
                    headers={}, query={
                        'client_id': 'vrtnu-site'
                    }, data=urlencode_postdata(post_data))

            except ExtractorError as e:
                if isinstance(e.cause, compat_HTTPError) and e.cause.code == 401:
                    login_attempt += 1
                    self.report_warning('Authentication failed')
                    self._sleep(1, None, msg_template='Waiting for %(timeout)s seconds before trying again')
                else:
                    raise e
            else:
                break

        self._authenticated = True

    def _real_extract(self, url):
        display_id = self._match_id(url)

        model_json = self._download_json(f'{url.strip("/")}.model.json', display_id,
                                         'Downloading asset JSON', 'Unable to download asset JSON')
        details = model_json.get('details')
        actions = details.get('actions')
        title = details.get('title')
        episode_publication_id = actions[2].get('episodePublicationId')
        episode_video_id = actions[2].get('episodeVideoId')
        video_id = f'{episode_publication_id}${episode_video_id}'
        description = details.get('description')
        episode = details.get('data').get('episode')
        display_id = episode.get('name')
        timestamp = parse_iso8601(episode.get('onTime').get('raw'))
        upload_date = strftime('%Y%m%d', gmtime(timestamp))
        series_info = details.get('data')
        series = series_info.get('program').get('title')
        season = series_info.get('season').get('title').get('value')
        season_number = series_info.get('season').get('title').get('raw')
        season_id = series_info.get('season').get('id')
        episode = series_info.get('episode').get('number').get('value')
        episode_number = series_info.get('episode').get('number').get('raw')
        episode_id = series_info.get('episode').get('id')

        video_info = None
        vrtnutoken = ""

        if self._authenticated:
            vrtnutoken = self._download_json('https://token.vrt.be/refreshtoken',
                                             video_id, note='refreshtoken: Retrieve vrtnutoken',
                                             errnote='refreshtoken failed')['vrtnutoken']

        headers = self.geo_verification_headers()
        headers.update({'Content-Type': 'application/json; charset=utf-8'})
        vrtPlayerToken = self._download_json(
            '%s/tokens' % self._REST_API_BASE_TOKEN, video_id,
            'Downloading token', headers=headers, data=json.dumps({
                'identityToken': vrtnutoken
            }).encode('utf-8'))['vrtPlayerToken']

        video_info = self._download_json(
            '%s/media-items/%s' % (self._REST_API_BASE_VIDEO, video_id),
            video_id, 'Downloading video JSON', query={
                'vrtPlayerToken': vrtPlayerToken,
                'client': 'vrtnu-web@PROD',
            }, expected_status=400)
        if 'title' not in video_info:
            code = video_info.get('code')
            if code == 'AUTHENTICATION_REQUIRED':
                self.raise_login_required()
            elif code == 'INVALID_LOCATION':
                self.raise_geo_restricted(countries=['BE'])
            raise ExtractorError(video_info.get('message') or code, expected=True)

        formats = []
        subtitles = {}
        for target in video_info['targetUrls']:
            format_url, format_type = url_or_none(target.get('url')), str_or_none(target.get('type'))
            if not format_url or not format_type:
                continue
            format_type = format_type.upper()
            if format_type in self._HLS_ENTRY_PROTOCOLS_MAP:
                fmts, subs = self._extract_m3u8_formats_and_subtitles(
                    format_url, video_id, 'mp4', self._HLS_ENTRY_PROTOCOLS_MAP[format_type],
                    m3u8_id=format_type, fatal=False)
                formats.extend(fmts)
                subtitles = self._merge_subtitles(subtitles, subs)
            elif format_type == 'HDS':
                formats.extend(self._extract_f4m_formats(
                    format_url, video_id, f4m_id=format_type, fatal=False))
            elif format_type == 'MPEG_DASH':
                fmts, subs = self._extract_mpd_formats_and_subtitles(
                    format_url, video_id, mpd_id=format_type, fatal=False)
                formats.extend(fmts)
                subtitles = self._merge_subtitles(subtitles, subs)
            elif format_type == 'HSS':
                fmts, subs = self._extract_ism_formats_and_subtitles(
                    format_url, video_id, ism_id='mss', fatal=False)
                formats.extend(fmts)
                subtitles = self._merge_subtitles(subtitles, subs)
            else:
                formats.append({
                    'format_id': format_type,
                    'url': format_url,
                })

        subtitle_urls = video_info.get('subtitleUrls')
        if isinstance(subtitle_urls, list):
            for subtitle in subtitle_urls:
                subtitle_url = subtitle.get('url')
                if subtitle_url and subtitle.get('type') == 'CLOSED':
                    subtitles.setdefault('nl', []).append({'url': subtitle_url})

        return {
            'id': video_id,
            'display_id': display_id,
            'timestamp': timestamp,
            'release_timestamp': timestamp,
            'upload_date': upload_date,
            'release_date': upload_date,
            'title': title,
            'description': description,
            'series': series,
            'season': season,
            'season_number': int_or_none(season_number),
            'season_id': season_id,
            'episode': episode,
            'episode_number': episode_number,
            'episode_id': episode_id,
            'channel': 'VRT',
            'formats': formats,
            'duration': float_or_none(video_info.get('duration'), 1000),
            'thumbnail': video_info.get('posterImageUrl'),
            'subtitles': subtitles,
        }
