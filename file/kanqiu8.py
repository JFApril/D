#!/usr/bin/env python3
# 看球8直播爬虫 V2.2 - 修复预告比赛日期时间缺失，比赛开赛时间（北京时间）与主播开播时间双重兼容
import json, re, time, requests
from datetime import datetime, timezone, timedelta
from urllib.parse import quote
from base.spider import Spider as BaseSpider

API_HOST = "https://zhiboapi1001.bszb.me"
WEB_HOST = "https://kanqiu8svip-cctv.123kq.live"
UA = "Mozilla/5.0 (Linux; Android 10; K) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Mobile Safari/537.36"
TZ_BJ = timezone(timedelta(hours=8))

class Spider(BaseSpider):
    def getName(self):
        return "看球8"

    def init(self, extend=""):
        self.api_host = API_HOST
        self.web_host = WEB_HOST
        self.headers = {
            "User-Agent": UA,
            "Referer": self.web_host + "/",
            "Origin": self.web_host,
            "Accept": "application/json, text/plain, */*",
            "Accept-Language": "zh-CN,zh;q=0.9",
        }

    def _get(self, path, params=None):
        try:
            url = f"{self.api_host}{path}" if path.startswith("/") else f"{self.api_host}/{path}"
            r = requests.get(url, headers=self.headers, params=params, timeout=8, verify=False)
            if r.status_code == 200:
                d = r.json()
                return d.get("data") if d.get("status") in [0, 200, "0", "200"] or d.get("code") == 0 else d
        except Exception:
            pass
        return None

    def _format_score(self, sc):
        if sc is None:
            return None
        if isinstance(sc, (int, float)):
            return int(sc)
        if isinstance(sc, list):
            return sum(int(x) for x in sc if str(x).isdigit())
        if isinstance(sc, str):
            s = sc.strip()
            if s.startswith("[") and s.endswith("]"):
                try:
                    arr = json.loads(s)
                    if isinstance(arr, list):
                        return sum(int(x) for x in arr if str(x).isdigit())
                except Exception:
                    pass
            if s.isdigit():
                return int(s)
        return sc

    def _format_match_time(self, item, match_info):
        m_time = match_info.get("time") or match_info.get("match_time") or item.get("match_time")
        if m_time and str(m_time).isdigit():
            ts = int(m_time)
            if ts > 0:
                dt = datetime.fromtimestamp(ts, TZ_BJ)
                return dt.strftime("%H:%M")

        st = item.get("start_time") or match_info.get("start_time") or ""
        if isinstance(st, str) and len(st) >= 16:
            return st[11:16]

        st_stamp = item.get("start_stamp") or 0
        if str(st_stamp).isdigit() and int(st_stamp) > 0:
            dt = datetime.fromtimestamp(int(st_stamp), TZ_BJ)
            return dt.strftime("%H:%M")

        return ""

    def _parse_live_item(self, item):
        if not isinstance(item, dict):
            return None
        lid = item.get("liveid") or item.get("id") or (item.get("match") or {}).get("id")
        if not lid:
            return None
        raw_title = item.get("title") or item.get("match_title") or ""
        anchor = item.get("anchor") if isinstance(item.get("anchor"), dict) else {}
        anchor_name = anchor.get("nick_name") or item.get("anchor_name") or ""
        match_info = item.get("match") if isinstance(item.get("match"), dict) else {}

        ht_obj = match_info.get("hometeam") if isinstance(match_info.get("hometeam"), dict) else {}
        at_obj = match_info.get("awayteam") if isinstance(match_info.get("awayteam"), dict) else {}
        home = item.get("hometeam_name") or ht_obj.get("name_zh") or ht_obj.get("short_name_zh") or match_info.get("hometeam") or item.get("hometeam") or ""
        away = item.get("awayteam_name") or at_obj.get("name_zh") or at_obj.get("short_name_zh") or match_info.get("awayteam") or item.get("awayteam") or ""

        if (not home or not away) and raw_title and " VS " in raw_title:
            parts = raw_title.split(" VS ")
            if not home:
                home = parts[0].strip()
            if not away and len(parts) > 1:
                away = parts[1].strip()

        hs_raw = item.get("home_score") if item.get("home_score") is not None else match_info.get("home_score")
        as_raw = item.get("away_score") if item.get("away_score") is not None else match_info.get("away_score")
        hs = self._format_score(hs_raw)
        as_ = self._format_score(as_raw)

        m_status = item.get("match_status") or match_info.get("match_status") or match_info.get("status")
        is_live = item.get("is_live") == 1 or item.get("status") == 1 or m_status in [2, 3, 4, 5, 7, 8]

        if home and away:
            if is_live and hs is not None and as_ is not None:
                title = f"{home} {hs}:{as_} {away}"
            else:
                title = f"{home} VS {away}"
        elif raw_title:
            title = raw_title
        else:
            title = anchor_name or f"直播间 {lid}"

        me_obj = match_info.get("matchevent") if isinstance(match_info.get("matchevent"), dict) else {}
        badge = item.get("badge_text") or me_obj.get("short_name_zh") or me_obj.get("name_zh") or match_info.get("eventname") or ""
        
        time_str = self._format_match_time(item, match_info)
        status_txt = "🔴 直播中" if is_live else "📅 预告"
        remarks_parts = [p for p in [status_txt, time_str, badge, anchor_name] if p]
        remarks = " | ".join(remarks_parts) if remarks_parts else "看球8直播"
        pic = item.get("thumb") or item.get("cover") or ht_obj.get("logo") or anchor.get("avatar") or ""
        return {
            "vod_id": str(lid),
            "vod_name": title,
            "vod_pic": pic,
            "vod_remarks": remarks,
        }

    def homeContent(self, filter):
        classes = [
            {"type_id": "all", "type_name": "全部"},
            {"type_id": "football", "type_name": "⚽ 足球"},
            {"type_id": "basketball", "type_name": "🏀 篮球"},
            {"type_id": "esports", "type_name": "🎮 电竞"},
            {"type_id": "general", "type_name": "🏆 综合"},
        ]
        list_data = self._get("/api/home/getHomeLiveListsCdn", {"type": "all", "page": 1})
        lives = []
        if isinstance(list_data, dict):
            raw_lives = list_data.get("lives") or []
            lives = [self._parse_live_item(i) for i in raw_lives if self._parse_live_item(i)]
        if not lives:
            data = self._get("/api/home/getHomeDataCdn")
            if isinstance(data, dict):
                raw_lives = data.get("lives") or data.get("hot") or []
                lives = [self._parse_live_item(i) for i in raw_lives if self._parse_live_item(i)]
        return {"class": classes, "list": lives, "filters": {}}

    def categoryContent(self, tid, pg, filter, extend):
        page = int(pg) if str(pg).isdigit() else 1
        t_str = str((extend or {}).get("cateId") or tid or "all")
        type_map = {"0": "all", "1": "football", "2": "basketball", "3": "esports", "9": "general"}
        type_val = type_map.get(t_str, t_str)
        data = self._get("/api/home/getHomeLiveListsCdn", {"type": type_val, "page": page})
        result_list = []
        total = 0
        limit = 20
        if isinstance(data, dict):
            raw_lives = data.get("lives") or []
            result_list = [self._parse_live_item(i) for i in raw_lives if self._parse_live_item(i)]
            total = int(data.get("total") or len(result_list))
            limit = int(data.get("size") or 20)
        return {
            "page": page,
            "pagecount": (total + limit - 1) // limit if limit > 0 else 1,
            "limit": limit,
            "total": total,
            "list": result_list,
        }

    def detailContent(self, ids):
        lid = ids[0] if isinstance(ids, list) and ids else str(ids)
        data = self._get("/api/live/getLiveInfo", {"liveid": lid})
        if not isinstance(data, dict):
            return {"list": []}
        live = data.get("live") if isinstance(data.get("live"), dict) else {}
        title = live.get("title") or "看球8直播"
        pic = live.get("thumb") or ""
        badge = live.get("badge_text") or ""
        anchor_name = (live.get("anchor") or {}).get("nick_name") or ""
        play_from_list = []
        play_url_list = []
        videos = data.get("videos")
        if isinstance(videos, list) and videos:
            v_urls = []
            for v in videos:
                if not isinstance(v, dict):
                    continue
                v_name = v.get("type_name_txt") or v.get("type_name") or "官方信号"
                v_url = v.get("url") or ""
                if v_url:
                    v_urls.append(f"{v_name}${v_url}")
            if v_urls:
                play_from_list.append("官方原画")
                play_url_list.append("#".join(v_urls))
        anchors = data.get("anchors")
        if isinstance(anchors, list) and anchors:
            a_urls = []
            for a in anchors:
                if not isinstance(a, dict):
                    continue
                a_nick = a.get("nick_name") or "主播"
                a_live = a.get("live") if isinstance(a.get("live"), dict) else {}
                a_pull = a_live.get("pull_url") or ""
                if a_pull:
                    a_urls.append(f"{a_nick}${a_pull}")
            if a_urls:
                play_from_list.append("主播解说")
                play_url_list.append("#".join(a_urls))
        cur_pull = live.get("pull_url") or ""
        if cur_pull and not any(cur_pull in u for u in play_url_list):
            play_from_list.append("当前主播")
            play_url_list.append(f"{anchor_name or '直播信号'}${cur_pull}")
        if not play_url_list:
            play_from_list.append("看球8")
            play_url_list.append(f"直播线路${cur_pull or self.web_host}")
        vod = {
            "vod_id": str(lid),
            "vod_name": title,
            "vod_pic": pic,
            "vod_remarks": f"{badge} {anchor_name}".strip(),
            "vod_content": f"开播时间: {live.get('start_time', '')} | 赛事: {badge}",
            "vod_play_from": "$$$".join(play_from_list),
            "vod_play_url": "$$$".join(play_url_list),
        }
        return {"list": [vod]}

    def searchContent(self, key, quick, pg="1"):
        kw = (key or "").strip().lower()
        if not kw:
            return {"list": [], "page": 1}
        page = int(pg) if str(pg).isdigit() else 1
        data = self._get("/api/home/getHomeLiveListsCdn", {"type": "all", "page": page})
        matches = []
        if isinstance(data, dict):
            raw_lives = data.get("lives") or []
            for item in raw_lives:
                parsed = self._parse_live_item(item)
                if not parsed:
                    continue
                title = parsed.get("vod_name", "").lower()
                remarks = parsed.get("vod_remarks", "").lower()
                if kw in title or kw in remarks:
                    matches.append(parsed)
        return {"list": matches, "page": page}

    def playerContent(self, flag, id, vipFlags):
        url = (id or "").strip()
        header = json.dumps({
            "User-Agent": UA,
            "Referer": self.web_host + "/",
            "Origin": self.web_host,
        })
        if re.search(r"\.(m3u8|flv|mp4)(\?|$)", url, re.I) or url.startswith("http://") or url.startswith("https://"):
            return {"parse": 0, "url": url, "header": header}
        return {"parse": 1, "url": url, "header": header}

    def localProxy(self, param):
        return [200, "text/plain", b"", {}]