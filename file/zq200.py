#!/usr/bin/python
# -*- coding: utf-8 -*-
# Version: V14 - 修复队徽路径 足球前缀改回 football/team (v13 误用 team/ 致404)
# 适用于TVBox/T4/海阔，无外部依赖
import json, time
from urllib.request import urlopen, Request

try:
    from base.spider import Spider
except ImportError:
    class Spider:
        def getName(self): return ""
        def init(self, extend=""): pass

class Spider(Spider):
    def getName(self): return "zuqiu200直播"

    def init(self, extend=""):
        self.host = "https://zuqiu200.app"
        self.api_host = "https://enskweeseey8kp2frvb06.k8v4dh4.app"
        self.headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36", "Referer": self.host + "/", "Origin": self.host}
        self.categories = [
            {"type_id": "1", "type_name": "足球"},
            {"type_id": "2", "type_name": "篮球"},
            {"type_id": "3", "type_name": "网球"},
            {"type_id": "4", "type_name": "排球"},
            {"type_id": "all", "type_name": "全部"}
        ]
        self.cache = {}

    def _api_get(self, path):
        url = self.api_host + path
        try:
            req = Request(url, headers=self.headers)
            with urlopen(req, timeout=15) as resp:
                if resp.getcode() == 200:
                    return json.loads(resp.read().decode())
        except Exception:
            pass
        return None

    def _date_str(self, offset):
        t = time.time() + offset * 86400
        return time.strftime("%Y-%m-%d", time.localtime(t))

    def _fetch_records(self, ds):
        if ds in self.cache:
            return self.cache[ds]
        data = self._api_get(f"/api/c7/business/match/list?lang=zh&date={ds}")
        records = []
        if data and data.get("success") and isinstance(data.get("data"), dict):
            records = data["data"].get("records", []) or []
        self.cache[ds] = records
        return records

    def _get_records(self):
        for off in (0, 1, -1):
            records = self._fetch_records(self._date_str(off))
            if records:
                return records
        return []

    def _get_logo_url(self, sport_id, logo):
        if not logo:
            return ""
        if logo.startswith("http"):
            return logo
        if "/" in logo:
            return f"https://img0.aiscore.com/{logo}"
        prefix = {1: "football/team/", 2: "basketball/team/", 3: "v2/team/", 4: "volleyball/team/", 5: "v2/team/"}
        return f"https://img0.aiscore.com/{prefix.get(sport_id, 'football/team/')}{logo}"

    def _fmt_time(self, ts_sec):
        if not ts_sec:
            return ""
        return time.strftime("%m-%d %H:%M", time.localtime(ts_sec))

    def _fmt_score(self, m):
        if m.get("sportId") == 5:
            innings = (m.get("ckScores") or {}).get("innings") or []
            p1 = f"{innings[0].get('runs')}/{innings[0].get('wickets')}" if len(innings) >= 1 and innings[0] else ""
            p2 = f"{innings[1].get('runs')}/{innings[1].get('wickets')}" if len(innings) >= 2 and innings[1] else ""
            return " ".join(x for x in (p1, p2) if x)
        h, a = m.get("homeScores") or [], m.get("awayScores") or []
        if not h and not a:
            return ""
        return f"{h[-1] if h else 0}-{a[-1] if a else 0}"

    def _extract_url(self, m):
        vu = m.get("videoUrl") or ""
        if vu.startswith("http"):
            return vu
        anchors = m.get("anchorAppointmentVoList") or []
        for a in anchors:
            s1, s2 = a.get("playStreamAddress") or "", a.get("playStreamAddress2") or ""
            if ".m3u8" in s1:
                return s1
            if ".m3u8" in s2:
                return s2
        for a in anchors:
            s1, s2 = a.get("playStreamAddress") or "", a.get("playStreamAddress2") or ""
            if s1.startswith("http"):
                return s1
            if s2.startswith("http"):
                return s2
        return ""

    def _get_livestreams(self):
        records = self._get_records()
        now = int(time.time())
        result = []
        seen = set()
        for m in records:
            home = (m.get("homeTeam") or {}).get("teamName") or ""
            away = (m.get("awayTeam") or {}).get("teamName") or ""
            if not home or not away:
                continue
            league = (m.get("competition") or {}).get("competitionName") or ""
            match_id = m.get("matchId") or ""
            mt = m.get("matchTime") or 0
            url = self._extract_url(m)
            is_live = bool(url)
            is_soon = (not url) and abs(mt - now) <= 1800
            if not is_live and not is_soon:
                continue
            time_str = self._fmt_time(mt)
            score = self._fmt_score(m)
            prefix = "🔴 " if is_live else "⏳ "
            parts = [prefix]
            parts.extend(x for x in (time_str, league, score) if x)
            key = match_id or (home + away + league)
            if key in seen:
                continue
            seen.add(key)
            result.append({
                "vod_id": match_id,
                "vod_name": f"{home} vs {away}",
                "vod_pic": self._get_logo_url(m.get("sportId"), (m.get("homeTeam") or {}).get("logo") or ""),
                "vod_play_from": league or "直播",
                "vod_play_url": url or "",
                "vod_remarks": " ".join(parts),
                "sport_id": str(m.get("sportId") or ""),
                "_mt": mt,
                "_live": 1 if is_live else 0
            })
        result.sort(key=lambda x: (-x["_live"], x["_mt"]))
        return result

    def homeVideoContent(self, extend=""):
        return self.homeContent(extend)

    def homeContent(self, extend=""):
        classes = [{"type_id": c["type_id"], "type_name": c["type_name"], "type_extend": "", "type_url": ""} for c in self.categories]
        try:
            return {"class": classes, "list": self._get_livestreams(), "filter": {}}
        except Exception:
            return {"class": classes, "list": [], "filter": {}}

    def categoryContent(self, tid, pg, filterable, extend):
        try:
            videos = self._get_livestreams()
            filtered = videos if tid == "all" else [v for v in videos if v.get("sport_id") == str(tid)]
            total = len(filtered)
            page_size = 20
            start = (int(pg) - 1) * page_size
            page_videos = filtered[start:start + page_size]
            return {"list": page_videos, "page": pg, "pagecount": (total + page_size - 1) // page_size or 1, "limit": page_size, "total": total}
        except Exception:
            return {"list": [], "page": pg, "pagecount": 1, "limit": 20, "total": 0}

    def detailContent(self, ids):
        try:
            target = str(ids[0]) if isinstance(ids, (list, tuple)) and ids else str(ids)
            for v in self._get_livestreams():
                if v["vod_id"] == target:
                    return {"list": [v]}
            return {"list": []}
        except Exception:
            return {"list": []}

    def searchContent(self, keyword, quick, pg):
        try:
            keyword_lower = (keyword or "").lower()
            results = [v for v in self._get_livestreams() if keyword_lower in v["vod_name"].lower() or (keyword or "") in v["vod_play_from"]]
            total = len(results)
            page_size = 20
            start = (int(pg) - 1) * page_size
            page_results = results[start:start + page_size]
            return {"list": page_results, "page": pg, "pagecount": (total + page_size - 1) // page_size or 1, "limit": page_size, "total": total}
        except Exception:
            return {"list": [], "page": pg, "pagecount": 1, "limit": 20, "total": 0}

    def playerContent(self, flag, id, vipFlags):
        url = str(id or "")
        if url:
            try:
                fresh = self._extract_url(next((m for m in self._get_records() if m.get("matchId") == url), {}))
                if fresh:
                    url = fresh
            except Exception:
                pass
        return {"parse": 0, "url": url, "header": {"User-Agent": self.headers["User-Agent"], "Referer": self.host + "/"}}