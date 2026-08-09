#!/usr/bin/python
# -*- coding: utf-8 -*-
# V2.8 - 7zb体育直播 - 列表页标题格式v2+log注释
import re, json, time, hashlib, traceback
import requests
from urllib.parse import quote
from base.spider import Spider

#_LOG = "/storage/emulated/0/Download/spider/7zb_debug.log"
#def _log(msg):
#    try:
#        with open(_LOG, "a") as f: f.write("[%s] %s\n" % (time.strftime("%H:%M:%S"), str(msg)[:800]))
#    except: pass
def _log(msg): pass

class Spider(Spider):
    def getName(self): return "7zb体育"

    HOST = "https://m.7zb.top"
    DATA_HOST = "https://7zb7.live"
    JSONP_HOST = "https://json.ncctrials.com"
    BASE_URL = "/webApi"
    API_KEY_REQ = b"PHp1st5vEg5Ca8FH"
    API_KEY_RESP = b"qlCJekfRKwWkQxl7"
    UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/140.0.0.0 Safari/537.36"

    def init(self, extend=""):
        #_log("init v2.7 start")
        self.session_id = ""

    def _aes_ecb(self, data, key):
        try:
            from Crypto.Cipher import AES
            pad_len = 16 - (len(data) % 16)
            data += bytes([pad_len] * pad_len)
            cipher = AES.new(key, AES.MODE_ECB)
            return cipher.encrypt(data)
        except ImportError:
            return None

    def _aes_ecb_dec(self, data, key):
        try:
            from Crypto.Cipher import AES
            cipher = AES.new(key, AES.MODE_ECB)
            dec = cipher.decrypt(data)
            pad_len = dec[-1]
            if 0 < pad_len <= 16 and all(b == pad_len for b in dec[-pad_len:]):
                dec = dec[:-pad_len]
            return dec
        except ImportError:
            return None

    def _varint(self, num):
        b = []
        while num > 0x7f:
            b.append((num & 0x7f) | 0x80)
            num >>= 7
        b.append(num & 0x7f)
        return bytes(b)

    def _pb_varint(self, fn, v):
        return self._varint((fn << 3) | 0) + self._varint(v)

    def _pb_string(self, fn, s):
        sb = s.encode("utf-8") if isinstance(s, str) else s
        return self._varint((fn << 3) | 2) + self._varint(len(sb)) + sb

    def _pb_bytes(self, fn, b):
        return self._varint((fn << 3) | 2) + self._varint(len(b)) + b

    def _pb_message(self, fn, m):
        return self._varint((fn << 3) | 2) + self._varint(len(m)) + m

    def _pb_parse(self, data):
        fields = {}
        off = 0
        while off < len(data):
            b = data[off]; off += 1
            fn = b >> 3; wt = b & 0x7
            if wt == 0:
                v = 0; shift = 0
                while off < len(data):
                    bb = data[off]; off += 1
                    v |= (bb & 0x7f) << shift
                    if (bb & 0x80) == 0: break
                    shift += 7
                fields.setdefault(fn, []).append(("v", v))
            elif wt == 2:
                length = 0; shift = 0
                while off < len(data):
                    bb = data[off]; off += 1
                    length |= (bb & 0x7f) << shift
                    if (bb & 0x80) == 0: break
                    shift += 7
                val = data[off:off+length]; off += length
                fields.setdefault(fn, []).append(("b", val))
            else:
                break
        return fields

    def _build_request(self, params_json):
        ci = b""
        if self.session_id:
            ci += self._pb_string(1, self.session_id)
        ci += self._pb_varint(5, 3) + self._pb_varint(6, 1)
        pj = params_json.encode("utf-8") if isinstance(params_json, str) else params_json
        cr = self._pb_message(1, ci) + self._pb_bytes(2, pj)
        return self._pb_message(1, cr)

    def _api_post(self, path, params=None):
        try:
            proto = self._build_request(json.dumps(params or {}))
            enc = self._aes_ecb(proto, self.API_KEY_REQ)
            if not enc:
                return None
            header = bytes([0, 0xA0]) + len(enc).to_bytes(4, "big")
            body = header + enc
            url = self.DATA_HOST + self.BASE_URL + path
            r = requests.post(url, data=body, headers={
                "User-Agent": self.UA,
                "Referer": self.HOST + "/",
                "Content-Type": "application/octet-stream"
            }, timeout=15)
            rb = r.content
            if len(rb) < 6:
                return None
            dec = self._aes_ecb_dec(rb[6:], self.API_KEY_RESP)
            if not dec:
                return None
            f = self._pb_parse(dec)
            if 2 not in f or not f[2]:
                return None
            resp = self._pb_parse(f[2][0][1])
            code = 0
            if 1 in resp and resp[1]:
                cr = self._pb_parse(resp[1][0][1])
                if 1 in cr and cr[1]:
                    code = cr[1][0][1]
            if 2 in resp and resp[2]:
                body_str = resp[2][0][1].decode("utf-8", errors="replace")
                if code == 200:
                    try:
                        return json.loads(body_str)
                    except json.JSONDecodeError:
                        return None
                else:
                    return None
            return None
        except Exception as e:
            #_log("api_post err: %s %s" % (path, e))
            return None

    def _ensure_session(self):
        if not self.session_id:
            uid = str(-int(time.time() * 1000)) + str(hashlib.md5(str(time.time()).encode()).hexdigest()[:6])
            data = self._api_post("/login/guestLogin", {
                "uid": uid,
                "nickName": hashlib.md5(str(time.time()).encode()).hexdigest()[:8].upper(),
                "grow": 0, "score": 0
            })
            if data and "sessionId" in data:
                self.session_id = data["sessionId"]

    def _parse_title(self, title):
        if not title:
            return "", ""
        t = re.sub(r'[\t]+', '  ', title).strip()
        m = re.match(r'^(.+?)\s{1,4}(.+?)(?:\s+(?:VS|vs|V\s*S|-))\s*(.+)$', t)
        if m:
            return m.group(1).strip(), "%s VS %s" % (m.group(2).strip(), m.group(3).strip())
        m2 = re.match(r'^(.+?)\s+(.+)$', t)
        if m2:
            return m2.group(1).strip(), m2.group(2).strip()
        return "", t

    def _get_stream(self, room_num):
        try:
            v = int(time.time() * 1000)
            url = f"{self.JSONP_HOST}/room/{room_num}/detail.json?v={v}"
            r = requests.get(url, timeout=8, headers={
                "User-Agent": self.UA, "Referer": self.HOST + "/", "Accept": "*/*"
            })
            text = r.text
            m = re.search(r'\((\{.*\})\)', text, re.DOTALL)
            if not m:
                return None
            data = json.loads(m.group(1))
            stream = data.get("data", {}).get("stream", {})
            room_data = data.get("data", {}).get("room", {})
            if not stream:
                return None
            return {
                "flv": stream.get("flv", ""),
                "hdFlv": stream.get("hdFlv", ""),
                "m3u8": stream.get("m3u8", ""),
                "hdM3u8": stream.get("hdM3u8", ""),
                "name": room_data.get("anchor", {}).get("nickName") or "",
                "title": room_data.get("title", ""),
                "pic": room_data.get("customCoverUrl") or room_data.get("cover") or "",
            }
        except Exception as e:
            #_log("get_stream err: %s %s" % (room_num, e))
            return None

    def _parse_room(self, d):
        rid = str(d.get("roomNum", ""))
        anchor = d.get("anchor", {})
        anchor_name = anchor.get("nickName") or ""
        pic = d.get("customCoverUrl") or d.get("customCover") or d.get("cover") or anchor.get("icon") or ""
        title = d.get("title") or ""
        league, match_info = self._parse_title(title)
        if match_info and anchor_name:
            name = "%s [%s]" % (match_info, anchor_name)
        else:
            name = anchor_name or match_info or d.get("roomName") or f"直播间 {rid}"
        now_str = time.strftime("%m-%d %H:%M")
        marks = ["🔴", now_str]
        if league:
            marks.append(league)
        remark = " ".join(marks)
        return {
            "vod_id": rid,
            "vod_name": name,
            "vod_pic": pic,
            "vod_remarks": remark
        }

    def homeContent(self, filter):
        classes = [
            {"type_id": "hot", "type_name": "热门直播"},
            {"type_id": "live", "type_name": "直播中"},
            {"type_id": "match", "type_name": "赛程"}
        ]
        filters = {
            "hot": [{"name": "推荐", "key": "recommend"}],
            "live": [{"name": "全部", "key": "all"}, {"name": "足球", "key": "football"}, {"name": "篮球", "key": "basketball"}],
            "match": [{"name": "全部", "key": "all"}, {"name": "足球", "key": "football"}, {"name": "篮球", "key": "basketball"}]
        }
        return {"class": classes, "filters": filters}

    def categoryContent(self, tid, pg, filter, extend):
        self._ensure_session()
        tid = str(tid or "hot")
        pg = int(pg) if pg else 1
        params = {"page": pg, "pageSize": 30}
        if tid == "live":
            params["type"] = "live"
        elif tid == "match":
            params["type"] = "match"
        else:
            params["type"] = "hot"
        if isinstance(extend, dict) and extend.get("key") and extend.get("key") != "all":
            params["category"] = extend["key"]
        items = []
        seen = set()
        data = self._api_post("/live/hot", params)
        if data:
            rooms = data.get("rooms", data.get("list", []))
            if isinstance(rooms, list):
                for room in rooms:
                    item = self._parse_room(room)
                    vid = item["vod_id"]
                    if vid not in seen:
                        seen.add(vid)
                        items.append(item)
        #_log("cat total=%d" % len(items))
        return {"page": pg, "pagecount": 10, "limit": 30, "total": len(items), "list": items}

    def detailContent(self, ids):
        vid = str(ids[0] if isinstance(ids, list) and ids else ids or "")
        room_num = vid.split("###")[0].split("|")[-1] or vid
        if not room_num:
            return {"code": 1, "list": []}
        stream = self._get_stream(room_num)
        if stream:
            hd_flv = stream.get("hdFlv", "")
            sd_flv = stream.get("flv", "")
            hd_m3u8 = stream.get("hdM3u8", "")
            sd_m3u8 = stream.get("m3u8", "")
            anchor_name = stream.get("name", "")
            title_raw = stream.get("title", "")
            pic = stream.get("pic", "")
            league, match_info = self._parse_title(title_raw)
            vod_name = "%s %s" % (match_info, anchor_name) if anchor_name and match_info else (anchor_name or match_info or f"直播间 {room_num}")
            now_str = time.strftime("%H:%M")
            date_str = ""
            for kw in ["今天", "明日", "明天"]:
                if kw in title_raw:
                    date_str = kw
                    break
            if not date_str:
                date_str = time.strftime("%m-%d")
            remarks_parts = ["🔴", date_str, now_str]
            if league:
                remarks_parts.append(league)
            remarks = " ".join(remarks_parts)
            lines = []
            if hd_flv:
                lines.append(f"高清FLV${hd_flv}")
            if hd_m3u8:
                lines.append(f"高清HLS${hd_m3u8}")
            if sd_flv:
                lines.append(f"标清FLV${sd_flv}")
            if sd_m3u8:
                lines.append(f"标清HLS${sd_m3u8}")
            play_url = "#".join(lines) if lines else f"直播${hd_m3u8 or sd_m3u8 or hd_flv or sd_flv}"
            #_log("detail room=%s name=%s remarks=%s" % (room_num, vod_name[:40], remarks[:60]))
        else:
            vod_name = f"直播间 {room_num}"
            pic = ""
            play_url = f"直播$https://hwyypull.ncctrials.com/live/stream-{room_num}_lhd.m3u8"
            remarks = time.strftime("%m-%d %H:%M")
            #_log("detail room=%s NO STREAM" % room_num)
        vod = {
            "vod_id": vid, "vod_name": vod_name, "vod_pic": pic,
            "vod_remarks": remarks, "vod_content": "",
            "vod_play_from": "7zb",
            "vod_play_url": play_url
        }
        return {"code": 1, "page": 1, "pagecount": 1, "limit": 1, "total": 1, "list": [vod]}

    def searchContent(self, key, quick, pg="1"):
        self._ensure_session()
        items = []
        data = self._api_post("/live/hot", {"keyword": key, "page": int(pg) if pg else 1})
        if data:
            rooms = data.get("rooms", data.get("list", []))
            if isinstance(rooms, list):
                for room in rooms:
                    items.append(self._parse_room(room))
        return {"list": items, "page": int(pg) if pg else 1}

    def playerContent(self, flag, id, vipFlags):
        url = str(id or "")
        #_log("player id=%s" % url[:120])
        if url.startswith("http") and (".flv" in url or ".m3u8" in url):
            #_log("player direct=%s" % url[:120])
            return {"parse": 0, "url": url, "header": {"User-Agent": self.UA, "Referer": self.HOST + "/"}}
        room_num = ""
        if "roomNum=" in url:
            room_num = url.split("roomNum=")[-1].split("&")[0]
        elif re.match(r"^\d+$", url):
            room_num = url
        if room_num:
            stream = self._get_stream(room_num)
            if stream:
                play_url = stream.get("hdFlv") or stream.get("flv") or stream.get("hdM3u8") or stream.get("m3u8", "")
                if play_url:
                    #_log("player room=%s stream=%s" % (room_num, play_url[:120]))
                    return {"parse": 0, "url": play_url, "header": {"User-Agent": self.UA, "Referer": self.HOST + "/"}}
            fallback = f"https://hwyypull.ncctrials.com/live/stream-{room_num}_lhd.m3u8"
            #_log("player room=%s fallback=%s" % (room_num, fallback))
            return {"parse": 0, "url": fallback, "header": {"User-Agent": self.UA, "Referer": self.HOST + "/"}}
        #_log("player passthrough=%s" % url[:120])
        return {"parse": 0, "url": url, "header": {"User-Agent": self.UA, "Referer": self.HOST + "/"}}
