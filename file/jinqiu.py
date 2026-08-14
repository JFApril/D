# @version V4.4
import re, base64, time, json, requests
from base.spider import Spider as BaseSpider

REAL_KEY = bytes.fromhex('4b566b734c326a4a36654c4f50376358')
IV0 = bytes(16)
API = 'https://jk.jkjqtv.com/app'
UA = 'Mozilla/5.0 (Linux; Android 10; Mobile) AppleWebKit/537.36'

def pkcs7_pad(data):
    p = 16 - (len(data) % 16)
    return data + bytes([p]) * p

def pkcs7_unpad(data):
    p = data[-1]
    if 1 <= p <= 16:
        return data[:-p]
    return data

def aes_cbc_enc(key, iv, data):
    c = AES.new(key, AES.MODE_CBC, iv)
    return c.encrypt(pkcs7_pad(data))

def aes_ecb_dec(key, data):
    c = AES.new(key, AES.MODE_ECB)
    return pkcs7_unpad(c.decrypt(data))

def enc(val):
    return base64.b64encode(aes_cbc_enc(REAL_KEY, IV0, val.encode())).decode()

def dec_resp(raw):
    return aes_ecb_dec(REAL_KEY, base64.b64decode(raw)).decode()

def fmt_time(ts):
    if not ts: return ''
    try:
        return time.strftime('%m-%d %H:%M', time.localtime(int(ts)))
    except:
        return ''

CIRCLE_RED = '\U0001f534'  # 🔴
CIRCLE_DARK = '\u25cb'  # ○
NO_SIGNAL = '\u6682\u65f6\u6ca1\u4fe1\u53f7'  # 暂时没信号

