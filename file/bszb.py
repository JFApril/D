#!/usr/bin/env python3
# 比赛直播 (bszb) V2.2 - 纯Python端内AES解密直链直出，直达真实FLV/M3U8流（parse=0无嗅探依赖）
import json, re, time, requests, hashlib
from base64 import b64decode
from base.spider import Spider as BaseSpider

API_HOST = "https://apc.x4w3s3i3i8n7p2m6w0.cc"
IM_API_HOST = "https://openim-php-api.qaek4a2wjx6bt.cc"
WEB_HOST = "https://m.bszb450.com"
UA = "Mozilla/5.0 (Linux; Android 10; K) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Mobile Safari/537.36"

SALT = "yKBm0pKLdVcGbnu4XGon13TsyBdEsjj3WVAzszpoqjn3BNmovLgzvcRTxD1Wey7QQ10kcov0b8e9oBi7jAUR"
AES_KEY = b"j3Qpq3BWs6qUCctm"
AES_IV = b"b2mdEEYbW1qprFsg"

_SBOX = [
    0x63,0x7c,0x77,0x7b,0xf2,0x6b,0x6f,0xc5,0x30,0x01,0x67,0x2b,0xfe,0xd7,0xab,0x76,
    0xca,0x82,0xc9,0x7d,0xfa,0x59,0x47,0xf0,0xad,0xd4,0xa2,0xaf,0x9c,0xa4,0x72,0xc0,
    0xb7,0xfd,0x93,0x26,0x36,0x3f,0xf7,0xcc,0x34,0xa5,0xe5,0xf1,0x71,0xd8,0x31,0x15,
    0x04,0xc7,0x23,0xc3,0x18,0x96,0x05,0x9a,0x07,0x12,0x80,0xe2,0xeb,0x27,0xb2,0x75,
    0x09,0x83,0x2c,0x1a,0x1b,0x6e,0x5a,0xa0,0x52,0x3b,0xd6,0xb3,0x29,0xe3,0x2f,0x84,
    0x53,0xd1,0x00,0xed,0x20,0xfc,0xb1,0x5b,0x6a,0xcb,0xbe,0x39,0x4a,0x4c,0x58,0xcf,
    0xd0,0xef,0xaa,0xfb,0x43,0x4d,0x33,0x85,0x45,0xf9,0x02,0x7f,0x50,0x3c,0x9f,0xa8,
    0x51,0xa3,0x40,0x8f,0x92,0x9d,0x38,0xf5,0xbc,0xb6,0xda,0x21,0x10,0xff,0xf3,0xd2,
    0xcd,0x0c,0x13,0xec,0x5f,0x97,0x44,0x17,0xc4,0xa7,0x7e,0x3d,0x64,0x5d,0x19,0x73,
    0x60,0x81,0x4f,0xdc,0x22,0x2a,0x90,0x88,0x46,0xee,0xb8,0x14,0xde,0x5e,0x0b,0xdb,
    0xe0,0x32,0x3a,0x0a,0x49,0x06,0x24,0x5c,0xc2,0xd3,0xac,0x62,0x91,0x95,0xe4,0x79,
    0xe7,0xc8,0x37,0x6d,0x8d,0xd5,0x4e,0xa9,0x6c,0x56,0xf4,0xea,0x65,0x7a,0xae,0x08,
    0xba,0x78,0x25,0x2e,0x1c,0xa6,0xb4,0xc6,0xe8,0xdd,0x74,0x1f,0x4b,0xbd,0x8b,0x8a,
    0x70,0x3e,0xb5,0x66,0x48,0x03,0xf6,0x0e,0x61,0x35,0x57,0xb9,0x86,0xc1,0x1d,0x9e,
    0xe1,0xf8,0x98,0x11,0x69,0xd9,0x8e,0x94,0x9b,0x1e,0x87,0xe9,0xce,0x55,0x28,0xdf,
    0x8c,0xa1,0x89,0x0d,0xbf,0xe6,0x42,0x68,0x41,0x99,0x2d,0x0f,0xb0,0x54,0xbb,0x16
]

