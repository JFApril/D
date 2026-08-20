#!/usr/bin/env python3
# 绿茵直播 (9939) V1.3 - 修复开赛时间映射方向(matchLivestreams.reservedAnchors.houseId→matchTime)，remarks直播中后标开赛日期时间（直出原生可播直链parse=0）
import sys, re, json, time, requests
from datetime import datetime, timezone, timedelta

try:
    from base.spider import Spider as BaseSpider
except ImportError:
    class BaseSpider:
        def __init__(self): pass

TZ_BJ = timezone(timedelta(hours=8))
WEB_HOST = "https://9939vip79.app"
HEADERS = {
    "User-Agent": "Mozilla/5.0 (iPhone; CPU iPhone OS 16_6 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/16.6 Mobile/15E148 Safari/604.1",
    "Origin": WEB_HOST,
    "Referer": WEB_HOST + "/"
}
FALLBACK_API = "https://lzfs5tah9amkatbu4tb07.k8v4dh4.app"

CATEGORY_MAP = {
    "0": "全部",
    "1": "⚽ 足球",
    "2": "🏀 篮球",
    "12": "🎮 电竞",
    "3": "🎾 网球",
    "13": "📊 赛事分析"
}

class Spider(BaseSpider):
    def getName(self):
        return "绿茵直播"

    def init(self, extend=""):
        self.api_base = self._get_api_base()

    def _get_api_base(self):
        try:
            r = requests.get(WEB_HOST + "/config.json", headers=HEADERS, timeout=10, verify=False)
            cfg = r.json()
            ep = (cfg.get("api-endpoint") or "").strip().rstrip("/")
            if ep:
                return ep
        except Exception:
            pass
        return FALLBACK_API

    def _fetch_index(self):
        url = self.api_base + "/api/c5/business/livehouse/index"
        try:
            r = requests.get(url, headers=HEADERS, timeout=10, verify=False)
            data = (r.json() or {}).get("data") or {}
        except Exception:
            data = {}
        mt_map = {}
        for it in (data.get("matchLivestreams") or []):
            if not isinstance(it, dict):
                continue
            mt = it.get("matchTime")
            if not mt:
                continue
            for ra in (it.get("reservedAnchors") or []):
                if isinstance(ra, dict) and ra.get("houseId"):
                    mt_map[str(ra.get("houseId"))] = mt
        return data, mt_map

    def _all_items(self, data):
        items = []
        seen = set()
        for key in ["ongoingLivestreams", "matchLivestreams", "anchorLivestreams", "streamingAnchorRanking"]:
            for it in (data.get(key) or []):
                if not isinstance(it, dict):
                    continue
                hid = str(it.get("houseId", ""))
                if not hid or hid in seen:
                    continue
                seen.add(hid)
                items.append(it)
        return items

    def _is_playable(self, it):
        addr = it.get("playStreamAddress") or ""
        return it.get("liveStatus") == 2 and len(addr) > 0 and not addr.rstrip("/").endswith("/live")

    def _match_time_str(self, it, mt_map):
        ts = it.get("matchTime") or mt_map.get(str(it.get("houseId", "")))
        if not ts or int(ts) <= 0:
            return ""
        try:
            return datetime.fromtimestamp(int(ts), TZ_BJ).strftime("%m-%d %H:%M")
        except Exception:
            return ""

    def homeContent(self, filter):
        classes = [{"type_name": v, "type_id": k} for k, v in CATEGORY_MAP.items()]
        res = self.categoryContent("0", "1", filter, {})
        return {"class": classes, "list": res.get("list", []), "filters": {}}

    def homeVideoContent(self):
        return self.categoryContent("0", "1", False, {})

    def categoryContent(self, tid, pg, filter, extend):
        try:
            page = int(pg)
        except Exception:
            page = 1
        data, mt_map = self._fetch_index()
        items = self._all_items(data)
        if tid and tid != "0":
            items = [it for it in items if str(it.get("anchorType", "")) == str(tid) or str(it.get("raceTypeId", "")) == str(tid)]
        items.sort(key=lambda x: 0 if self._is_playable(x) else 1)
        vod_list = []
        for it in items:
            hid = str(it.get("houseId", ""))
            name = it.get("houseName") or it.get("houseNameEn") or it.get("nickName") or "未知"
            nick = it.get("nickName") or ""
            pic = it.get("houseImage") or it.get("userImage") or ""
            ls = it.get("liveStatus")
            if self._is_playable(it):
                status = "🔴 直播中"
            elif ls == 1:
                status = "📅 未开播"
            elif ls in (3, 4):
                status = "⛔ 禁播"
            else:
                status = "⚪ 其他"
            mts = self._match_time_str(it, mt_map)
            parts = [status]
            if mts:
                parts.append(mts)
            if nick:
                parts.append(nick)
            vod_list.append({"vod_id": hid, "vod_name": name, "vod_pic": pic, "vod_remarks": " | ".join(parts)})
        return {"page": page, "pagecount": page + 1 if len(vod_list) >= 20 else page, "limit": 20, "total": 999, "list": vod_list}

    def detailContent(self, ids):
        hid = ids[0] if isinstance(ids, list) else ids
        url = self.api_base + "/api/c3/business/livehouse/detail?houseId=" + str(hid)
        try:
            r = requests.get(url, headers=HEADERS, timeout=10, verify=False)
            ad = ((r.json() or {}).get("data") or {}).get("anchorDetail") or {}
        except Exception:
            ad = {}
        if not ad:
            d2, _ = self._fetch_index()
            for it in self._all_items(d2):
                if str(it.get("houseId", "")) == str(hid):
                    ad = it
                    break
        name = ad.get("houseName") or ad.get("houseNameEn") or ad.get("nickName") or "未知"
        nick = ad.get("nickName") or ""
        pic = ad.get("houseImage") or ad.get("userImage") or ""
        flv = ad.get("playStreamAddress") or ""
        m3u8 = ad.get("playStreamAddress2") or ""
        flv3 = ad.get("playStreamAddress3") or ""
        episodes = []
        if flv:
            episodes.append("FLV线路$" + flv)
        if m3u8:
            episodes.append("M3U8线路$" + m3u8)
        if flv3:
            episodes.append("线路3$" + flv3)
        if not episodes:
            episodes.append("默认线路$" + "https://live07.workingspaceshq.com/live/" + str(hid) + ".flv")
        vod = {
            "vod_id": str(hid),
            "vod_name": name,
            "vod_pic": pic,
            "type_name": "体育直播",
            "vod_year": datetime.now(TZ_BJ).strftime("%Y"),
            "vod_area": "中国",
            "vod_remarks": ("🔴 直播中 | " if self._is_playable(ad) else "") + (nick or ""),
            "vod_actor": nick,
            "vod_director": "绿茵直播",
            "vod_content": name,
            "vod_play_from": "$$$".join(["绿茵直播"]),
            "vod_play_url": "$$$".join(["#".join(episodes)])
        }
        return {"list": [vod]}

    def searchContent(self, key, quick, pg="1"):
        data, mt_map = self._fetch_index()
        items = self._all_items(data)
        key = (key or "").lower()
        vod_list = []
        for it in items:
            name = it.get("houseName") or it.get("houseNameEn") or it.get("nickName") or ""
            if key and key not in name.lower():
                continue
            hid = str(it.get("houseId", ""))
            nick = it.get("nickName") or ""
            pic = it.get("houseImage") or it.get("userImage") or ""
            status = "🔴 直播中" if self._is_playable(it) else "📅 未开播"
            mts = self._match_time_str(it, mt_map)
            parts = [status]
            if mts:
                parts.append(mts)
            if nick:
                parts.append(nick)
            vod_list.append({"vod_id": hid, "vod_name": name, "vod_pic": pic, "vod_remarks": " | ".join(parts)})
        return {"list": vod_list}

    def playerContent(self, flag, id, vipFlags):
        headers = {
            "User-Agent": "Mozilla/5.0 (iPhone; CPU iPhone OS 16_6 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/16.6 Mobile/15E148 Safari/604.1",
            "Referer": WEB_HOST + "/",
            "Origin": WEB_HOST
        }
        return {"parse": 0, "playUrl": "", "url": id, "header": json.dumps(headers)}

    def isVideoFormat(self, url):
        return 1

    def manualVideoCheck(self):
        return 0

    def localProxy(self, param):
        return [200, "text/plain", b"", {}]