class Spider(BaseSpider):
    def getName(self): return '\u7403\u76f4\u64ad'
    def init(self, extend=''):
        self.s = requests.Session()
        self.s.headers.update({'User-Agent': UA})
        self._live_cache = None
        self._live_cache_ts = 0
        self._match_cache = None
        self._match_cache_ts = 0
    def isVideoFormat(self, url): return True
    def manualVideoCheck(self): pass
    def destroy(self): pass

    def homeContent(self, filter):
        cats = [{'type_id': '1', 'type_name': '\u8db3\u7403'}, {'type_id': '2', 'type_name': '\u7bee\u7403'}]
        data = self._get_matches()
        vids = [self._to_vod(m) for m in self._filter_by_type(data, '1')[:20]] if data else []
        return {'class': cats, 'list': vids}

    def homeVideoContent(self):
        data = self._get_matches()
        return {'list': [self._to_vod(m) for m in data[:20]] if data else []}

    def categoryContent(self, tid, pg, filter, extend):
        data = self._get_matches()
        vids = [self._to_vod(m) for m in self._filter_by_type(data, tid)] if data else []
        return {'page': int(pg), 'pagecount': 1, 'limit': len(vids), 'total': len(vids), 'list': vids}

    def detailContent(self, ids):
        vid = ids[0]
        mid = vid.split('_')[-1]
        data = self._get_matches()
        if not data: return {'list': []}
        m = next((x for x in data if str(x.get('id')) == mid), None)
        if not m: return {'list': []}
        return {'list': [self._to_vod(m, detail=True)]}

    def searchContent(self, key, quick, pg='1'):
        return {'list': [], 'page': 1}

    def playerContent(self, flag, id, vipFlags):
        parts = id.split('_')
        if len(parts) >= 3 and parts[-1].isdigit():
            match_id = parts[-2]
            url_idx = int(parts[-1])
        else:
            match_id = parts[-1]
            url_idx = 0
        live_urls = self._get_live_urls(match_id)
        if live_urls and url_idx < len(live_urls):
            return {'parse': 0, 'url': live_urls[url_idx], 'header': {'User-Agent': UA}}
        if live_urls:
            return {'parse': 0, 'url': live_urls[0], 'header': {'User-Agent': UA}}
        return {'parse': 0, 'url': f'https://m.jqpyn.com/#/player/{match_id}', 'header': {'User-Agent': UA}}

    def _get_live_urls(self, mid):
        live_map = self._get_live_map()
        return live_map.get(int(mid), {}).get('urls', [])

    def _get_live_url(self, mid):
        urls = self._get_live_urls(mid)
        return urls[0] if urls else None

    def _get_live_map(self):
        now = time.time()
        if self._live_cache and now - self._live_cache_ts < 300:
            return self._live_cache
        data = self._fetch('encryptionForyou')
        mapping = {}
        if data:
            for section in data:
                for item in section.get('list', []):
                    mid = item.get('match_id')
                    url = item.get('live_url')
                    nick = item.get('nickName', '')
                    if not mid:
                        continue
                    is_preferred = url and url.startswith('https://live2.hylivedo.com/')
                    is_valid = is_preferred or (url and url.startswith('https://bf.njscwh.com/'))
                    if not is_valid:
                        continue
                    if mid not in mapping:
                        mapping[mid] = {'urls': [], 'nicks': [], 'room_title': item.get('room_title', ''), 'short_name': item.get('short_name_zh', '')}
                    existing_urls = mapping[mid]['urls']
                    if url not in existing_urls:
                        existing_urls.append(url)
                        mapping[mid]['nicks'].append(nick)
                    if nick and len(mapping[mid]['nicks']) < len(mapping[mid]['urls']):
                        mapping[mid]['nicks'].append(nick)
        self._live_cache = mapping
        self._live_cache_ts = now
        return mapping

    def _get_matches(self):
        now = time.time()
        if self._match_cache and now - self._match_cache_ts < 60:
            return self._match_cache
        data = self._fetch('encryptionRecommMatch')
        if not data:
            time.sleep(0.2)
            data = self._fetch('encryptionRecommMatch')
        if data:
            live_map = self._get_live_map()
            match_ids = set(m.get('id') for m in data)
            for mid, info in live_map.items():
                if mid not in match_ids:
                    room_title = info.get('room_title', '')
                    if ' VS ' in room_title:
                        parts = room_title.split(' VS ')
                        home_name = parts[0]
                        away_name = parts[1] if len(parts) > 1 else ''
                    else:
                        home_name = room_title
                        away_name = ''
                    short_name = info.get('short_name', '')
                    type_id = '2' if any(x in short_name for x in ['篮', 'NBA', 'CBA', '女子篮', '男子篮']) else '1'
                    data.append({
                        'id': mid,
                        'type_id': type_id,
                        'home_name': home_name,
                        'away_name': away_name,
                        'home_scores': [0],
                        'away_scores': [0],
                        'status_id': 2,
                        'match_time': int(time.time()),
                        'competition_name': short_name or '',
                        'home_log': 'https://m.jqpyn.com/favicon.ico',
                        'away_log': 'https://m.jqpyn.com/favicon.ico',
                    })
            self._match_cache = data
            self._match_cache_ts = now
        return self._match_cache or []

    def _fetch(self, endpoint, **extra):
        ts = enc(str(int(time.time()*1000)))
        p = {
            'check_type': enc('1'), 'lang': enc('zh'), 'client_channel': enc('801'),
            'api_version': enc('1'), 'version': enc('1.2.6'), 'client': enc('h5'),
            'customer_id': enc('0'), 'uid': enc('377021891'), 'token': enc(''),
            'browser_id': enc('d6023a89-4a3e-4c8d-b1c7-3e8f5b4a2c1d'),
            'timeNowClient': ts, **{k: enc(v) for k,v in extra.items()}
        }
        try:
            r = self.s.get(f'{API}/{endpoint}', params=p, timeout=10)
            if r.status_code != 200: return None
            return json.loads(dec_resp(r.text.strip())).get('data')
        except:
            return None

    def _filter_by_type(self, data, tid):
        if not data: return []
        return [m for m in data if str(m.get('type_id')) == tid]

    def _to_vod(self, m, detail=False):
        mid = str(m.get('id'))
        home = m.get('home_name', '')
        away = m.get('away_name', '')
        hs = m.get('home_scores', [0])
        as_ = m.get('away_scores', [0])
        h_score = hs[0] if hs else 0
        a_score = as_[0] if as_ else 0
        status = m.get('status_id', 1)
        is_live = status > 1
        league = m.get('competition_name', '')
        match_time = m.get('match_time', 0)

        live_map = self._get_live_map()
        info = live_map.get(int(mid), {})
        urls = info.get('urls', [])
        nicks = info.get('nicks', [])
        has_url = len(urls) > 0
        nick = nicks[0] if nicks else info.get('nick', '')

        score_str = f'{h_score}:{a_score}'
        if nick:
            name = f'{home} {score_str} {away} [{nick}]'
        else:
            name = f'{home} {score_str} {away}'

        time_str = fmt_time(match_time)
        if is_live and has_url:
            remarks = f'{CIRCLE_RED} {time_str} {league}'
        else:
            remarks = f'{CIRCLE_DARK} {time_str} {league}'

        logo = m.get('home_log') or m.get('away_log') or 'https://m.jqpyn.com/favicon.ico'

        if has_url:
            play_parts = []
            for i, url in enumerate(urls):
                domain = 'live2' if 'live2.hylivedo.com' in url else 'bf'
                nick_i = nicks[i] if i < len(nicks) else (nick if i == 0 else '')
                label = f'{nick_i}{domain}线路{i+1}' if nick_i else f'{domain}线路{i+1}'
                play_parts.append(f'{label}$jinqiu_{mid}_{i}')
            play_url = '#'.join(play_parts)
        else:
            play_url = f'{NO_SIGNAL}$jinqiu_{mid}'

        vod = {
            'vod_id': f'jinqiu_{mid}',
            'vod_name': name,
            'vod_pic': logo,
            'vod_remarks': remarks,
            'vod_play_from': '\u7403\u76f4\u64ad',
            'vod_play_url': play_url,
        }
        if detail:
            content = f'{league} {score_str} {time_str}'
            if not has_url:
                content = NO_SIGNAL
            vod['vod_content'] = content
        return vod

try:
    from Crypto.Cipher import AES
except:
    import subprocess, sys
    subprocess.check_call([sys.executable, '-m', 'pip', 'install', 'pycryptodome', '-q'])
    from Crypto.Cipher import AES