_INV_SBOX = [0] * 256
for _i, _v in enumerate(_SBOX):
    _INV_SBOX[_v] = _i

_RCON = [0x01,0x02,0x04,0x08,0x10,0x20,0x40,0x80,0x1b,0x36]

def _xtime(a):
    return ((a << 1) ^ 0x11b) if (a & 0x80) else (a << 1)

def _mul(a, b):
    r = 0
    for _ in range(8):
        if b & 1:
            r ^= a
        a = _xtime(a)
        b >>= 1
    return r

def _inv_shift_rows(s):
    return [s[0], s[13], s[10], s[7], s[4], s[1], s[14], s[11], s[8], s[5], s[2], s[15], s[12], s[9], s[6], s[3]]

def _inv_sub_bytes(s):
    return [_INV_SBOX[b] for b in s]

def _inv_mix_columns(s):
    r = []
    for i in range(4):
        c = s[i*4:i*4+4]
        r += [
            _mul(c[0], 0x0e) ^ _mul(c[1], 0x0b) ^ _mul(c[2], 0x0d) ^ _mul(c[3], 0x09),
            _mul(c[0], 0x09) ^ _mul(c[1], 0x0e) ^ _mul(c[2], 0x0b) ^ _mul(c[3], 0x0d),
            _mul(c[0], 0x0d) ^ _mul(c[1], 0x09) ^ _mul(c[2], 0x0e) ^ _mul(c[3], 0x0b),
            _mul(c[0], 0x0b) ^ _mul(c[1], 0x0d) ^ _mul(c[2], 0x09) ^ _mul(c[3], 0x0e)
        ]
    return r

def _add_rk(s, rk):
    return [a ^ b for a, b in zip(s, rk)]

