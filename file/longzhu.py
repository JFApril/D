#!/usr/bin/env python3
# 龙珠直播 (longzhu) V1.3 - 增强数据结构空安全防护（修复bindMatchData为None导致的NoneType报错，播放直链解混淆保持可播）
import sys, re, json, time, requests
from datetime import datetime, timezone, timedelta
from urllib.parse import urlencode

try:
    from base.spider import Spider as BaseSpider
except ImportError:
    class BaseSpider:
        def __init__(self): pass

TZ_BJ = timezone(timedelta(hours=8))
API_BASE = "https://lzapi.wulalive.com"
HEADERS = {
    "User-Agent": "Mozilla/5.0 (iPhone; CPU iPhone OS 16_6 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/16.6 Mobile/15E148 Safari/604.1",
    "Origin": "https://m.51liaoqiu.com",
    "Referer": "https://m.51liaoqiu.com/",
    "client": "web_mobile",
    "channel": "web",
    "product": "lzLive",
    "version": "1.0.0",
    "device": "6a1b2c3d4e5f7a8b"
}

def _deobfuscate_url(url):
    if not url:
        return ""
    def _repl(m):
        prefix = m.group(1)
        hash_val = m.group(2)
        if len(hash_val) == 33:
            hash_val = hash_val[:6] + hash_val[7:]
        return "auth_key=" + prefix + hash_val
    return re.sub(r"auth_key=(\d+-\d+-\d+-)([a-zA-Z0-9]{33})", _repl, url)

