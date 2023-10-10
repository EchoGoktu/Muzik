import re

from .common import InfoExtractor
from ..utils import (
    int_or_none,
    parse_duration,
    traverse_obj,
    url_or_none,
)


class JTBCIE(InfoExtractor):
    IE_DESC = 'jtbc.co.kr'
    _VALID_URL = r'''(?x)
        https?://(?:
            vod\.jtbc\.co\.kr/player/(?:program|clip)
            |tv\.jtbc\.co\.kr/(?:replay|trailer|clip)/pr\d+/pm\d+
        )/(?P<id>(?:ep|vo)\d+)'''
    _GEO_COUNTRIES = ['KR']

    _TESTS = [{
        'url': 'https://tv.jtbc.co.kr/replay/pr10011629/pm10067930/ep20216321/view',
        'md5': 'e6ade71d8c8685bbfd6e6ce4167c6a6c',
        'info_dict': {
            'id': 'ep20216321',
            'ext': 'mp4',
            'title': '힘쎈여자 강남순 2회 다시보기',
            'description': 'md5:043c1d9019100ce271dba09995dbd1e2',
            'duration': 3770.0,
            'release_date': '20231008',
            'age_limit': 15,
            'thumbnail': 'https://fs.jtbc.co.kr//joydata/CP00000001/prog/drama/stronggirlnamsoon/img/20231008_163541_522_1.jpg',
            'series': '힘쎈여자 강남순',
        },
    }, {
        'url': 'https://vod.jtbc.co.kr/player/program/ep20216733',
        'md5': '217a6d190f115a75e4bda0ceaa4cd7f4',
        'info_dict': {
            'id': 'ep20216733',
            'ext': 'mp4',
            'title': '헬로 마이 닥터 친절한 진료실 149회 다시보기',
            'description': 'md5:1d70788a982dd5de26874a92fcffddb8',
            'duration': 2720.0,
            'release_date': '20231009',
            'age_limit': 15,
            'thumbnail': 'https://fs.jtbc.co.kr//joydata/CP00000001/prog/culture/hellomydoctor/img/20231009_095002_528_1.jpg',
            'series': '헬로 마이 닥터 친절한 진료실',
        },
    }, {
        'url': 'https://vod.jtbc.co.kr/player/clip/vo10721270',
        'md5': '05782e2dc22a9c548aebefe62ae4328a',
        'info_dict': {
            'id': 'vo10721270',
            'ext': 'mp4',
            'title': '뭉쳐야 찬다3 2회 예고편 - A매치로 향하는 마지막 관문💥',
            'description': 'md5:d48b51a8655c84843b4ed8d0c39aae68',
            'duration': 46.0,
            'release_date': '20231015',
            'age_limit': 15,
            'thumbnail': 'https://fs.jtbc.co.kr//joydata/CP00000001/prog/enter/soccer3/img/20231008_210957_775_1.jpg',
            'series': '뭉쳐야 찬다3',
        },
    }, {
        'url': 'https://tv.jtbc.co.kr/trailer/pr10010392/pm10032526/vo10720912/view',
        'md5': '217a6d190f115a75e4bda0ceaa4cd7f4',
        'info_dict': {
            'id': 'vo10720912',
            'ext': 'mp4',
            'title': '아는 형님 404회 예고편 | 10월 14일(토) 저녁 8시 50분 방송!',
            'description': 'md5:2743bb1079ceb85bb00060f2ad8f0280',
            'duration': 148.0,
            'release_date': '20231014',
            'age_limit': 15,
            'thumbnail': 'https://fs.jtbc.co.kr//joydata/CP00000001/prog/enter/jtbcbros/img/20231006_230023_802_1.jpg',
            'series': '아는 형님',
        },
    }]

    def _real_extract(self, url):
        video_id = self._match_id(url)
        webpage = self._download_webpage(url, video_id)

        file_id = self._search_regex(r'data-vod="(VO\d+)"', webpage, 'vod id')

        metadata = self._download_json(
            f'https://now-api.jtbc.co.kr/v1/vod/detail?vodFileId={file_id}',
            video_id, note='Downloading mobile details', fatal=False)

        playback_data = self._download_json(
            f'https://api.jtbc.co.kr/vod/{file_id}', video_id, note='Downloading VOD playback data')

        subtitles = {}
        for sub in traverse_obj(playback_data, ('tracks', lambda _, v: v['file'])):
            subtitles.setdefault(sub.get('label', 'und'), []).append({'url': sub['file']})

        formats = []
        for stream in traverse_obj(playback_data, ('sources', 'HLS', lambda _, v: v['file'])):
            m3u8_url = re.sub(r'/playlist(?:_pd\d+)?\.m3u8', '/index.m3u8', stream['file'])
            formats.extend(self._extract_m3u8_formats(m3u8_url, video_id, fatal=False))

        return {
            'id': video_id,
            **traverse_obj(metadata, ('vodDetail', {
                'title': 'vodTitleView',
                'series': 'programTitle',
                'age_limit': ('watchAge', {int_or_none}),
                'release_date': ('broadcastDate', {lambda x: re.match(r'\d{8}', x.replace('.', ''))}, 0),
                'description': 'episodeContents',
                'thumbnail': ('imgFileUrl', {url_or_none}),
            })),
            'duration': parse_duration(playback_data.get('playTime')),
            'formats': formats,
            'subtitles': subtitles,
        }


class JTBCProgramIE(InfoExtractor):
    IE_NAME = 'JTBC:program'
    _VALID_URL = r'https?://(?:vod\.jtbc\.co\.kr/program|tv\.jtbc\.co\.kr/replay)/(?P<id>pr\d+)/(?:replay|pm\d+)/?(?:$|[?#])'

    _TESTS = [{
        'url': 'https://tv.jtbc.co.kr/replay/pr10010392/pm10032710',
        'info_dict': {
            '_type': 'playlist',
            'id': 'pr10010392',
        },
        'playlist_count': 398,
    }, {
        'url': 'https://vod.jtbc.co.kr/program/pr10011491/replay',
        'info_dict': {
            '_type': 'playlist',
            'id': 'pr10011491',
        },
        'playlist_count': 59,
    }]

    def _real_extract(self, url):
        program_id = self._match_id(url)

        vod_list = self._download_json(
            'https://now-api.jtbc.co.kr/v1/vodClip/programHome/programReplayVodList', program_id,
            note='Downloading program replay list', query={
                'programId': program_id,
                'rowCount': '10000',
            })

        entries = [self.url_result(f'https://vod.jtbc.co.kr/player/program/{video_id}', JTBCIE, video_id)
                   for video_id in traverse_obj(vod_list, ('programReplayVodList', ..., 'episodeId'))]

        return self.playlist_result(entries, program_id)
