#!/usr/bin/env python3
# 菲利体育 V5.0 - AES解密直链播放（无噎探依赖）
import re, json, time, requests, struct, hashlib
from base.spider import Spider as BaseSpider
from base64 import b64encode, b64decode

HOST = "https://shutu16.com"
UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/140.0.0.0 Safari/537.36"

_SBOX = [0x63,0x7c,0x77,0x7b,0xf2,0x6b,0x6f,0xc5,0x30,0x01,0x67,0x2b,0xfe,0xd7,0xab,0x76,0xca,0x82,0xc9,0x7d,0xfa,0x59,0x47,0xf0,0xad,0xd4,0xa2,0xaf,0x9c,0xa4,0x72,0xc0,0xb7,0xfd,0x93,0x26,0x36,0x3f,0xf7,0xcc,0x34,0xa5,0xe5,0xf1,0x71,0xd8,0x31,0x15,0x04,0xc7,0x23,0xc3,0x18,0x96,0x05,0x9a,0x07,0x12,0x80,0xe2,0xeb,0x27,0xb2,0x75,0x09,0x83,0x2c,0x1a,0x1b,0x6e,0x5a,0xa0,0x52,0x3b,0xd6,0xb3,0x29,0xe3,0x2f,0x84,0x53,0xd1,0x00,0xed,0x20,0xfc,0xb1,0x5b,0x6a,0xcb,0xbe,0x39,0x4a,0x4c,0x58,0xcf,0xd0,0xef,0xaa,0xfb,0x43,0x4d,0x33,0x85,0x45,0xf9,0x02,0x7f,0x50,0x3c,0x9f,0xa8,0x51,0xa3,0x40,0x8f,0x92,0x9d,0x38,0xf5,0xbc,0xb6,0xda,0x21,0x10,0xff,0xf3,0xd2,0xcd,0x0c,0x13,0xec,0x5f,0x97,0x44,0x17,0xc4,0xa7,0x7e,0x3d,0x64,0x5d,0x19,0x73,0x60,0x81,0x4f,0xdc,0x22,0x2a,0x90,0x88,0x46,0xee,0xb8,0x14,0xde,0x5e,0x0b,0xdb,0xe0,0x32,0x3a,0x0a,0x49,0x06,0x24,0x5c,0xc2,0xd3,0xac,0x62,0x91,0x95,0xe4,0x79,0xe7,0xc8,0x37,0x6d,0x8d,0xd5,0x4e,0xa9,0x6c,0x56,0xf4,0xea,0x65,0x7a,0xae,0x08,0xba,0x78,0x25,0x2e,0x1c,0xa6,0xb4,0xc6,0xe8,0xdd,0x74,0x1f,0x4b,0xbd,0x8b,0x8a,0x70,0x3e,0xb5,0x66,0x48,0x03,0xf6,0x0e,0x61,0x35,0x57,0xb9,0x86,0xc1,0x1d,0x9e,0xe1,0xf8,0x98,0x11,0x69,0xd9,0x8e,0x94,0x9b,0x1e,0x87,0xe9,0xce,0x55,0x28,0xdf,0x8c,0xa1,0x89,0x0d,0xbf,0xe6,0x42,0x68,0x41,0x99,0x2d,0x0f,0xb0,0x54,0xbb,0x16]
_RCON = [0x01,0x02,0x04,0x08,0x10,0x20,0x40,0x80,0x1b,0x36]

def _xtime(a): return ((a<<1)^0x11b) if a&0x80 else a<<1
def _mul(a,b):
    r=0
    for _ in range(8):
        if b&1: r^=a
        a=_xtime(a)
        b>>=1
    return r

def _sub_bytes(s): return [_SBOX[b] for b in s]
def _shift_rows(s):
    return [s[0],s[5],s[10],s[15],s[4],s[9],s[14],s[3],s[8],s[13],s[2],s[7],s[12],s[1],s[6],s[11]]
def _mix_columns(s):
    r=[]
    for i in range(4):
        c=s[i*4:i*4+4]
        r+=[_mul(c[0],2)^_mul(c[1],3)^c[2]^c[3], c[0]^_mul(c[1],2)^_mul(c[2],3)^c[3], c[0]^c[1]^_mul(c[2],2)^_mul(c[3],3), _mul(c[0],3)^c[1]^c[2]^_mul(c[3],2)]
    return r

def _add_rk(s,rk): return [a^b for a,b in zip(s,rk)]

