#!/usr/bin/env python3
# 大米直播 V2.5 - 修复: 信号路数(live-scores.json实时比分+detail API信号补全)
import re, json, time, requests
from datetime import datetime, timezone, timedelta
from base.spider import Spider as BaseSpider

HOST = 'https://www.damizhibo.com'
LIST_URL = 'https://www.damizhibo.com/list.json'
LOGO = 'https://www.damizhibo.com/favicon.ico'
UA = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/140.0.0.0 Safari/537.36'

FOOTBALL_KW = ['足球','football','soccer','世界杯','world cup','中超','csl',
    '英超','premier','uefa','欧冠','欧联','europa','西甲','laliga','德甲',
    'bundesliga','意甲','serie a','法甲','ligue 1','中甲','中乙','足协杯',
    '亚冠','afc','世预赛','欧国联','日职','j league','韩k','k league',
    '澳超','a league','荷甲','葡超','俄超','冰岛超','爱超','罗甲','捷甲',
    '匈甲','中冠','哈萨甲','巴西乙','土超','比甲','丹超','挪超','瑞典超',
    '奥超','瑞士超','美甲','美乙','美女职','美青杯','联盟杯','墨联','墨西乙',
    '委内超','巴西杯','阿甲','秘鲁甲','玻利甲','菲州长杯','欧联杯','欧女杯',
    '韩女联','澳南超','澳新南联','澳维女超','韩K2联','球会友谊','白俄超',
    '东南锦','日职联','国际赛女','英联杯']

BASKETBALL_KW = ['篮球','basketball','nba','wnba','cba','nbl','欧冠篮',
    'euroleague','欧篮','g league','ncaa','pba','澳nbl','韩k2联']

HOT_KW = ['世界杯','world cup','中超','csl','wnba','nba','cba','中冠',
    '冰岛超','巴西乙','国际赛','联盟杯','欧联杯','欧足联','英联杯',
    'wnba','墨联','nbl','日职联','东南锦']