def _key_exp(key):
    w = list(key)
    for i in range(4, 44):
        t = w[(i-1)*4:i*4]
        if i % 4 == 0:
            t = [_SBOX[b] for b in [t[1], t[2], t[3], t[0]]]
            t[0] ^= _RCON[i // 4 - 1]
        w.extend(a ^ b for a, b in zip(w[(i-4)*4:(i-3)*4], t))
    return [w[i*16:(i+1)*16] for i in range(11)]

def _dec_block(block, rk):
    s = _add_rk(block, rk[10])
    for r in range(9, 0, -1):
        s = _inv_shift_rows(s)
        s = _inv_sub_bytes(s)
        s = _add_rk(s, rk[r])
        s = _inv_mix_columns(s)
    s = _inv_shift_rows(s)
    s = _inv_sub_bytes(s)
    s = _add_rk(s, rk[0])
    return s

def _aes_cbc_decrypt(key, iv, ciphertext):
    rk = _key_exp(key)
    pt = bytearray()
    prev = iv
    for i in range(0, len(ciphertext), 16):
        cur_ct = ciphertext[i:i+16]
        dec = bytes(_dec_block(list(cur_ct), rk))
        pt.extend(bytes(a ^ b for a, b in zip(dec, prev)))
        prev = cur_ct
    if pt:
        pad_len = pt[-1]
        if 0 < pad_len <= 16:
            pt = pt[:-pad_len]
    return bytes(pt)

def decrypt_play_data(b64_str):
    try:
        raw_ct = b64decode(b64_str.strip('" \n\r\t'))
        dec_bytes = _aes_cbc_decrypt(AES_KEY, AES_IV, raw_ct)
        return json.loads(dec_bytes.decode('utf-8'))
    except Exception:
        return None

def make_signature(params):
    sorted_keys = sorted(params.keys())
    s = "".join(f"{k}{params[k]}" for k in sorted_keys if params[k] is not None and k != "signature")
    s += SALT
    return hashlib.md5(s.encode('utf-8')).hexdigest()


class Spider(BaseSpider):
    def getName(self):
        return "比赛直播"

    def init(self, extend=""):
        self.api_host = API_HOST
        self.im_api_host = IM_API_HOST
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
                return d.get("data") if d.get("code") in [200, 0, "200", "0"] else d
        except Exception:
            pass
        return None

    def _fetch_stream_url(self, room_id, match_id="0", sport_id="0", code_id="gqzm"):
        try:
            now_ts = int(time.time())
            params = {
                "room_id": str(room_id),
                "code_id": code_id,
                "time": now_ts
            }
            if str(room_id) == "888888888":
                params["match_id"] = int(match_id)
                params["sport_id"] = int(sport_id)
            params["signature"] = make_signature(params)

            headers = {
                "Content-Type": "application/x-www-form-urlencoded",
                "platform": "bszb",
                "version": "1.4.1",
                "device": "4",
                "api-version": "8",
                "imei": "864567041234567",
                "User-Agent": UA,
                "Origin": self.web_host,
                "Referer": self.web_host + "/",
            }
            r = requests.post(f"{self.im_api_host}/v230/play/url", data=params, headers=headers, timeout=6, verify=False)
            if r.status_code == 200 and r.text:
                dec = decrypt_play_data(r.text)
                if isinstance(dec, dict) and dec.get("code") == 200:
                    stream_url = dec.get("data", {}).get("play_url")
                    if stream_url:
                        return stream_url
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

    def _parse_match_item(self, m):
        if not isinstance(m, dict):
            return None
        mid = m.get("match_id")
        if not mid:
            return None
        sport_id = m.get("sport_id", 0)
        home = m.get("home_name", "").strip()
        away = m.get("away_name", "").strip()
        
        hs = self._format_score(m.get("home_score"))
        as_ = self._format_score(m.get("away_score"))
        
        m_status = int(m.get("match_status") or 1)
        m_time = int(m.get("match_time") or 0)
        now_ts = int(time.time())
        
        is_live = (m_status in [2, 3, 4, 5, 7, 8]) and (m_time <= now_ts + 600)
        if m_status == 1 or m_time > now_ts + 600:
            is_live = False

        if home and away:
            if is_live and hs is not None and as_ is not None:
                title = f"{home} {hs}:{as_} {away}"
            else:
                title = f"{home} VS {away}"
        else:
            title = m.get("alias_name") or f"比赛 {mid}"

        alias = m.get("alias_name", "")
        m_date = m.get("match_date", "")
        time_str = m.get("match_hour") or (m_date[11:16] if len(m_date) >= 16 else "")
        status_txt = "🔴 直播中" if is_live else "📅 预告"
        
        anchors = m.get("anchor_list") or []
        anchor_txt = f"{len(anchors)}个主播" if anchors else ""

        remarks_parts = [p for p in [status_txt, time_str, alias, anchor_txt] if p]
        remarks = " | ".join(remarks_parts) if remarks_parts else "比赛直播"

        pic = m.get("home_logo") or m.get("away_logo") or ""
        return {
            "vod_id": f"{mid}_{sport_id}",
            "vod_name": title,
            "vod_pic": pic,
            "vod_remarks": remarks,
        }

    def homeContent(self, filter):
        classes = [
            {"type_id": "0", "type_name": "全部"},
            {"type_id": "1", "type_name": "⚽ 足球"},
            {"type_id": "2", "type_name": "🏀 篮球"},
            {"type_id": "101", "type_name": "🎮 英雄联盟"},
            {"type_id": "102", "type_name": "⚔️ 王者荣耀"},
            {"type_id": "103", "type_name": "🔫 CS:GO"},
            {"type_id": "104", "type_name": "🛡️ DOTA2"},
        ]
        data = self._get("/h5/v14/matchs", {"sport_id": 0, "page": 1, "size": 50})
        matches = []
        if isinstance(data, list):
            for day in data:
                if isinstance(day, dict):
                    raw_list = day.get("match_list") or []
                    for item in raw_list:
                        p = self._parse_match_item(item)
                        if p:
                            matches.append(p)
        return {"class": classes, "list": matches, "filters": {}}

    def categoryContent(self, tid, pg, filter, extend):
        page = int(pg) if str(pg).isdigit() else 1
        sport_id = str((extend or {}).get("cateId") or tid or "0")
        data = self._get("/h5/v14/matchs", {"sport_id": sport_id, "page": page, "size": 50})
        result_list = []
        if isinstance(data, list):
            for day in data:
                if isinstance(day, dict):
                    raw_list = day.get("match_list") or []
                    for item in raw_list:
                        p = self._parse_match_item(item)
                        if p:
                            result_list.append(p)
        total = len(result_list)
        return {
            "page": page,
            "pagecount": page + (1 if total >= 50 else 0),
            "limit": 50,
            "total": total,
            "list": result_list,
        }

    def detailContent(self, ids):
        raw_id = ids[0] if isinstance(ids, list) and ids else str(ids)
        parts = raw_id.split("_")
        mid = parts[0]
        sport_id = parts[1] if len(parts) > 1 else "0"

        room_data = self._get("/h5/v13/room", {"room_id": "888888888", "match_id": mid, "sport_id": sport_id})
        match_info = {}
        title = "比赛直播"
        pic = ""
        badge = ""
        if isinstance(room_data, dict):
            match_info = room_data.get("match_info") or {}
            title = room_data.get("room_title") or f"{match_info.get('home_name', '')} VS {match_info.get('away_name', '')}".strip() or "比赛直播"
            badge = match_info.get("alias_name", "")
            pic = match_info.get("screenshot_url") or match_info.get("home_logo") or ""

        play_from_list = []
        play_url_list = []

        live_data = self._get("/h5/v13/match/live", {"match_id": mid, "sport_id": sport_id})
        has_rooms = False
        if isinstance(live_data, list) and live_data:
            for r_item in live_data:
                if not isinstance(r_item, dict):
                    continue
                r_id = r_item.get("chatroom_id") or r_item.get("room_id")
                r_title = r_item.get("user_nickname") or r_item.get("room_title") or "直播"
                if r_id:
                    has_rooms = True
                    group_name = "官方原画" if str(r_id) == "888888888" else f"主播-{r_title}"
                    play_from_list.append(group_name)
                    play_url_list.append(f"高清直链$stream://{r_id}_{mid}_{sport_id}")

        if not has_rooms:
            play_from_list.append("官方原画")
            play_url_list.append(f"原声直链$stream://888888888_{mid}_{sport_id}")

        vod = {
            "vod_id": raw_id,
            "vod_name": title,
            "vod_pic": pic,
            "vod_remarks": badge,
            "vod_content": f"赛事: {badge} | 时间: {match_info.get('match_time', '')}",
            "vod_play_from": "$$$".join(play_from_list),
            "vod_play_url": "$$$".join(play_url_list),
        }
        return {"list": [vod]}

    def searchContent(self, key, quick, pg="1"):
        kw = (key or "").strip().lower()
        if not kw:
            return {"list": [], "page": 1}
        page = int(pg) if str(pg).isdigit() else 1
        data = self._get("/h5/v14/matchs", {"sport_id": 0, "page": page, "size": 50})
        matches = []
        if isinstance(data, list):
            for day in data:
                if isinstance(day, dict):
                    for item in day.get("match_list") or []:
                        parsed = self._parse_match_item(item)
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
        
        if url.startswith("stream://"):
            raw_target = url[9:]
            p_parts = raw_target.split("_")
            r_id = p_parts[0]
            m_id = p_parts[1] if len(p_parts) > 1 else "0"
            s_id = p_parts[2] if len(p_parts) > 2 else "0"
            
            stream_url = self._fetch_stream_url(r_id, m_id, s_id, "gqzm")
            if not stream_url:
                stream_url = self._fetch_stream_url(r_id, m_id, s_id, "bqzm")
            if not stream_url:
                stream_url = self._fetch_stream_url(r_id, m_id, s_id, "lgzm")
                
            if stream_url:
                return {"parse": 0, "url": stream_url, "header": header}
            
            fallback_web = f"{self.web_host}/broadcast/details?room_id={r_id}&match_id={m_id}&sport_id={s_id}"
            return {"parse": 1, "url": fallback_web, "header": header}

        if re.search(r"\.(m3u8|flv|mp4)(\?|$)", url, re.I):
            return {"parse": 0, "url": url, "header": header}
        return {"parse": 1, "url": url, "header": header}

    def localProxy(self, param):
        return [200, "text/plain", b"", {}]
