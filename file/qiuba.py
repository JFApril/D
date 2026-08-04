#!/usr/bin/python
# -*- coding: utf-8 -*-
# 版本: V2 - 修复remark日期时间格式，显示"月-日 时:分"（UTC+8）
import re, json, requests, base64
from urllib.parse import quote
from base.spider import Spider

class Spider(Spider):
    def getName(self): return "球吧体育"

    def init(self, extend=""):
        self.host = "https://www.qiuba001.vip"
        self.api = self.host + "/api"
        self.headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
            "Referer": self.host + "/",
            "Origin": self.host,
            "Accept": "*/*",
            "Accept-Language": "zh-CN,zh;q=0.9"
        }
        
        self.video_headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
            "Referer": self.host + "/",
            "Origin": self.host,
            "Accept": "*/*",
            "Accept-Language": "zh-CN,zh;q=0.9",
            "Connection": "keep-alive"
        }

    def _get(self, url, timeout=15):
        try:
            r = requests.get(url, headers=self.headers, timeout=timeout)
            r.raise_for_status()
            return r.json()
        except:
            return {}

    def _post(self, url, data, timeout=15):
        try:
            r = requests.post(url, json=data, headers=self.headers, timeout=timeout)
            r.raise_for_status()
            return r.json()
        except:
            return {}

    def _fix(self, u):
        if not u:
            return ""
        if u.startswith("//"):
            return "https:" + u
        elif u.startswith("/"):
            return self.host + u
        return u

    def _decode_play_url(self, encrypted):
        if not encrypted or not encrypted.startswith("crawler_b64:"):
            return ""
        try:
            encoded = encrypted.split(":", 1)[1]
            encoded = encoded.replace("-", "+").replace("_", "/")
            padding = 4 - len(encoded) % 4
            if padding != 4:
                encoded += "=" * padding
            return base64.b64decode(encoded).decode("utf-8")
        except:
            return ""

    def _format_status(self, status):
        status_map = {
            "live": "🔴 进行中",
            "not_started": "⚪ 未开始",
            "finished": "⚫ 已结束"
        }
        return status_map.get(status, status)

    def _format_score(self, home_score, away_score):
        if home_score is not None and away_score is not None:
            return f"{home_score}:{away_score}"
        return "vs"

    def homeContent(self, filter):
        data = self._get(f"{self.api}/categories")
        classes = []
        if data and isinstance(data, list):
            for cat in data:
                classes.append({
                    "type_id": str(cat.get("id", "")),
                    "type_name": cat.get("name", "")
                })
        elif data and "categories" in data:
            for cat in data["categories"]:
                classes.append({
                    "type_id": str(cat.get("id", "")),
                    "type_name": cat.get("name", "")
                })
        
        list_data = self._get(f"{self.api}/matches?page=1&page_size=20&status=live")
        list_items = []
        if list_data and "items" in list_data:
            for item in list_data["items"]:
                list_items.append(self._parse_match_item(item))
        
        return {"class": classes, "list": list_items, "filters": {}}

    def categoryContent(self, tid, pg, filter, extend):
        url = f"{self.api}/matches?page={pg}&page_size=20&category_id={tid}"
        data = self._get(url)
        items = []
        total = 0
        pagecount = 1
        if data and "items" in data:
            for item in data["items"]:
                items.append(self._parse_match_item(item))
            total = data.get("total", len(items))
            page_size = data.get("page_size", 20)
            pagecount = (total + page_size - 1) // page_size
        
        return {"page": int(pg), "pagecount": pagecount, "limit": 20, "total": total, "list": items}

    def _parse_match_item(self, item):
        match_id = str(item.get("id", ""))
        home_team = item.get("home_team", {})
        away_team = item.get("away_team", {})
        competition = item.get("competition", {})
        
        home_name = home_team.get("name", "主队")
        away_name = away_team.get("name", "客队")
        competition_name = competition.get("name", "未知联赛")
        status = item.get("status", "not_started")
        
        home_score = item.get("home_score")
        away_score = item.get("away_score")
        score = self._format_score(home_score, away_score)
        clock = item.get("clock", "")
        
        signal_count = item.get("signal_count", 0)
        signal_total = item.get("signal_total_count", 0)
        
        start_time = item.get("start_time", "")
        time_part = ""
        if start_time and "T" in start_time:
            try:
                dt = start_time.replace("Z", "+00:00")
                from datetime import datetime, timezone, timedelta
                dt_obj = datetime.fromisoformat(dt)
                dt_utc8 = dt_obj.astimezone(timezone(timedelta(hours=8)))
                time_part = dt_utc8.strftime("%m-%d %H:%M")
            except:
                time_part = start_time.split("T")[1][:5] if "T" in start_time else ""
        
        status_text = self._format_status(status)
        
        name = f"{competition_name} {home_name} vs {away_name}"
        if status == "live":
            name = f"{competition_name} {home_name} {score} {away_name}"
        
        remarks = f"{status_text} {score}"
        if signal_count > 0:
            remarks += f" | {signal_count}路"
        if time_part:
            remarks += f" {time_part}"
        
        home_logo = home_team.get("logo", "")
        away_logo = away_team.get("logo", "")
        pic = home_logo if home_logo else (away_logo if away_logo else "")
        
        vod_id = f"qiuba|{match_id}|{quote(name)}"
        
        return {
            "vod_id": vod_id,
            "vod_name": name,
            "vod_pic": pic,
            "vod_remarks": remarks,
            "_status": status,
            "_signal_count": signal_count,
            "_start_time": start_time
        }

    def detailContent(self, ids):
        vid = str(ids[0] if isinstance(ids, list) and ids else ids or "")
        parts = vid.split("|")
        if len(parts) < 2 or parts[0] != "qiuba":
            return {"code": 1, "list": []}
        
        match_id = parts[1]
        name = parts[2] if len(parts) > 2 else "体育直播"
        try:
            from urllib.parse import unquote
            name = unquote(name)
        except:
            pass
        
        match_data = self._get(f"{self.api}/matches/{match_id}")
        if not match_data:
            return {"code": 1, "list": []}
        
        signals_data = self._get(f"{self.api}/matches/{match_id}/signals")
        signals = []
        if signals_data and "signals" in signals_data:
            signals = signals_data["signals"]
        elif isinstance(signals_data, list):
            signals = signals_data
        
        play_lines = []
        if signals:
            for i, sig in enumerate(signals):
                source_id = sig.get("source_id", "")
                display_name = sig.get("display_name", f"信号{i+1}")
                status = sig.get("status", "")
                recommended = sig.get("recommended", False)
                
                if status == "recommended_online":
                    prefix = "⭐"
                elif status == "online":
                    prefix = "🟢"
                else:
                    prefix = "⚪"
                
                signal_name = f"{prefix} {display_name}"
                play_url = f"qiuba_play|{match_id}|{source_id}"
                play_lines.append(f"{signal_name}${play_url}")
        
        if not play_lines:
            play_lines.append(f"默认直播$qiuba_play|{match_id}|default")
        
        home_team = match_data.get("home_team", {})
        away_team = match_data.get("away_team", {})
        competition = match_data.get("competition", {})
        
        home_name = home_team.get("name", "主队")
        away_name = away_team.get("name", "客队")
        competition_name = competition.get("name", "未知联赛")
        status = match_data.get("status", "not_started")
        
        home_score = match_data.get("home_score")
        away_score = match_data.get("away_score")
        score = self._format_score(home_score, away_score)
        
        status_text = self._format_status(status)
        
        vod_name = f"{competition_name} {home_name} vs {away_name}"
        if status == "live":
            vod_name = f"{competition_name} {home_name} {score} {away_name}"
        
        home_logo = home_team.get("logo", "")
        away_logo = away_team.get("logo", "")
        vod_pic = home_logo if home_logo else (away_logo if away_logo else "")
        
        vod_content = f"比赛：{competition_name}\n"
        vod_content += f"主队：{home_name}\n"
        vod_content += f"客队：{away_name}\n"
        vod_content += f"状态：{status_text}\n"
        if status == "live":
            vod_content += f"比分：{score}\n"
        vod_content += f"信号源：{len(signals)}路"
        
        return {
            "code": 1,
            "msg": "比赛详情",
            "page": 1,
            "pagecount": 1,
            "limit": 1,
            "total": 1,
            "list": [{
                "vod_id": vid,
                "vod_name": vod_name,
                "vod_pic": vod_pic,
                "vod_remarks": status_text,
                "vod_content": vod_content,
                "vod_play_from": "球吧直播",
                "vod_play_url": "#".join(play_lines)
            }]
        }

    def searchContent(self, key, quick, pg="1"):
        url = f"{self.api}/matches?page={pg}&page_size=20&search={quote(key)}"
        data = self._get(url)
        items = []
        if data and "items" in data:
            for item in data["items"]:
                items.append(self._parse_match_item(item))
        
        return {"list": items, "page": int(pg)}

    def playerContent(self, flag, id, vipFlags):
        url = str(id or "")
        
        if url.startswith("qiuba_play|"):
            parts = url.split("|")
            if len(parts) >= 3:
                match_id = parts[1]
                source_id = parts[2]
                
                if source_id == "default":
                    play_data = self._get(f"{self.api}/matches/{match_id}/signals")
                    if play_data:
                        signals = []
                        if "signals" in play_data:
                            signals = play_data["signals"]
                        elif isinstance(play_data, list):
                            signals = play_data
                        
                        if signals:
                            for sig in signals:
                                if sig.get("status") == "recommended_online":
                                    source_id = sig.get("source_id", "")
                                    break
                            if source_id == "default" and signals:
                                source_id = signals[0].get("source_id", "")
                
                if source_id and source_id != "default":
                    session_data = self._post(f"{self.api}/play/session", {"source_id": source_id})
                    if session_data and "real_url_encrypted" in session_data:
                        encrypted = session_data["real_url_encrypted"]
                        m3u8_url = self._decode_play_url(encrypted)
                        if m3u8_url:
                            return {"parse": 0, "url": m3u8_url, "header": self.video_headers}
                
                return {"parse": 1, "url": f"{self.host}/", "header": self.video_headers}
        
        if ".m3u8" in url or ".mp4" in url or ".flv" in url:
            return {"parse": 0, "url": url, "header": self.video_headers}
        
        return {"parse": 1, "url": url, "header": self.video_headers}
