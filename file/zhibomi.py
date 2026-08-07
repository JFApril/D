#!/usr/bin/env python3
# 直播迷 V1.0 - zhibome.net 单页m.html解析
import re, json, time, requests
from base.spider import Spider as BaseSpider

HOST = 'http://www.zhibome.net'
LIVE_HOST = 'http://www.livezhibomi.xyz'
LOGO = 'http://www.zhibome.net/images/app.png'
UA = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/140.0.0.0 Safari/537.36'


class Spider(BaseSpider):
    def getName(self):
        return "直播迷"

    def init(self, extend=""):
        self.host = HOST
        self._cache = {}
        self._CACHE_TTL = 30

    def _get_cache(self, key):
        e = self._cache.get(key)
        if e and time.time() - e['t'] < self._CACHE_TTL:
            return e['v']
        return None

    def _set_cache(self, key, val):
        self._cache[key] = {'v': val, 't': time.time()}

    def _headers(self):
        return {'User-Agent': UA, 'Referer': HOST + '/'}

    def _get_html(self):
        cached = self._get_cache('html')
        if cached is not None: return cached
        try:
            r = requests.get(HOST + '/m.html', headers=self._headers(), timeout=15)
            r.encoding = r.apparent_encoding or 'utf-8'
            html = r.text
            if html and len(html) > 100:
                self._set_cache('html', html)
                return html
        except:
            pass
        return self._get_cache('html') or ''

    def _parse_matches(self, html):
        if not html: return []
        ul_m = re.search(r'<ul\s+data-role="listview"[^>]*>', html)
        if not ul_m: return []
        ul_start = ul_m.start()
        ul_end = html.find('</ul>', ul_start)
        if ul_end < 0: ul_end = len(html)
        section = html[ul_start:ul_end]

        results = []
        for m in re.finditer(r'<a\s+href="#page_(\d+)"[^>]*>(.*?)</a>', section, re.DOTALL):
            mid = m.group(1)
            body = m.group(2)
            league_m = re.search(r'class=["\']league["\'][^>]*>\s*([^<]+)', body)
            league = league_m.group(1).strip() if league_m else ''
            is_live = "class='live'" in body or 'class="live"' in body
            status_m = re.search(r'class=["\'](?:live|close)["\'][^>]*>\s*([^<]+)', body)
            status_text = status_m.group(1).strip() if status_m else ''
            time_str = status_text if re.match(r'^\d{2}:\d{2}$', status_text) else ''
            if not time_str:
                time_m = re.search(r'(\d{2}:\d{2})', re.sub(r'<[^>]+>', ' ', body))
                if time_m: time_str = time_m.group(1)
            clean_text = re.sub(r'<[^>]+>', ' ', body).strip()
            clean_text = re.sub(r'\s+', ' ', clean_text)
            if league: clean_text = clean_text.replace(league, '', 1)
            if time_str: clean_text = clean_text.replace(time_str, '', 1)
            clean_text = clean_text.replace('VS', '').replace('进入直播频道', '').strip()
            clean_text = re.sub(r'\s+', ' ', clean_text).strip()
            if not league and not clean_text: continue
            results.append({
                'id': mid, 'name': clean_text, 'league': league,
                'time': time_str, 'status': 'live' if is_live else ('close' if status_text else ''),
            })
        return results

    def _get_classes(self, matches):
        seen = {}
        classes = []
        for m in matches:
            lg = m['league']
            if lg and lg not in seen:
                seen[lg] = True
                classes.append({'type_id': lg, 'type_name': lg})
        classes.insert(0, {'type_id': 'all', 'type_name': '全部赛程'})
        classes.insert(0, {'type_id': 'live', 'type_name': '🔴直播中'})
        return classes

    def _get_detail(self, html, mid):
        mark = f'id="page_{mid}"'
        idx = html.find(mark)
        if idx < 0: return {'links': []}
        div_start = html.rfind('<div', 0, idx)
        if div_start < 0: div_start = idx
        next_div = html.find('<div data-role="page"', div_start + 5)
        if next_div < 0: next_div = html.find('</body>', div_start)
        if next_div < 0: next_div = len(html)
        section = html[div_start:next_div]
        content_m = re.search(r'data-role="content"[^>]*class="link"[^>]*>([\s\S]*?)</div>', section)
        if not content_m:
            content_m = re.search(r'data-role="content"[^>]*>([\s\S]*?)</div>', section)
        if not content_m: return {'links': []}
        content = content_m.group(1)
        links = []
        for a_m in re.finditer(r'<a[^>]*href="(https?://[^"]+)"[^>]*>', content):
            url = a_m.group(1)
            if 'plu-' in url:
                links.insert(0, ('原画', url))
            elif 'bb-' in url:
                links.insert(1 if len(links) > 0 else 0, ('备用', url))
            else:
                links.append(('线路' + str(len(links) + 1), url))
        if not links:
            links.append(('直播', LIVE_HOST + '/tv/plu-' + mid + '.html'))
        return {'links': links}

    def _build_remarks(self, m):
        parts = []
        if m['status'] == 'live':
            parts.append('\U0001f534')
            parts.append('直播中')
            if m['time']: parts.append(m['time'])
        elif m['time']:
            parts.append(m['time'])
        else:
            parts.append('待定')
        if m['league']: parts.append(m['league'])
        return ' '.join(parts)

    def homeContent(self, filter):
        html = self._get_html()
        matches = self._parse_matches(html)
        return {'class': self._get_classes(matches), 'filters': {}}

    def categoryContent(self, tid, pg, filter, extend):
        try:
            tid = (extend or {}).get('cateId') or tid or 'all'
            pg = int(pg or 1)
            html = self._get_html()
            matches = self._parse_matches(html)
            if tid == 'live':
                matches = [m for m in matches if m['status'] == 'live']
            elif tid != 'all':
                matches = [m for m in matches if m['league'] == tid]
            list_items = []
            for m in matches:
                list_items.append({
                    'vod_id': m['id'],
                    'vod_name': m['name'],
                    'vod_pic': LOGO,
                    'vod_remarks': self._build_remarks(m),
                    'vod_tag': m['league'],
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
            html = self._get_html()
            matches = self._parse_matches(html)
            target = None
            for m in matches:
                if m['id'] == vid:
                    target = m
                    break
            detail = self._get_detail(html, vid)
            play_urls = [f'{label}${url}' for label, url in detail['links']]
            league = target['league'] if target else ''
            name = target['name'] if target else f'直播-{vid}'
            if league: name = f'\u3010{league}\u3011{name}'
            return {'list': [{
                'vod_id': vid,
                'vod_name': name,
                'vod_pic': LOGO,
                'vod_remarks': target['time'] if target and target['time'] else '直播中',
                'vod_content': f'直播迷体育直播 - {league} {name}',
                'vod_play_from': '直播迷',
                'vod_play_url': '#'.join(play_urls),
            }]}
        except:
            return {'list': []}

    def searchContent(self, kw, quick, pg):
        return {'page': 1, 'pagecount': 1, 'limit': 20, 'total': 0, 'list': []}

    def playerContent(self, flag, id, vipFlags):
        try:
            url = str(id or '')
            ref = LIVE_HOST + '/tv/'
            if 'livezhibomi' in url: ref = HOST + '/m.html'
            elif 'zhibome' in url: ref = HOST + '/'
            parse = 0 if re.search(r'\.(m3u8|mp4|flv|ts)(\?|$)', url, re.IGNORECASE) else 1
            return {'parse': parse, 'url': url, 'header': {
                'User-Agent': UA, 'Referer': ref,
                'Accept': 'text/html,application/xhtml+xml',
            }}
        except:
            return {'parse': 1, 'url': str(id or '')}

    def localProxy(self, param):
        return [200, "text/plain", b"", {}]