def _key_exp(key):
    w=list(key)
    for i in range(4,44):
        t=w[(i-1)*4:i*4]
        if i%4==0:
            t=[_SBOX[b] for b in [t[1],t[2],t[3],t[0]]]
            t[0]^=_RCON[i//4-1]
        w.extend(a^b for a,b in zip(w[(i-4)*4:(i-3)*4],t))
    return [w[i*16:(i+1)*16] for i in range(11)]

def _enc_block(block, rk):
    s=_add_rk(block, rk[0])
    for r in range(1,10):
        s=_sub_bytes(s)
        s=_shift_rows(s)
        s=_mix_columns(s)
        s=_add_rk(s, rk[r])
    s=_sub_bytes(s)
    s=_shift_rows(s)
    s=_add_rk(s, rk[10])
    return s

def _pkcs7_pad(data, bs=16):
    pad_len=bs-(len(data)%bs)
    return data+bytes([pad_len]*pad_len)

def _aes_cbc_encrypt(key, iv, plaintext):
    rk=_key_exp(key)
    ct=bytearray()
    prev=iv
    for i in range(0, len(plaintext), 16):
        block=bytes(a^b for a,b in zip(plaintext[i:i+16], prev))
        encrypted=bytes(_enc_block(list(block), rk))
        ct.extend(encrypted)
        prev=encrypted
    return bytes(ct)

def aes_encrypt(plaintext_str):
    key=b"this_is_aes_key!"
    iv=key[:16]
    data=_pkcs7_pad(plaintext_str.encode())
    return b64encode(_aes_cbc_encrypt(key, iv, data)).decode()

class Spider(BaseSpider):
    def getName(self): return "菲利体育"
    def init(self, extend=""):
        self.host = HOST
        self.headers = {
            "User-Agent": UA, "Referer": self.host + "/",
            "Accept": "application/json, text/plain, */*",
            "Accept-Language": "zh-CN,zh;q=0.9",
            "Origin": self.host, "Content-Type": "application/json",
        }
        self._token = None
        self._token_time = 0
        self._ensure_token()

    def _ensure_token(self):
        now = time.time()
        if self._token and (now - self._token_time) < 1800: return self._token
        try:
            r = requests.post(self.host + "/api/connect", headers=self.headers, json={}, timeout=10, verify=False)
            d = r.json()
            if d.get("code") == 0 and d.get("data", {}).get("token"):
                self._token = d["data"]["token"]
                self._token_time = now
                self.headers["token"] = self._token
                return self._token
        except: pass
        return None

    def _get(self, path):
        if not self._ensure_token(): return None
        try:
            r = requests.get(self.host + path, headers=self.headers, timeout=10, verify=False)
            d = r.json()
            if d.get("code") == 0: return d.get("data")
            if d.get("code") == 2:
                self._token = None
                self._ensure_token()
                r2 = requests.get(self.host + path, headers=self.headers, timeout=10, verify=False)
                d2 = r2.json()
                if d2.get("code") == 0: return d2.get("data")
        except: pass
        return None

    def _post(self, path, body):
        if not self._ensure_token(): return None
        try:
            r = requests.post(self.host + path, headers=self.headers, json=body, timeout=10, verify=False)
            d = r.json()
            if d.get("code") == 0: return d.get("data")
            if d.get("code") == 2:
                self._token = None
                self._ensure_token()
                r2 = requests.post(self.host + path, headers=self.headers, json=body, timeout=10, verify=False)
                d2 = r2.json()
                if d2.get("code") == 0: return d2.get("data")
        except: pass
        return None

    def _today(self): return time.strftime("%Y-%m-%d")

    def _encrypt_stream_token(self, stream_token):
        ts = int(time.time())
        return aes_encrypt(f"{stream_token}/{ts}")

    def _fetch_stream_url(self, stream_token):
        encrypted = self._encrypt_stream_token(stream_token)
        data = self._post("/api/v2/match-live-stream", {"stream_token": encrypted, "tv": 0})
        if data and isinstance(data, dict) and data.get("url"):
            return data["url"].strip()
        return None

    def _fetch_matches(self, date_str=None):
        data = self._get(f"/api/v2/match-on-date?date={date_str or self._today()}")
        if not data or not isinstance(data.get("list"), list): return []
        result = []
        for comp in data["list"]:
            cn, ci, ct, cl = comp.get("name",""), comp.get("id",0), comp.get("type",1), comp.get("logo","")
            for m in comp.get("match_list", []):
                m["_comp_name"]=cn; m["_comp_id"]=ci; m["_comp_type"]=ct; m["_comp_logo"]=cl
                result.append(m)
        return result

    def _parse_match(self, m):
        mid=str(m.get("id","")); ct=m.get("_comp_type",m.get("type",1)); ci=m.get("_comp_id",m.get("cid",0))
        home,away=m.get("host_team_name",""),m.get("away_team_name","")
        status,has_live=m.get("status",-1),m.get("has_live",0)
        league=m.get("_comp_name",m.get("competition_name",""))
        match_time, pic=m.get("match_time",""),m.get("host_team_logo","")
        dp,tp="",""
        if match_time:
            parts=match_time.split(" ")
            if len(parts)>=2: dp,tp=parts[0][5:],parts[1][:5]
            elif parts: tp=parts[0][:5]
        prefix="\U0001f7e2 " if status==0 and has_live else ("\u2705 " if status==2 else "\U0001f4c5 ")
        td=f"{dp} {tp}".strip() if dp and tp else (tp if tp else "")
        remarks=prefix+(f"{td} {league}".strip() if td and league else (league or td or "\u4f53\u80b2\u76f4\u64ad"))
        return {"vod_id":f"fl|{ct}|{ci}|{mid}","vod_name":f"{home} vs {away}","vod_pic":pic,"vod_remarks":remarks}

    def _is_hot(self, name):
        if not name: return False
        return any(k in name for k in ["\u4e16\u754c\u676f","\u4e2d\u8d85","\u82f1\u8d85","\u897f\u7532","\u5fb7\u7532","\u610f\u7532","\u6cd5\u7532","\u6b27\u51a0","\u6b27\u8054","NBA","WNBA","CBA"])

    def homeContent(self, f):
        matches=self._fetch_matches(); live=[self._parse_match(m) for m in matches if m.get("status")==0]
        return {"class":[{"type_id":"all","type_name":"\u5168\u90e8"},{"type_id":"live","type_name":"\U0001f7e2 \u76f4\u64ad\u4e2d"},{"type_id":"hot","type_name":"\U0001f525 \u70ed\u95e8"},{"type_id":"football","type_name":"\u26bd \u8db3\u7403"},{"type_id":"basketball","type_name":"\U0001f3c0 \u7bee\u7403"}],"list":live if live else [self._parse_match(m) for m in matches[:20]],"filters":{}}

    def _filter_matches(self, matches, tid):
        r=[]
        for m in matches:
            s,ct,lg=m.get("status",-1),m.get("_comp_type",1),m.get("_comp_name","")
            if tid=="live" and s!=0: continue
            if tid=="hot" and not self._is_hot(lg): continue
            if tid=="football" and ct!=1: continue
            if tid=="basketball" and ct!=2: continue
            r.append(self._parse_match(m))
        return r

    def categoryContent(self, tid, pg, filter, extend):
        tid=str((extend or {}).get("cateId") or tid or "all")
        f=self._filter_matches(self._fetch_matches(), tid)
        return {"page":1,"pagecount":1,"limit":200,"total":len(f),"list":f}

    def detailContent(self, ids):
        result={"list":[]}
        for vid in (ids if isinstance(ids,list) else [ids]):
            parts=str(vid).split("|")
            ct=int(parts[1]) if len(parts)>=4 else 1
            ci=int(parts[2]) if len(parts)>=4 else 0
            mid=int(parts[3]) if len(parts)>=4 else (int(parts[-1]) if parts[-1].isdigit() else 0)
            target=None
            for m in self._fetch_matches():
                if str(m.get("id"))==str(mid): target=dict(m); break
            dd=self._get(f"/api/v2/match-live/{ct}/{ci}/{mid}")
            if dd and isinstance(dd,dict):
                if not target: target={}
                target.update(dd)
                if dd.get("type"): ct=dd["type"]
                if dd.get("cid"): ci=dd["cid"]
            if not target: continue
            lives=target.get("lives",[])
            st=lives[0].get("stream_token") if lives and lives[0].get("stream_token") else None
            play_urls=[]
            if st:
                su=self._fetch_stream_url(st)
                if su: play_urls.append(f"\u83f2\u5229\u4f53\u80b2${su}")
                else: play_urls.append(f"\u83f2\u5229\u4f53\u80b2${self.host}/live/{st}")
            if not play_urls: play_urls.append(f"\u6682\u65e0\u4fe1\u53f7${self.host}")
            home,away=target.get("host_team_name","\u4e3b\u961f"),target.get("away_team_name","\u5ba2\u961f")
            league,match_time,pic=target.get("_comp_name",target.get("name","")),target.get("match_time",""),target.get("host_team_logo","")
            result["list"].append({"vod_id":vid,"vod_name":f"{home} vs {away}","vod_pic":pic,"vod_remarks":f"{league} {match_time}".strip(),"vod_play_from":"\u83f2\u5229\u4f53\u80b2","vod_play_url":"#".join(play_urls)})
        return result

    def searchContent(self, key, quick, pg="1"):
        kw=(key or "").strip().lower()
        if not kw: return {"list":[],"page":1}
        results=[]
        for m in self._fetch_matches():
            if kw in f"{m.get('host_team_name','')} {m.get('away_team_name','')} {m.get('_comp_name','')}".lower():
                results.append(self._parse_match(m))
        return {"list":results,"page":int(pg) if pg else 1}

    def playerContent(self, flag, id, vipFlags):
        url=id or ""
        header=json.dumps({"User-Agent":UA,"Referer":self.host+"/","Origin":self.host})
        if re.search(r"\.(m3u8|flv|mp4)(\?|$)",url,re.I): return {"parse":0,"url":url,"header":header}
        if url.startswith("http") or url.startswith("//"): return {"parse":0,"url":url,"header":header}
        return {"parse":1,"url":self.host,"header":header}

    def localProxy(self, param): return [200,"text/plain",b"",{}]
