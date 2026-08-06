#!/usr/bin/env python3
import re, json, time, requests
from urllib.parse import quote
from base.spider import Spider as BaseSpider

HOST = 'https://www.doubaozhibo.com'
UA = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/140.0.0.0 Safari/537.36'

class Spider(BaseSpider):
    def getName(self):
        return "豆包直播"

    def init(self, extend=""):
        self.host = HOST
        self.ua = UA
        self._cache = {}
        self._CACHE_TTL = 600

    def _get_cache(self, key):
        e = self._cache.get(key)
        if e and time.time() - e['t'] < self._CACHE_TTL:
            return e['v']
        return None

    def _set_cache(self, key, val):
        self._cache[key] = {'v': val, 't': time.time()}

    def _headers(self, referer=None):
        return {
            'User-Agent': self.ua,
            'Referer': referer or self.host + '/',
            'Accept': 'application/json, text/plain, */*',
            'Accept-Language': 'zh-CN,zh;q=0.9,en;q=0.8'
        }

    def _html_headers(self):
        return {
            'User-Agent': self.ua,
            'Referer': self.host + '/',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
            'Accept-Language': 'zh-CN,zh;q=0.9,en;q=0.8'
        }

    def _get(self, url, referer=None, timeout=10):
        try:
            r = requests.get(url, headers=self._headers(referer), timeout=timeout)
            return r.text
        except:
            return ''

    def _get_json(self, url, referer=None, timeout=10):
        try:
            t = self._get(url, referer, timeout)
            return json.loads(t or '{}')
        except:
            return {}

    def _clean(self, s):
        return re.sub(r'<[^>]+>', '', str(s or '')).replace('&nbsp;', ' ').replace('&amp;', '&').replace('"', '"').replace('&#39;', "'").strip()

    def _abs_url(self, url, base=None):
        url = str(url or '').strip()
        base = base or self.host
        if not url: return ''
        if re.match(r'^https?://', url, re.I): return url
        if url.startswith('//'): return 'https:' + url
        if url.startswith('/'): return base.rstrip('/') + url
        return base.rstrip('/') + '/' + url

    def _fmt_time(self, iso_str):
        if not iso_str: return ''
        try:
            t_str = re.sub(r'(\.\d+)?Z$', '', iso_str)
            from datetime import datetime, timezone, timedelta
            dt = datetime.strptime(t_str, '%Y-%m-%dT%H:%M:%S').replace(tzinfo=timezone.utc)
            local = dt.astimezone(timezone(timedelta(hours=8)))
            return local.strftime('%m-%d %H:%M')
        except:
            return ''

    def _parse_api_schedule(self, json_data, tid):
        list_items = []
        days = json_data.get('data', {}).get('days', []) if json_data else []
        for day in days:
            for item in (day.get('live') or []):
                signals = item.get('signals') or []
                if not signals: continue
                league = self._clean(item.get('league', ''))
                teamA = self._clean(item.get('teamA', ''))
                teamB = self._clean(item.get('teamB', ''))
                status = item.get('status')
                match_time = self._fmt_time(item.get('matchTime', ''))
                scoreA = item.get('teamAscore')
                scoreB = item.get('teamBscore')
                score_str = f'{scoreA}-{scoreB}' if scoreA is not None and scoreB is not None else '0:0'
                data_type = str(item.get('dataType', ''))
                if tid and tid != 'all':
                    if tid == 'important' and not item.get('isImportant'): continue
                    if tid == 'football' and data_type != 'football': continue
                    if tid == 'basketball' and data_type != 'basketball': continue
                    if tid == 'worldcup' and '世界杯' not in league: continue
                status_tag = '\U0001f534' if status == 1 else ''
                name = f'{teamA} {score_str} {teamB}'
                remarks_parts = []
                if status_tag: remarks_parts.append(status_tag)
                if match_time: remarks_parts.append(match_time)
                if league: remarks_parts.append(league)
                remarks = ' '.join(remarks_parts) or '直播'
                vod_id = f'live_{item["id"]}'
                pic = item.get('teamAImage') or item.get('teamBImage') or ''
                sig_data = []
                for s in signals:
                    sig_data.append({
                        'name': self._clean(s.get('name') or s.get('label') or ''),
                        'url': self._abs_url(f'/play/{s["playId"]}', self.host)
                    })
                self._set_cache(vod_id, {'name': name, 'signals': sig_data})
                list_items.append({
                    'vod_id': vod_id,
                    'vod_name': name,
                    'vod_pic': pic or f'{self.host}/logo.png',
                    'vod_remarks': remarks
                })
            for item in (day.get('playback') or []):
                league = self._clean(item.get('league', ''))
                teamA = self._clean(item.get('teamA', ''))
                teamB = self._clean(item.get('teamB', ''))
                scoreA = item.get('teamAscore')
                scoreB = item.get('teamBscore')
                score_str = f'({scoreA}-{scoreB})' if scoreA is not None and scoreB is not None else ''
                match_time = self._fmt_time(item.get('matchTime', ''))
                data_type = str(item.get('dataType', ''))
                if tid and tid != 'all' and tid != 'playback':
                    if tid == 'important' and not item.get('isImportant'): continue
                    if tid == 'football' and data_type != 'football': continue
                    if tid == 'basketball' and data_type != 'basketball': continue
                    if tid == 'worldcup' and '世界杯' not in league: continue
                name = f'{teamA} {score_str} {teamB}'.strip()
                remarks_parts = []
                if match_time: remarks_parts.append(match_time)
                if league: remarks_parts.append(league)
                remarks_parts.append('\u25b6\u200b\u25b7\u200b')
                remarks = ' '.join(remarks_parts)
                pb_id = f'pb_{item.get("playbackId") or item.get("id")}'
                pic = item.get('teamAImage') or item.get('teamBImage') or ''
                self._set_cache(pb_id, {'name': name, 'signals': []})
                list_items.append({
                    'vod_id': pb_id,
                    'vod_name': name,
                    'vod_pic': pic or f'{self.host}/logo.png',
                    'vod_remarks': remarks
                })
        return list_items

    def _parse_play_page(self, html):
        if not html: return ''
        m = re.search(r'id="__NUXT_DATA__"[^>]*>([\s\S]*?)</script>', html)
        if m:
            try:
                arr = json.loads(m.group(1))
                for item in arr:
                    if isinstance(item, str) and re.search(r'\.(m3u8|flv|mp4)(\?|$)', item, re.I):
                        return item if item.startswith('http') else self._abs_url(item, self.host)
            except: pass
        m = re.search(r'"proxyUrl"\s*:\s*"((?:\\.|[^"\\])*)"', html)
        if m:
            try:
                url = self._abs_url(json.loads('"' + m.group(1) + '"'), self.host)
                if re.search(r'\.(m3u8|flv|mp4)(\?|$)', url, re.I): return url
            except: pass
        m = re.search(r'(?:https?:)?//[^"\']+\.m3u8[^"\'\s]*', html, re.I)
        if m: return self._abs_url(m.group(0), self.host)
        m = re.search(r'/hls/[A-Za-z0-9._-]+\.m3u8', html, re.I)
        if m: return self._abs_url(m.group(0), self.host)
        return ''

    def _resolve_m3u8(self, play_url):
        if not play_url: return ''
        if re.search(r'\.(m3u8|flv|mp4)(\?|$)', play_url, re.I): return play_url
        cached = self._get_cache('m3u8_' + play_url)
        if cached: return cached
        html = self._get(play_url, self.host + '/')
        m3u8 = self._parse_play_page(html)
        if m3u8 and m3u8 != play_url:
            self._set_cache('m3u8_' + play_url, m3u8)
            return m3u8
        return play_url

    def _get_classes(self):
        return [
            {'type_id': 'all', 'type_name': '⚽全部'},
            {'type_id': 'important', 'type_name': '⭐重要'},
            {'type_id': 'football', 'type_name': '⚽足球'},
            {'type_id': 'basketball', 'type_name': '🏀篮球'},
            {'type_id': 'worldcup', 'type_name': '🌍世界杯'},
            {'type_id': 'playback', 'type_name': '\u25b6\u200b\u25b7\u200b'},
        ]

    def homeContent(self, filter):
        return {'class': self._get_classes(), 'filters': {}}

    def categoryContent(self, tid, pg, filter, extend):
        try:
            tid = (extend or {}).get('cateId') or tid or 'all'
            pg = int(pg or 1)
            json_data = self._get_json(HOST + '/api/v1/schedules/public/local', HOST + '/')
            list_items = self._parse_api_schedule(json_data, tid)
            return {
                'page': pg, 'pagecount': 1, 'limit': len(list_items),
                'total': len(list_items), 'list': list_items
            }
        except:
            return {'page': 1, 'pagecount': 1, 'limit': 30, 'total': 0, 'list': []}

    def detailContent(self, ids):
        try:
            vid = (ids[0] if isinstance(ids, list) else str(ids or '')).strip()
            if not vid: return {'list': []}
            data = self._get_cache(vid)
            if not data:
                json_data = self._get_json(HOST + '/api/v1/schedules/public/local', HOST + '/')
                self._parse_api_schedule(json_data, 'all')
                data = self._get_cache(vid)
            if not data: return {'list': []}
            signals = data.get('signals') or []
            if not signals:
                return {'list': [{
                    'vod_id': vid, 'vod_name': data.get('name', '比赛'),
                    'vod_pic': f'{HOST}/logo.png', 'vod_remarks': '暂无信号',
                    'vod_play_from': '豆包直播', 'vod_play_url': f'暂无${HOST}/',
                    'vod_content': '暂无可用信号'
                }]}
            play_urls = '#'.join(f'{s["name"]}${s["url"]}' for s in signals)
            return {'list': [{
                'vod_id': vid, 'vod_name': data.get('name', '比赛'),
                'vod_pic': f'{HOST}/logo.png',
                'vod_remarks': f'{len(signals)}个信号',
                'vod_play_from': '豆包直播', 'vod_play_url': play_urls,
                'vod_content': data.get('name', '')
            }]}
        except:
            return {'list': []}

    def searchContent(self, kw, quick, pg):
        return {'page': 1, 'pagecount': 1, 'limit': 30, 'total': 0, 'list': []}

    def playerContent(self, flag, id, vipFlags):
        try:
            url = str(id or '')
            if re.search(r'\.(m3u8|flv|mp4)(\?|$)', url, re.I):
                return {'parse': 0, 'url': url, 'header': {
                    'User-Agent': self.ua, 'Referer': HOST + '/', 'Origin': HOST
                }}
            m3u8 = self._resolve_m3u8(url)
            if m3u8 and re.search(r'\.(m3u8|flv|mp4)(\?|$)', m3u8, re.I):
                return {'parse': 0, 'url': m3u8, 'header': {
                    'User-Agent': self.ua, 'Referer': HOST + '/', 'Origin': HOST
                }}
            return {'parse': 0, 'url': url, 'header': {'User-Agent': self.ua, 'Referer': HOST + '/'}}
        except:
            return {'parse': 0, 'url': str(id or '')}

    def localProxy(self, param):
        return [200, "text/plain", b"", {}]