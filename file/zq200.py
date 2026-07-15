#!/usr/bin/python
# -*- coding: utf-8 -*-
# Version: V12 - 无外部依赖版本，使用urllib替代requests
# 适用于  等平台，无需pip安装任何依赖,过滤主播
import json, time, re
from urllib.request import urlopen, Request

try:
    from base.spider import Spider
except ImportError:
    # 独立运行时的备用Spider类
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
    
    def _api_get(self, path):
        url = f"{self.api_host}{path}"
        try:
            req = Request(url, headers=self.headers)
            with urlopen(req, timeout=15) as resp:
                if resp.getcode() == 200:
                    data = resp.read().decode()
                    return json.loads(data)
            return None
        except: return None
    
    def _get_livestreams(self):
        ts = int(time.time() * 1000)
        data = self._api_get(f"/api/c5/business/livehouse/index?lang=zh&timestamp={ts}")
        if not data or not data.get("success"): return []
        result = []
        seen = set()
        sport_prefix = {1: "football", 2: "basketball", 3: "v2", 4: "volleyball"}
        
        def get_logo_url(sport_id, logo):
            if logo:
                if not logo.startswith("http"):
                    if "/" in logo:
                        return f"https://img0.aiscore.com/{logo}"
                    else:
                        prefix = sport_prefix.get(sport_id, "football")
                        return f"https://img0.aiscore.com/{prefix}/team/{logo}"
            return logo or ""
        
        def fmt_time(ts_sec):
            if not ts_sec: return ""
            return time.strftime('%m-%d %H:%M', time.localtime(ts_sec))
        
        match_streams = data.get("data", {}).get("matchLivestreams", [])
        house_time_map = {}
        house_stream_map = {}
        for item in match_streams:
            match_data = item.get("result", {}).get("match", {})
            if not match_data: continue
            match_time = match_data.get("matchTime", 0)
            status_id = match_data.get("statusId", 0)
            for anchor in item.get("reservedAnchors", []):
                h_id = anchor.get("houseId", "")
                if h_id: house_time_map[h_id] = (match_time, status_id)
        
        ongoing = data.get("data", {}).get("ongoingLivestreams", [])
        for item in ongoing:
            house_id = item.get("houseId", "")
            stream_url = item.get("playStreamAddress", "")
            stream_m3u8 = item.get("playStreamAddress2", "")
            valid_stream = ""
            if stream_url and stream_url.startswith("http") and stream_url != "www":
                valid_stream = stream_url
            elif stream_m3u8 and stream_m3u8.startswith("http") and stream_m3u8 != "www":
                valid_stream = stream_m3u8
            if house_id and valid_stream:
                house_stream_map[house_id] = valid_stream
        
        anchor_streams = data.get("data", {}).get("anchorLivestreams", [])
        for item in anchor_streams:
            house_id = item.get("houseId", "")
            stream_url = item.get("playStreamAddress", "")
            stream_m3u8 = item.get("playStreamAddress2", "")
            valid_stream = ""
            if stream_url and stream_url.startswith("http") and stream_url != "www":
                valid_stream = stream_url
            elif stream_m3u8 and stream_m3u8.startswith("http") and stream_m3u8 != "www":
                valid_stream = stream_m3u8
            if house_id and valid_stream:
                house_stream_map[house_id] = valid_stream
        
        for item in match_streams:
            match_data = item.get("result", {}).get("match", {})
            if not match_data: continue
            competition = match_data.get("competition", {})
            home_team_data = match_data.get("homeTeam", {})
            away_team_data = match_data.get("awayTeam", {})
            home_team = home_team_data.get("name", "")
            away_team = away_team_data.get("name", "")
            league = competition.get("name", "")
            video_url = match_data.get("videoUrl", "")
            sport_id = match_data.get("sportId")
            status_id = match_data.get("statusId", 0)
            match_name = f"{home_team} vs {away_team}" if home_team and away_team else ""
            if not match_name: continue
            
            effective_video_url = ""
            if video_url and video_url.startswith("http") and video_url != "https":
                effective_video_url = video_url
            else:
                for anchor in item.get("reservedAnchors", []):
                    anchor_stream = anchor.get("playStreamAddress", "")
                    anchor_stream2 = anchor.get("playStreamAddress2", "")
                    if anchor_stream and anchor_stream.startswith("http") and anchor_stream != "www":
                        effective_video_url = anchor_stream
                        break
                    elif anchor_stream2 and anchor_stream2.startswith("http") and anchor_stream2 != "www":
                        effective_video_url = anchor_stream2
                        break
                
                if not effective_video_url:
                    for anchor in item.get("reservedAnchors", []):
                        h_id = anchor.get("houseId", "")
                        if h_id and h_id in house_stream_map:
                            effective_video_url = house_stream_map[h_id]
                            break
            
            match_id = match_data.get("id", "")
            match_time = match_data.get("matchTime", 0)
            time_str = fmt_time(match_time)
            is_live = effective_video_url and status_id in (2, 4)
            is_upcoming = not effective_video_url and status_id in (1, 2, 3)
            if is_live:
                prefix = "🟢 "
            elif is_upcoming:
                prefix = "⏳ "
            else:
                prefix = ""
            if time_str and league:
                remarks = f"{prefix}{time_str} {league}"
            elif time_str:
                remarks = f"{prefix}{time_str}"
            else:
                remarks = f"{prefix}{league}" if league else ""
            home_logo = home_team_data.get("logo", "")
            home_logo_url = get_logo_url(sport_id, home_logo)
            key = f"{match_name}_{league}"
            if key in seen: continue
            seen.add(key)
            if effective_video_url:
                final_url = effective_video_url
            else:
                final_url = f"https://zuqiu200.app/match/{match_id}" if match_id else ""
            result.append({
                "vod_id": match_id,
                "vod_name": match_name,
                "vod_pic": home_logo_url,
                "vod_play_from": league or "直播",
                "vod_play_url": final_url,
                "vod_remarks": remarks,
                "sport_id": str(sport_id) if sport_id else ""
            })
        
        for item in ongoing:
            house_id = item.get("houseId", "")
            house_name = item.get("houseName", "")
            stream_url = item.get("playStreamAddress", "")
            stream_m3u8 = item.get("playStreamAddress2", "")
            race_type_id = item.get("raceTypeId")
            house_image = item.get("houseImage", "")
            
            valid_stream = ""
            if stream_url and stream_url.startswith("http") and stream_url != "www":
                valid_stream = stream_url
            elif stream_m3u8 and stream_m3u8.startswith("http") and stream_m3u8 != "www":
                valid_stream = stream_m3u8
            
            if house_id and house_name and valid_stream:
                parts = house_name.split("|")
                league = parts[0].strip() if len(parts) > 0 else ""
                match_info = parts[1].strip() if len(parts) > 1 else house_name
                team_parts = match_info.split("VS")
                if len(team_parts) < 2: team_parts = match_info.split("vs")
                home_team = team_parts[0].strip() if len(team_parts) > 0 else ""
                away_team = team_parts[1].strip() if len(team_parts) > 1 else ""
                match_name = f"{home_team} vs {away_team}" if home_team and away_team else house_name
                mt = house_time_map.get(house_id, (0, 0))
                time_str = fmt_time(mt[0])
                if time_str and league:
                    remarks = f"🟢 {time_str} {league}"
                elif time_str:
                    remarks = f"🟢 {time_str}"
                else:
                    remarks = f"🟢 {league}" if league else "🟢 直播中"
                key = f"{match_name}_{league}"
                if key in seen: continue
                seen.add(key)
                result.append({
                    "vod_id": house_id,
                    "vod_name": match_name,
                    "vod_pic": house_image,
                    "vod_play_from": league or "直播",
                    "vod_play_url": valid_stream,
                    "vod_remarks": remarks,
                    "sport_id": str(race_type_id) if race_type_id else ""
                })
        
        return result
    
    def homeVideoContent(self, extend=""):
        return self.homeContent(extend)
    
    def homeContent(self, extend=""):
        try:
            classes = []
            for cat in self.categories:
                classes.append({
                    "type_id": cat["type_id"],
                    "type_name": cat["type_name"],
                    "type_extend": "",
                    "type_url": ""
                })
            
            videos = self._get_livestreams()
            return {"class": classes, "list": videos, "filter": {}}
        except Exception as e:
            return {"class": [], "list": [], "filter": {}}
    
    def categoryContent(self, tid, pg, filterable, extend):
        try:
            all_videos = self._get_livestreams()
            if tid == "all":
                videos = all_videos
            else:
                videos = [v for v in all_videos if v.get("sport_id") == tid]
            
            page_size = 20
            start = (int(pg) - 1) * page_size
            end = start + page_size
            page_videos = videos[start:end]
            
            return {"list": page_videos, "page": pg, "pagecount": (len(videos) + page_size - 1) // page_size, "limit": page_size, "total": len(videos)}
        except Exception as e:
            return {"list": [], "page": pg, "pagecount": 1, "limit": 20, "total": 0}
    
    def detailContent(self, ids):
        try:
            all_videos = self._get_livestreams()
            for video in all_videos:
                if video["vod_id"] == ids[0]:
                    detail = video.copy()
                    detail["vod_play_from"] = video["vod_play_from"]
                    detail["vod_play_url"] = video["vod_play_url"]
                    return {"list": [detail]}
            return {"list": []}
        except Exception as e:
            return {"list": []}
    
    def searchContent(self, keyword, quick, pg):
        try:
            all_videos = self._get_livestreams()
            results = []
            keyword_lower = keyword.lower()
            
            for video in all_videos:
                name = video["vod_name"].lower()
                if keyword_lower in name or keyword in video["vod_play_from"]:
                    results.append(video)
            
            page_size = 20
            start = (int(pg) - 1) * page_size
            end = start + page_size
            page_results = results[start:end]
            
            return {"list": page_results, "page": pg, "pagecount": (len(results) + page_size - 1) // page_size, "limit": page_size, "total": len(results)}
        except Exception as e:
            return {"list": [], "page": pg, "pagecount": 1, "limit": 20, "total": 0}
    
    def playerContent(self, flag, id, vipFlags):
        try:
            parse = 0
            url = id
            
            if not url:
                url = ""
            
            return {"parse": parse, "url": url, "header": ""}
        except Exception as e:
            return {"parse": 0, "url": "", "header": ""}