class Spider(BaseSpider):
    def getName(self):
        return "龙珠直播"

    def init(self, extend=""):
        pass

    def isVideoFormat(self, url):
        return 1

    def manualVideoCheck(self):
        return 0

    def homeContent(self, filter):
        classes = [
            {"type_name": "全部直播", "type_id": "0"},
            {"type_name": "⚽ 足球", "type_id": "2"},
            {"type_name": "🏀 篮球", "type_id": "1"},
            {"type_name": "🎮 电竞", "type_id": "3"},
            {"type_name": "🌐 综合", "type_id": "13"}
        ]
        res = self.categoryContent("0", "1", filter, {})
        return {
            "class": classes,
            "list": res.get("list", []),
            "filters": {}
        }

    def homeVideoContent(self):
        return self.categoryContent("0", "1", False, {})

    def categoryContent(self, tid, pg, filter, extend):
        try:
            page = int(pg)
        except Exception:
            page = 1
        
        params = {"page": page, "size": 30}
        if tid and tid != "0":
            params["categoryId"] = tid

        url = f"{API_BASE}/room-biz/room/pageRankList?" + urlencode(params)
        try:
            r = requests.get(url, headers=HEADERS, timeout=10, verify=False)
            data = r.json()
            items = data.get("data", {}).get("list", []) or []
        except Exception:
            items = []

        vod_list = []
        now_ts = int(time.time())

        for item in items:
            if not isinstance(item, dict):
                continue
            info = item.get("infoData") or {}
            room_id = str(info.get("roomId", ""))
            if not room_id:
                continue

            live_info = item.get("liveData") or {}
            live_status = live_info.get("liveStatus", 0)
            stream_status = live_info.get("streamStatus", 0)

            anchor = (item.get("anchorData") or {}).get("userAccount") or {}
            anchor_name = anchor.get("nickname", "主播")
            avatar = anchor.get("avatar", "")

            match = item.get("bindMatchData") or {}
            home_team = (match.get("homeTeamData") or {}).get("name", "")
            away_team = (match.get("awayTeamData") or {}).get("name", "")
            comp_name = (match.get("competitionData") or {}).get("name", "")
            match_info = match.get("infoData") or {}
            match_ts = match_info.get("matchTimeAt", 0)
            match_status = match_info.get("matchStatus", 0)

            title = live_info.get("liveTitle") or info.get("title", "")
            if home_team and away_team:
                vod_name = f"{home_team} VS {away_team}"
                if comp_name:
                    vod_name += f" ({comp_name})"
            else:
                vod_name = title or f"{anchor_name}的直播间"

            time_str = ""
            if match_ts and int(match_ts) > 0:
                dt = datetime.fromtimestamp(int(match_ts), TZ_BJ)
                time_str = dt.strftime("%H:%M")

            if match_status == 8:
                status_txt = "🏁 完场"
            elif match_status in [2, 3, 4, 5, 7] or (stream_status == 1 and live_status == 1 and not match_status):
                status_txt = "🔴 直播中"
            elif match_status == 1 or (match_ts and int(match_ts) > now_ts + 600):
                status_txt = "📅 预告"
            else:
                status_txt = "🔴 直播中" if (stream_status == 1 or live_status == 1) else "📅 预告"

            remarks_parts = [status_txt]
            if time_str:
                remarks_parts.append(time_str)
            if comp_name:
                remarks_parts.append(comp_name)
            remarks_parts.append(anchor_name)

            vod_list.append({
                "vod_id": room_id,
                "vod_name": vod_name,
                "vod_pic": avatar or "https://m.51liaoqiu.com/favicon.ico",
                "vod_remarks": " | ".join(remarks_parts)
            })

        return {
            "page": page,
            "pagecount": page + 1 if len(vod_list) >= 30 else page,
            "limit": 30,
            "total": 999,
            "list": vod_list
        }

    def detailContent(self, ids):
        room_id = ids[0] if isinstance(ids, list) else ids
        url = f"{API_BASE}/room-biz/room/detail?roomId={room_id}"
        
        try:
            r = requests.get(url, headers=HEADERS, timeout=10, verify=False)
            res = r.json()
            data = res.get("data") or {}
        except Exception:
            data = {}

        info = data.get("infoData") or {}
        anchor = (data.get("anchorData") or {}).get("userAccount") or {}
        anchor_name = anchor.get("nickname", "主播")
        avatar = anchor.get("avatar", "")
        title = info.get("title", f"{anchor_name}的直播间")

        pull_streams = data.get("pullStreamData") or {}
        quality_map = [
            ("original", "龙珠-原画"),
            ("lud", "龙珠-超清"),
            ("lhd", "龙珠-高清"),
            ("lsd", "龙珠-标清"),
            ("lld", "龙珠-流畅")
        ]

        play_from = []
        play_urls = []

        for q_key, q_label in quality_map:
            stream_obj = pull_streams.get(q_key) or {}
            if not stream_obj or not isinstance(stream_obj, dict):
                continue

            flv_url = _deobfuscate_url(stream_obj.get("flvUrl", ""))
            m3u8_url = _deobfuscate_url(stream_obj.get("m3u8Url", ""))

            episodes = []
            if flv_url:
                episodes.append(f"FLV线路${flv_url}")
            if m3u8_url:
                episodes.append(f"M3U8线路${m3u8_url}")

            if episodes:
                play_from.append(q_label)
                play_urls.append("#".join(episodes))

        if not play_from:
            play_from.append("龙珠官方")
            play_urls.append(f"直播线路$https://lzpull.wulalive.com/lzLive/{int(room_id):08d}.flv")

        vod = {
            "vod_id": str(room_id),
            "vod_name": title,
            "vod_pic": avatar,
            "type_name": "体育直播",
            "vod_year": datetime.now(TZ_BJ).strftime("%Y"),
            "vod_area": "中国",
            "vod_remarks": f"主播: {anchor_name}",
            "vod_actor": anchor_name,
            "vod_director": "龙珠直播",
            "vod_content": f"房间号: {room_id} | 主播: {anchor_name} | {title}",
            "vod_play_from": "$$$".join(play_from),
            "vod_play_url": "$$$".join(play_urls)
        }

        return {"list": [vod]}

    def searchContent(self, key, quick, pg="1"):
        return {"list": []}

    def playerContent(self, flag, id, vipFlags):
        headers = {
            "User-Agent": "Mozilla/5.0 (iPhone; CPU iPhone OS 16_6 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/16.6 Mobile/15E148 Safari/604.1",
            "Referer": "https://m.51liaoqiu.com/",
            "Origin": "https://m.51liaoqiu.com"
        }
        return {
            "parse": 0,
            "playUrl": "",
            "url": id,
            "header": json.dumps(headers)
        }

    def localProxy(self, param):
        return [200, "text/plain", b"", {}]