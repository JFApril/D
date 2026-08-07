#!/usr/bin/env python3
# Version: V11 - 修复嗅探问题：直接从详情页提取m3u8流地址，无需嗅探
import re, json, requests, datetime
from base.spider import Spider as BaseSpider
from urllib.parse import quote, unquote

class Spider(BaseSpider):
    def getName(self):
        return "006直播"

    def init(self, extend=""):
        self.base_url = "https://hot.006shipin.com"
        self.headers = {
            "User-Agent": "Mozilla/5.0 (Linux; Android 12; Pixel 6) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/103.0.0.0 Mobile Safari/537.36",
            "Referer": "https://hot.006shipin.com/",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
            "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
            "Connection": "keep-alive"
        }

    def _get_html(self, url):
        try:
            r = requests.get(url, headers=self.headers, timeout=15)
            r.encoding = 'utf-8'
            return r.text
        except:
            return ""

    def _parse_matches(self, html):
        result = []
        today = datetime.date.today().strftime("%m月%d日")
        match_pattern = re.compile(r'id="t_(\d+)"(.*?)(?=id="t_|$)', re.DOTALL)
        for match in match_pattern.finditer(html):
            match_id = match.group(1)
            block = match.group(2)
            date_match = re.search(r'(\d{2}月\d{2}日)', block)
            current_date = date_match.group(1) if date_match else today
            league_match = re.search(r'<div[^>]*title="([^"]+)"[^>]*>', block)
            league = league_match.group(1) if league_match else "未知赛事"
            time_match = re.search(r'<span>(\d{1,2}:\d{2})</span>', block)
            match_time = time_match.group(1) if time_match else ""
            status_match = re.search(r'<div class="text-12 relative text-nowrap[^"]*">(.*?)</div>', block, re.DOTALL)
            status = ""
            is_live = False
            if status_match:
                full_tag = status_match.group(0)
                status = re.sub(r'<[^>]+>', '', status_match.group(1)).strip()
                if "text-error" in full_tag:
                    is_live = True
            home_match = re.search(r'<div class="flex-1 p-3 home-name max-w-full">(.*?)</div>', block)
            home_team = home_match.group(1) if home_match else ""
            away_match = re.search(r'<div class="flex-1 p-3 away-name max-w-full">(.*?)</div>', block)
            away_team = away_match.group(1) if away_match else ""
            score_match = re.search(r'<div class="text-15 text-default">(.*?)</div>', block, re.DOTALL)
            score = "VS"
            if score_match:
                score_text = re.sub(r'<[^>]+>', '', score_match.group(1)).strip()
                score_text = re.sub(r'\s+', ' ', score_text).strip()
                if re.match(r'\d+\s*-\s*\d+', score_text):
                    score = re.sub(r'\s+', '', score_text)
            if status == "未" or not status:
                display_score = "0:0"
            else:
                display_score = score.replace('-', ':') if score != "VS" else "0:0"
            vod_name = f"{home_team} {display_score} {away_team}"
            status_icon = "🔴" if is_live else ""
            if match_time:
                remarks = f"{status_icon}{today} {match_time} {league}"
            else:
                remarks = f"{status_icon}{current_date} {league}"
            vod_id = f"006|{match_id}"
            vod_pic = ""
            pic_match = re.search(r'src="(https?://[^"]+team[^"]+\.png[^"]*)"', block)
            if pic_match:
                vod_pic = pic_match.group(1)
            channels = []
            channel_links = re.findall(r'<a[^>]*href="([^"]+)"[^>]*title="([^"]+)"', block)
            for href, title in channel_links:
                channels.append({"name": title, "url": f"{self.base_url}{href}"})
            channel_count = len(channels)
            if channel_count > 0:
                remarks = f"{remarks} ({channel_count}路)"
            sport_type = "other"
            if "basketball.png" in block:
                sport_type = "basketball"
            elif "football.png" in block:
                sport_type = "football"
            elif any(k in league for k in ["篮球", "NBA", "CBA", "WNBA", "MPBL"]):
                sport_type = "basketball"
            elif any(k in league for k in ["足球", "联", "杯", "超", "甲", "乙", "杯赛"]):
                sport_type = "football"
            result.append({
                "vod_id": vod_id,
                "vod_name": vod_name,
                "vod_pic": vod_pic,
                "vod_remarks": remarks,
                "type_name": league,
                "sport_type": sport_type
            })
        return result

    def homeContent(self, filter):
        classes = [
            {"type_id": "all", "type_name": "全部"},
            {"type_id": "football", "type_name": "足球"},
            {"type_id": "basketball", "type_name": "篮球"},
            {"type_id": "other", "type_name": "综合"}
        ]
        return {"class": classes, "list": [], "filters": {}}

    def categoryContent(self, tid, pg, filter, extend):
        html = self._get_html(f"{self.base_url}/")
        if not html:
            return {"page": 1, "pagecount": 1, "limit": 30, "total": 0, "list": []}
        matches = self._parse_matches(html)
        if tid != "all":
            matches = [m for m in matches if m.get("sport_type", "other") == tid]
        return {"page": 1, "pagecount": 1, "limit": 30, "total": len(matches), "list": matches}

    def detailContent(self, ids):
        try:
            vid = ""
            if isinstance(ids, list) and ids:
                first = ids[0]
                vid = first.get("vod_id", "") if isinstance(first, dict) else str(first)
            else:
                vid = str(ids) if ids else ""
            if not vid:
                return {"list": []}
            parts = vid.split("|")
            if len(parts) < 2:
                return {"list": []}
            match_id = parts[1]
            home_html = self._get_html(f"{self.base_url}/")
            if not home_html:
                return {"list": []}
            matches = self._parse_matches(home_html)
            match_info = None
            for m in matches:
                mid = m.get("vod_id", "").split("|")[-1]
                if mid == match_id:
                    match_info = m
                    break
            if not match_info:
                return {"list": []}
            channel_links = []
            block_match = re.search(r'id="t_' + match_id + r'"(.*?)(?=id="t_|$)', home_html, re.DOTALL)
            if block_match:
                block = block_match.group(1)
                channel_links = re.findall(r'<a[^>]*href="(/live-[12]/\d+\?_tv=(\d+))"[^>]*title="([^"]+)"', block)
            if not channel_links:
                href_list = re.findall(r'<a[^>]*href="(/live-[12]/\d+\?_tv=(\d+))"[^>]*title="([^"]+)"', home_html)
                for href, tvid, title in href_list:
                    if match_id in href:
                        channel_links.append((href, tvid, title))
            from_names = []
            from_urls = []
            if channel_links:
                first_href = channel_links[0][0]
                detail_html = self._get_html(f"{self.base_url}{first_href}")
                if detail_html:
                    nuxt_data_match = re.search(r'id="__NUXT_DATA__"[^>]*>(.*?)</script>', detail_html, re.DOTALL)
                    if nuxt_data_match:
                        try:
                            nuxt_arr = json.loads(nuxt_data_match.group(1))
                            anchor_streams = {}
                            for item in nuxt_arr:
                                if isinstance(item, dict) and "username" in item and "stream" in item and "url" in item:
                                    name_idx = item["username"]
                                    stream_idx = item["stream"]
                                    url_idx = item["url"]
                                    if all(isinstance(i, int) and i < len(nuxt_arr) for i in [name_idx, stream_idx, url_idx]):
                                        anchor_name = str(nuxt_arr[name_idx])
                                        m3u8 = str(nuxt_arr[stream_idx])
                                        if m3u8 and ".m3u8" in m3u8:
                                            anchor_streams[anchor_name] = m3u8
                            for href, tvid, title in channel_links:
                                if title in anchor_streams:
                                    from_names.append(title)
                                    from_urls.append(anchor_streams[title])
                                else:
                                    from_names.append(title)
                                    from_urls.append(f"{self.base_url}{href}")
                        except:
                            for href, tvid, title in channel_links:
                                from_names.append(title)
                                from_urls.append(f"{self.base_url}{href}")
                    else:
                        for href, tvid, title in channel_links:
                            from_names.append(title)
                            from_urls.append(f"{self.base_url}{href}")
                else:
                    for href, tvid, title in channel_links:
                        from_names.append(title)
                        from_urls.append(f"{self.base_url}{href}")
            if not from_names:
                from_names = [match_info["vod_name"].split(" ")[0] if " " in match_info["vod_name"] else "默认直播"]
                from_urls = [f"{self.base_url}/live-2/{match_id}"]
            detail = {
                "vod_id": vid,
                "vod_name": match_info["vod_name"],
                "vod_pic": match_info.get("vod_pic", ""),
                "vod_remarks": match_info.get("vod_remarks", ""),
                "type_name": match_info.get("type_name", "直播"),
                "vod_year": "",
                "vod_lang": "",
                "vod_area": "",
                "vod_director": "",
                "vod_actor": "",
                "vod_content": "",
                "vod_play_from": "$$$".join(from_names),
                "vod_play_url": "$$$".join(from_urls)
            }
            return {"list": [detail]}
        except:
            return {"list": []}

    def searchContent(self, kw, quick, pg):
        html = self._get_html(f"{self.base_url}/")
        if not html:
            return {"page": 1, "pagecount": 1, "limit": 30, "total": 0, "list": []}
        all_matches = self._parse_matches(html)
        kw_lower = kw.lower()
        result = [m for m in all_matches if kw_lower in m.get("vod_name", "").lower() or kw_lower in m.get("type_name", "").lower()]
        return {"page": 1, "pagecount": 1, "limit": 30, "total": len(result), "list": result}

    def playerContent(self, flag, id, vipFlags):
        url = str(id) if id else ""
        if url.startswith("http") and ".m3u8" in url:
            return {"parse": 0, "url": url, "header": self.headers}
        if url.startswith("http") and ".flv" in url:
            return {"parse": 0, "url": url, "header": self.headers}
        if not url.startswith("http"):
            url = f"{self.base_url}{url}"
        return {"parse": 1, "url": url, "header": self.headers}

    def localProxy(self, param):
        return [200, "text/plain", b"", {}]