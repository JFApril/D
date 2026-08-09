#!/usr/bin/python
# -*- coding: utf-8 -*-
# V1.17 球布斯体育直播 - 去重+vivo200代理
import re, json, requests, time  #, os
from base.spider import Spider as BaseSpider
# LOG_DIR = "/storage/emulated/0/Download/Operit/cleanOnExit"
# LOG_FILE = os.path.join(LOG_DIR, "qbs_v1.17.log")
def _log(msg):
    pass
    # line = "[QBS V1.17 " + time.strftime("%H:%M:%S") + "] " + msg
    # print(line)
    # try:
    #     os.makedirs(LOG_DIR, exist_ok=True)
    #     with open(LOG_FILE, "a", encoding="utf-8") as f:
    #         f.write(line + "\n")
    # except Exception:
    #     pass
def _safe_pic(pic):
    p = pic or ""
    if not p or p.startswith("/") or not p.startswith("http"):
        return ""
    return p
def _fmt_time(ts):
    try:
        t = int(ts)
        return time.strftime("%m/%d %H:%M", time.localtime(t)) if t >= 1000000000 else ""
    except Exception:
        return ""
HOST = "https://www.jsnxka5nln.com"
API = "https://qiubusi.it"
SITE_CODE = "S0001"
UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/140.0.0.0 Safari/537.36"
PLAY_HEADER = json.dumps({"User-Agent": UA, "Referer": HOST + "/", "Origin": HOST})
CAT_KW1 = ["足球", "英超", "西甲", "意甲", "德甲", "法甲", "中超", "欧冠", "欧联", "挪超", "瑞超", "芬超", "比甲", "荷甲", "葡超", "澳超", "日职", "韩K", "巴甲", "南美杯", "联赛", "杯赛", "友谊赛", "英联杯"]
CAT_KW2 = ["篮球", "NBA", "nba", "CBA", "cba", "女篮", "男篮", "WNBA"]
VIVO_HOST = "live.vivo200.com"
PROXY_PREFIX = "/live-stream-proxy"
class Spider(BaseSpider):
    def getName(self):
        return "球布斯体育"
    def init(self, extend=""):
        self._guest_token = None
        self._guest_expires = 0
        self._rooms_cache = []
        self._rooms_cache_ts = 0
        self._s2r = {}
        self._r2room = {}
    def _get_rooms(self, force=False):
        now = time.time()
        if not force and self._rooms_cache and (now - self._rooms_cache_ts < 60):
            return self._rooms_cache
        seen = set()
        rooms = []
        for st in [1, 2]:
            d = self._api("/v1/live/recommend", {"sport_type": st})
            if d and d.get("code") == 0:
                lst = d.get("data", {}).get("list") or []
                if isinstance(lst, list):
                    for r in lst:
                        rid = str(r.get("room_id", ""))
                        if rid and rid not in seen:
                            seen.add(rid)
                            rooms.append(r)
                    _log("sport=" + str(st) + " got " + str(len(lst)))
        self._rooms_cache = rooms
        self._rooms_cache_ts = now
        self._s2r = {}
        self._r2room = {}
        for r in rooms:
            rid = str(r.get("room_id", ""))
            su = r.get("stream_url", "") or ""
            if su:
                self._s2r[su.split("?")[0]] = rid
            if rid:
                self._r2room[rid] = r
        _log("total: " + str(len(rooms)))
        return rooms
    def _ensure_guest(self):
        now = time.time()
        if self._guest_token and now < self._guest_expires:
            return self._guest_token
        try:
            h = {"Content-Type": "application/json", "Site-Code": SITE_CODE, "Sport-Data": "1", "OperationID": str(int(now * 1000))}
            r = requests.post(API + "/v1/guest/login", json={"platform": 5}, headers=h, timeout=10)
            d = r.json()
            if d.get("code") == 0 and d.get("data"):
                self._guest_token = d["data"]["req_token"]
                self._guest_expires = now + 3500
                _log("token ok")
                return self._guest_token
            _log("login " + str(d.get("code")) + " " + str(d.get("message", ""))[:30])
        except Exception as e:
            _log("login err:" + str(e)[:40])
        return None
    def _api(self, path, body=None):
        token = self._ensure_guest()
        if not token:
            return None
        h = {"Content-Type": "application/json", "Site-Code": SITE_CODE, "Sport-Data": "1", "OperationID": str(int(time.time() * 1000)), "Token": token}
        try:
            r = requests.post(API + path, json=body or {}, headers=h, timeout=10)
            d = r.json()
            if d.get("code") == 401:
                self._guest_token = None
                t2 = self._ensure_guest()
                if t2:
                    h["Token"] = t2
                    return requests.post(API + path, json=body or {}, headers=h, timeout=10).json()
            return d
        except Exception as e:
            _log("api err:" + str(e)[:40])
            return None
    def _proxy_url(self, url):
        if VIVO_HOST in url:
            from urllib.parse import urlparse
            p = urlparse(url)
            new = API + PROXY_PREFIX + p.path + "?" + p.query
            _log("proxy: " + new[:80])
            return new
        return url
    def _build_vod(self, r):
        rid = str(r.get("room_id", ""))
        stream = r.get("stream_url", "") or ""
        hot = r.get("hot_value", 0) or 0
        m = r.get("match") or {}
        if isinstance(m, dict) and m:
            home = m.get("home_team", "")
            away = m.get("away_team", "")
            league = m.get("league_name", "")
            mt = m.get("match_time", "")
            home_logo = m.get("home_logo", "")
            away_logo = m.get("away_logo", "")
            name = (home + " VS " + away) if (home and away) else r.get("title", "")
            ts = _fmt_time(mt)
        else:
            name = r.get("title", "")
            league = home_logo = away_logo = ts = ""
        anchor = r.get("anchor", {})
        aname = anchor.get("nickname", "") if isinstance(anchor, dict) else ""
        pic = _safe_pic(home_logo) or _safe_pic(away_logo) or _safe_pic(r.get("cover", ""))
        if name and aname:
            name += " [" + aname + "]"
        parts = ["🔴"]
        if ts: parts.append(ts)
        if league: parts.append(league)
        return {"vod_id": rid, "vod_name": name, "vod_pic": pic, "vod_remarks": " ".join(parts),
                "vod_play_from": "球布斯", "vod_play_url": name + "$" + stream if stream else "", "_hot": int(hot)}
    def homeContent(self, ext=False):
        _log("homeContent")
        return {"class": [{"type_id": 0, "type_name": "全部直播"}, {"type_id": 1, "type_name": "足球"}, {"type_id": 2, "type_name": "篮球"}], "filters": {}, "list": []}
    def categoryContent(self, tid, pg, ext={}, extend=""):
        tid_int = int(tid) if str(tid).isdigit() else 0
        page = int(pg) if str(pg).isdigit() else 1
        rooms = self._get_rooms()
        items = []
        for r in rooms:
            if not r.get("stream_url") or r.get("status", 0) != 1:
                continue
            m = r.get("match") or {}
            sport = m.get("sport_type", 0) if isinstance(m, dict) else 0
            if tid_int == 1 and sport == 2:
                continue
            if tid_int == 2 and sport == 1:
                continue
            items.append(self._build_vod(r))
        items.sort(key=lambda x: x.get("_hot", 0), reverse=True)
        _log("items=" + str(len(items)))
        return {"page": page, "pagecount": 1, "limit": 200, "total": len(items), "list": items}
    def detailContent(self, ids):
        rid = str(ids[0]) if ids else ""
        _log("detail rid=" + rid)
        if not rid:
            return {"list": []}
        rooms = self._get_rooms()
        target = None
        for r in rooms:
            if str(r.get("room_id")) == rid:
                target = r
                break
        if not target:
            _log("NOT FOUND")
            return {"list": []}
        vod = self._build_vod(target)
        stream = target.get("stream_url", "") or ""
        m = target.get("match") or {}
        league = m.get("league_name", "") if isinstance(m, dict) else ""
        anchor = target.get("anchor", {})
        aname = anchor.get("nickname", "") if isinstance(anchor, dict) else ""
        hot = target.get("hot_value", 0) or 0
        vod["vod_content"] = ("联赛: " + league + "<br>" if league else "") + "主播: " + aname + "<br>热度: " + str(hot) + "<br>状态: 直播中"
        vod["vod_play_url"] = ("高清直播$" + stream) if stream else ""
        return {"list": [vod]}
    def searchContent(self, wd, quick, pg):
        page = int(pg) if str(pg).isdigit() else 1
        rooms = self._get_rooms()
        wd_l = wd.lower()
        items = []
        for r in rooms:
            if not r.get("stream_url") or r.get("status", 0) != 1:
                continue
            m = r.get("match") or {}
            home = m.get("home_team", "") if isinstance(m, dict) else ""
            away = m.get("away_team", "") if isinstance(m, dict) else ""
            league = m.get("league_name", "") if isinstance(m, dict) else ""
            title = r.get("title", "")
            if wd_l not in (home + away + league + title).lower():
                continue
            items.append(self._build_vod(r))
        start = (page - 1) * 200
        return {"page": page, "pagecount": 1, "limit": 200, "total": len(items), "list": items[start:start + 200]}
    def playerContent(self, flag, id, vipFlags):
        url = str(id or "")
        _log("play url=" + url[:80])
        if not url:
            return {"parse": 0, "url": url, "header": PLAY_HEADER}
        if VIVO_HOST in url:
            self._get_rooms(force=True)
            base = url.split("?")[0]
            room_id = self._s2r.get(base)
            new_url = url
            if room_id:
                new_room = self._r2room.get(room_id)
                if new_room:
                    new_url = new_room.get("stream_url", "") or url
            return {"parse": 0, "url": self._proxy_url(new_url), "header": PLAY_HEADER}
        return {"parse": 0, "url": url, "header": PLAY_HEADER}
    def localProxy(self, param):
        return [200, "text/plain", b"", {}]