#!/usr/bin/env python3
# 310直播 V1.1 - remarks格式: 🔴 MM-DD HH:MM league
import re, json, time, requests
from base.spider import Spider as BaseSpider

HOST = 'https://www.cnrbc.com'
LOGO = HOST + '/favicon.ico'
UA = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/140.0.0.0 Safari/537.36'


class Spider(BaseSpider):
    def getName(self):
        return "310直播"

    def init(self, extend=""):
        self.host = HOST
        self._cache = {}
        self._CACHE_TTL = 120

    def _get_cache(self, key):
        e = self._cache.get(key)
        if e and time.time() - e['t'] < self._CACHE_TTL:
            return e['v']
        return None

    def _set_cache(self, key, val):
        self._cache[key] = {'v': val, 't': time.time()}

    def _headers(self):
        return {'User-Agent': UA, 'Referer': HOST + '/', 'Accept': 'text/html,application/xhtml+xml'}

    def _get_html(self, url):
        try:
            r = requests.get(url, headers=self._headers(), timeout=15)
            r.encoding = r.apparent_encoding or 'utf-8'
            return r.text
        except:
            return ''

    def _parse_cards(self, html):
        if not html: return []
        results = []
        for m in re.finditer(r'<a[^>]*class="clearfix[^"]*"[^>]*href="(https?://[^"]+)"[^>]*>(.*?)</a>', html, re.DOTALL):
            href, body = m.group(1), m.group(2)
            tag_text = m.group(0)[:m.group(0).find('>') + 1]
            if 'video-icon' not in body and '视频直播' not in body:
                continue
            mid_m = re.search(r'/detail/(\d+)', href)
            if not mid_m: continue
            mid = mid_m.group(1)
            home_m = re.search(r'team zhudui.*?<p>([^<]+)', body, re.DOTALL)
            away_m = re.search(r'team kedui.*?<p>([^<]+)', body, re.DOTALL)
            home = home_m.group(1).strip() if home_m else ''
            away = away_m.group(1).strip() if away_m else ''
            if not home or not away: continue
            league_m = re.search(r'<em>([^<]+)</em>\s*<i>([^<]+)', body)
            league = league_m.group(1).strip() if league_m else ''
            match_time = league_m.group(2).strip() if league_m else ''
            date_m = re.search(r'data-time="([^"]+)"', tag_text)
            data_date = date_m.group(1).strip() if date_m else ''
            logo_m = re.search(r'team zhudui.*?src="([^"]+)".*?alt="([^"]+)"', body, re.DOTALL)
            pic = ''
            if logo_m:
                src = logo_m.group(1)
                pic = src if src.startswith('http') else HOST + '/' + src.lstrip('/')
            is_live = 'zb_green' in body
            sport_m = re.search(r'sport_(\d)\.png', body)
            sport_type = 'basketball' if sport_m and sport_m.group(1) == '2' else 'football'
            tag_icon = '\U0001f534' if is_live else ''
            date_part = data_date[5:] if data_date else ''
            parts = []
            if tag_icon: parts.append(tag_icon)
            if date_part: parts.append(date_part)
            if match_time: parts.append(match_time)
            if league: parts.append(league)
            results.append({
                'mid': mid, 'home': home, 'away': away,
                'league': league, 'time': match_time, 'date': data_date, 'pic': pic,
                'is_live': is_live, 'sport_type': sport_type,
                'remarks': ' '.join(parts) or '直播',
            })
        return results

    def _get_classes(self):
        return [
            {'type_id': 'all', 'type_name': '全部'},
            {'type_id': 'zuqiu', 'type_name': '⚽ 足球'},
            {'type_id': 'lanqiu', 'type_name': '🏀 篮球'},
        ]

    def homeContent(self, filter):
        return {'class': self._get_classes(), 'filters': {}}

    def categoryContent(self, tid, pg, filter, extend):
        try:
            tid = (extend or {}).get('cateId') or tid or 'all'
            pg = int(pg or 1)
            cached = self._get_cache(f'cards_{tid}')
            if cached is not None:
                cards = cached
            else:
                html = self._get_html(HOST)
                all_cards = self._parse_cards(html)
                self._set_cache('cards_all', all_cards)
                cards = all_cards
                if tid == 'zuqiu':
                    cards = [c for c in all_cards if c['sport_type'] == 'football']
                elif tid == 'lanqiu':
                    cards = [c for c in all_cards if c['sport_type'] == 'basketball']
                else:
                    cards = all_cards
                self._set_cache(f'cards_{tid}', cards)
            list_items = []
            for c in cards:
                list_items.append({
                    'vod_id': f'310|{c["mid"]}',
                    'vod_name': f'{c["home"]} vs {c["away"]}',
                    'vod_pic': c['pic'] or LOGO,
                    'vod_remarks': c['remarks'],
                    'type_name': c['league'] or '全部',
                })
            return {
                'page': pg, 'pagecount': 1, 'limit': len(list_items),
                'total': len(list_items), 'list': list_items,
            }
        except:
            return {'page': 1, 'pagecount': 1, 'limit': 30, 'total': 0, 'list': []}

    def detailContent(self, ids):
        try:
            vid = (ids[0] if isinstance(ids, list) else str(ids or '')).strip()
            if not vid: return {'list': []}
            parts = vid.split('|')
            mid = parts[1] if len(parts) > 1 else parts[0]
            url = f'{HOST}/detail/{mid}'
            html = self._get_html(url)
            if not html: return {'list': []}
            name = ''
            h1_m = re.search(r'<h[12][^>]*>([\s\S]*?)</h[12]>', html)
            if h1_m:
                h_text = re.sub(r'<[^>]+>', '', h1_m.group(1)).strip()
                h_text = re.sub(r'^正在直播：\s*', '', h_text)
                vs_m = re.match(r'^(?:\d{2}-\d{2}\s+\d{2}:\d{2}\s+)?(.+?)\s*[-–—]?\s*vs\s*[-–—]?\s*(.+?)(?:\s*[\(（].*?[\)）])?\s*$', h_text)
                if vs_m:
                    name = vs_m.group(1).strip() + ' vs ' + vs_m.group(2).strip()
            if not name:
                title_m = re.search(r'<title>([^<]+)', html)
                if title_m:
                    t = title_m.group(1).strip()
                    t = re.sub(r'【310直播】.*?为您在线直播', '', t).strip()
                    t = re.sub(r'-310直播$', '', t).strip()
                    vs_m3 = re.match(r'^(.+?)\s*vs\s*(.+?)$', t)
                    if vs_m3:
                        name = vs_m3.group(1).strip() + ' vs ' + vs_m3.group(2).strip()
                    else:
                        name = t
            if not name: name = '直播'
            play_url = ''
            m3u8_m = re.search(r"src:\s*'([^']*\.m3u8[^']*)'", html)
            if m3u8_m:
                play_url = m3u8_m.group(1).replace('&amp;', '&')
            if not play_url:
                m3u8_m2 = re.search(r"https?://[^\"'\s]+\.m3u8[^\"'\s]*", html)
                if m3u8_m2: play_url = m3u8_m2.group(0)
            pic = LOGO
            img_m = re.search(r'<img[^>]*src="([^"]*)"[^>]*class="lazy"', html)
            if not img_m:
                img_m = re.search(r'team\s+zhudui.*?<img[^>]*src="([^"]+)"', html, re.DOTALL)
            if not img_m:
                img_m = re.search(r'<img[^>]*src="([^"]*badge/competitors[^"]+)"', html)
            if img_m:
                src = img_m.group(1)
                pic = src if src.startswith('http') else HOST + '/' + src.lstrip('/')
            if play_url == '': play_url = HOST
            has_signal = play_url != HOST
            return {'list': [{
                'vod_id': vid,
                'vod_name': name,
                'vod_pic': pic,
                'vod_remarks': '',
                'vod_play_from': '310直播',
                'vod_play_url': f'直播地址${play_url}' if has_signal else f'暂无信号${HOST}',
                'vod_content': name,
            }]}
        except:
            return {'list': []}

    def searchContent(self, kw, quick, pg):
        return {'page': 1, 'pagecount': 1, 'limit': 20, 'total': 0, 'list': []}

    def playerContent(self, flag, id, vipFlags):
        try:
            url = str(id or '')
            parse = 0 if re.search(r'\.(m3u8|flv|mp4)(\?|$)', url, re.IGNORECASE) else 1
            return {'parse': parse, 'url': url, 'header': {
                'User-Agent': UA, 'Referer': HOST + '/', 'Origin': HOST
            }}
        except:
            return {'parse': 1, 'url': str(id or '')}

    def localProxy(self, param):
        return [200, "text/plain", b"", {}]