class Spider(BaseSpider):
    def getName(self):
        return "大米直播"

    def init(self, extend=""):
        self.host = HOST
        self._cache = {}
        self._CACHE_TTL = 300

    def _get_cache(self, key):
        e = self._cache.get(key)
        if e and time.time() - e['t'] < self._CACHE_TTL:
            return e['v']
        return None

    def _set_cache(self, key, val):
        self._cache[key] = {'v': val, 't': time.time()}

    def _headers(self):
        return {'User-Agent': UA, 'Referer': self.host + '/', 'Accept': '*/*'}

    def _html_headers(self):
        return {'User-Agent': UA, 'Referer': self.host + '/', 'Accept': 'text/html,application/xhtml+xml'}

    def _get_json(self, url, referer=None, timeout=15):
        try:
            hd = self._headers()
            if referer: hd['Referer'] = referer
            r = requests.get(url, headers=hd, timeout=timeout)
            return json.loads(r.text or '{}')
        except:
            return {}

    def _fmt_time(self, t):
        if not t: return ''
        try:
            t_clean = t[:16].strip()
            if len(t_clean) >= 16:
                return f'{t_clean[5:7]}-{t_clean[8:10]} {t_clean[11:16]}'
            return t_clean
        except:
            return ''

    def _get_sport_type(self, m):
        mt = m.get('match_type', '').lower()
        if mt: return mt
        league = m.get('league', '').lower()
        if self._match_type(league, BASKETBALL_KW): return 'basketball'
        if self._match_type(league, FOOTBALL_KW): return 'football'
        return 'other'

    def _match_type(self, league, kw_list):
        name = league.lower()
        return any(k in name for k in kw_list)

    def _parse_html(self, html):
        """从HTML解析: Logo映射 + 比赛卡片(比分+状态)"""
        if not html: return {}, []
        logos = {}
        for src, alt in re.findall(r'<img[^>]*src="([^"]+)"[^>]*alt="([^"]+)"[^>]*>', html):
            alt = alt.strip()
            if alt and len(alt) > 1 and 'logo' not in alt.lower():
                logos[alt] = src if src.startswith('http') else HOST + '/' + src.lstrip('/')
        cards = []
        for m in re.finditer(r'<a[^>]*class="match-card[^"]*"[^>]*>(.*?)</a>', html, re.DOTALL):
            tag_text = m.group(0)[:m.group(0).find('>') + 1]
            card = m.group(1)
            mid_m = re.search(r'data-match-id="([^"]*)"', tag_text)
            match_id = mid_m.group(1).strip() if mid_m else ''
            mt_m = re.search(r'data-match-type="([^"]*)"', tag_text)
            match_type = mt_m.group(1).strip() if mt_m else ''
            dt_m = re.search(r'data-match-time="([^"]*)"', tag_text)
            data_time = dt_m.group(1).strip() if dt_m else ''
            league_m = re.search(r'class="league-badge"[^>]*>([^<]+)', card)
            league = league_m.group(1).strip() if league_m else ''
            time_m = re.search(r'class="match-time"[^>]*>([^<]+)', card)
            time_str = time_m.group(1).strip() if time_m else ''
            status_m = re.search(r'class="match-status[^"]*">([^<]+)', card)
            status = status_m.group(1).strip() if status_m else ''
            home_m = re.search(r'team-home.*?class="team-name">([^<]+)', card, re.DOTALL)
            home = home_m.group(1).strip() if home_m else ''
            away_m = re.search(r'team-away.*?class="team-name">([^<]+)', card, re.DOTALL)
            away = away_m.group(1).strip() if away_m else ''
            score_m = re.search(r'class="score">([^<]+)', card)
            score = score_m.group(1).strip().replace(' ', '') if score_m else ''
            home_logo_m = re.search(r'team-home.*?src="([^"]+)"', card, re.DOTALL)
            away_logo_m = re.search(r'team-away.*?src="([^"]+)"', card, re.DOTALL)
            home_logo = home_logo_m.group(1) if home_logo_m else ''
            away_logo = away_logo_m.group(1) if away_logo_m else ''
            cards.append({
                'match_id': match_id, 'league': league, 'time_str': time_str, 'data_time': data_time,
                'match_type': match_type, 'status': status, 'home': home, 'away': away, 'score': score,
                'home_logo': home_logo, 'away_logo': away_logo,
            })
        return logos, cards

    def _load_all_data(self):
        cached = self._get_cache('all_data')
        if cached is not None: return cached

        list_data = self._get_json(LIST_URL)
        matches_list = list_data if isinstance(list_data, list) else (list_data.get('data') or list_data.get('list') or [])

        # nami_id -> info (精确映射)
        id_map = {}
        for m in matches_list:
            nid = str(m.get('nami_id') or m.get('id') or '')
            if nid:
                id_map[nid] = {
                    'nami_id': nid, 'home': m.get('home_team', ''), 'away': m.get('away_team', ''),
                    'league': m.get('league_name', ''), 'time': m.get('match_time', ''),
                    'signals': m.get('signals', []),
                }

        live_scores = {}
        try:
            ls_data = self._get_json(f'{HOST}/api/live-scores.json?_={int(time.time()*1000)}')
            live_scores = ls_data.get('scores', {})
        except:
            pass

        try:
            r = requests.get(HOST + '/', headers=self._html_headers(), timeout=15)
            r.encoding = r.apparent_encoding or 'utf-8'
            html = r.text
        except:
            html = ''

        logos, html_cards = self._parse_html(html)

        result = []
        matched_ids = set()
        for card in html_cards:
            mid = card['match_id']
            info = id_map.get(mid, {})
            if mid and mid not in matched_ids:
                matched_ids.add(mid)
            elif not mid:
                for nid, v in id_map.items():
                    if v['home'] == card['home'] and v['away'] == card['away'] and nid not in matched_ids:
                        info = v
                        mid = nid
                        matched_ids.add(nid)
                        break
            home_logo = card['home_logo'] or logos.get(card['home'], '') or info.get('home_logo', '')
            away_logo = card['away_logo'] or logos.get(card['away'], '') or info.get('away_logo', '')
            time_val = card['data_time'] or info.get('time', '')
            nid = info.get('nami_id', mid)
            score = card['score']
            status = card['status']
            if nid and nid in live_scores:
                ls = live_scores[nid]
                hs = ls.get('home_score', '')
                aws = ls.get('away_score', '')
                if hs != '' and aws != '': score = f'{hs}-{aws}'
                ls_status = ls.get('status', '')
                if ls_status == 'live': status = '直播中'
                elif ls_status == 'finished': status = '完场'
            result.append({
                'nami_id': nid, 'home': card['home'], 'away': card['away'],
                'league': card['league'] or info.get('league', ''),
                'time': time_val, 'match_type': card.get('match_type', ''),
                'status': status, 'score': score,
                'home_logo': home_logo, 'away_logo': away_logo,
                'signals': info.get('signals', []),
            })

        for nid, info in id_map.items():
            if nid not in matched_ids:
                score = ''
                status = 'unknown'
                if nid in live_scores:
                    ls = live_scores[nid]
                    hs = ls.get('home_score', '')
                    aws = ls.get('away_score', '')
                    if hs != '' and aws != '': score = f'{hs}-{aws}'
                    ls_status = ls.get('status', '')
                    if ls_status == 'live': status = '直播中'
                    elif ls_status == 'finished': status = '完场'
                result.append({
                    'nami_id': nid, 'home': info['home'], 'away': info['away'],
                    'league': info['league'], 'time': info['time'],
                    'match_type': '', 'status': status, 'score': score,
                    'home_logo': logos.get(info['home'], ''),
                    'away_logo': logos.get(info['away'], ''),
                    'signals': info['signals'],
                })

        self._set_cache('all_data', result)
        return result

    def _fetch_detail_signals(self, nid):
        try:
            data = self._get_json(f'{HOST}/api/live/{nid}.json', referer=f'{HOST}/live/{nid}.html')
            sigs = data.get('signals', [])
            if sigs:
                labels = set()
                for s in sigs:
                    label = s.get('label', '')
                    if label in ('高清K', '高清J', '高清B'):
                        labels.add(label)
                return sigs
        except:
            pass
        return None

    def _build_name(self, home, away, score):
        if score and score != '-':
            return f'{home} {score} {away}'
        return f'{home} vs {away}'

    def _build_remarks(self, m):
        is_live = m.get('status') == '直播中'
        tag = '\U0001f534' if is_live else ''
        dt = self._fmt_time(m.get('time', ''))
        league = m.get('league', '')
        sig_count = len(m.get('signals', []))
        parts = []
        if tag: parts.append(tag)
        if dt: parts.append(dt)
        if league: parts.append(league)
        if sig_count >= 2: parts.append(f'{sig_count}路')
        return ' '.join(parts) or '直播'

    def _get_classes(self):
        return [
            {'type_id': 'all', 'type_name': '全部'},
            {'type_id': 'hot', 'type_name': '🔥 热门'},
            {'type_id': 'football', 'type_name': '⚽ 足球'},
            {'type_id': 'basketball', 'type_name': '🏀 篮球'},
        ]

    def homeContent(self, filter):
        return {'class': self._get_classes(), 'filters': {}}

    def categoryContent(self, tid, pg, filter, extend):
        try:
            tid = (extend or {}).get('cateId') or tid or 'all'
            pg = int(pg or 1)
            all_data = self._load_all_data()
            list_items = []
            for m in all_data:
                league = m.get('league', '')
                sport = self._get_sport_type(m)
                if tid == 'hot' and not self._match_type(league, HOT_KW): continue
                if tid == 'football' and sport != 'football': continue
                if tid == 'basketball' and sport != 'basketball': continue
                nid = m.get('nami_id', '')
                vod_id = f'dmz|{nid}' if nid else f'dmz|{m["home"]}_{m["away"]}'
                pic = m.get('home_logo', '') or m.get('away_logo', '') or LOGO
                list_items.append({
                    'vod_id': vod_id,
                    'vod_name': self._build_name(m['home'], m['away'], m.get('score', '')),
                    'vod_pic': pic,
                    'vod_remarks': self._build_remarks(m),
                    'type_name': league or '全部',
                })
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
            parts = vid.split('|')
            nid = parts[1] if len(parts) > 1 else parts[0]
            all_data = self._load_all_data()
            target = None
            for m in all_data:
                if m.get('nami_id') == nid or f'{m["home"]}_{m["away"]}' == nid:
                    target = m
                    break
            if not target: return {'list': []}
            home = target['home']
            away = target['away']
            league = target.get('league', '')
            signals = target.get('signals', [])
            if nid and len(signals) < 3:
                detail_sigs = self._fetch_detail_signals(nid)
                if detail_sigs and len(detail_sigs) > len(signals):
                    signals = detail_sigs
            play_urls = []
            for sig in signals:
                label = sig.get('label') or sig.get('name') or sig.get('title') or ''
                url = sig.get('url') or sig.get('link') or sig.get('src') or ''
                if url: play_urls.append(f'{label}${url}')
            if not play_urls:
                play_urls.append(f'暂无信号${HOST}')
            pic = target.get('home_logo', '') or target.get('away_logo', '') or LOGO
            return {'list': [{
                'vod_id': vid,
                'vod_name': self._build_name(home, away, target.get('score', '')),
                'vod_pic': pic,
                'vod_remarks': self._build_remarks({**target, 'signals': signals}),
                'vod_play_from': '大米直播',
                'vod_play_url': '#'.join(play_urls),
                'vod_content': (league or '体育直播') + '\n' + self._build_name(home, away, ''),
            }]}
        except:
            return {'list': []}

    def searchContent(self, kw, quick, pg):
        try:
            keyword = (kw or '').strip().lower()
            if not keyword:
                return {'page': 1, 'pagecount': 1, 'limit': 20, 'total': 0, 'list': []}
            all_data = self._load_all_data()
            list_items = []
            for m in all_data:
                if keyword in (m['home'] + ' ' + m['away'] + ' ' + m.get('league', '')).lower():
                    nid = m.get('nami_id', '')
                    pic = m.get('home_logo', '') or m.get('away_logo', '') or LOGO
                    list_items.append({
                        'vod_id': f'dmz|{nid}' if nid else f'dmz|{m["home"]}_{m["away"]}',
                        'vod_name': self._build_name(m['home'], m['away'], m.get('score', '')),
                        'vod_pic': pic,
                        'vod_remarks': self._build_remarks(m),
                    })
            return {
                'page': pg or 1, 'pagecount': 1, 'limit': len(list_items),
                'total': len(list_items), 'list': list_items
            }
        except:
            return {'page': 1, 'pagecount': 1, 'limit': 20, 'total': 0, 'list': []}

    def playerContent(self, flag, id, vipFlags):
        try:
            url = str(id or '')
            return {'parse': 0, 'url': url, 'header': {
                'User-Agent': UA, 'Referer': HOST + '/', 'Origin': HOST
            }}
        except:
            return {'parse': 0, 'url': str(id or '')}

    def localProxy(self, param):
        return [200, "text/plain", b"", {}]