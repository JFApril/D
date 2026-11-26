#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
云帧享（com.youkevideo.app）TVBox 源
================================================================
目标 APP：com.youkevideo.app 3.2.0（与「乐逗视频」同源同模板的兄弟租户）
本文件：TVBox / FongMi / 影视仓 通用 Python 爬虫源（class Spider，零第三方依赖）

★ 与乐逗源的关系（判族结论）
  · 同模板、同 CDN、同协议：配置走 https://ss.trgfd.cn/cache/index/<pkg>.json
  · 内容池/vid/ji 与乐逗完全共享（乐逗源实测：换 baoming 到云帧享即出真链）
  · 差别只在 **租户身份**：本源 PKG = com.youkevideo.app，apiKey 用云帧享自己的
    32 位串，vuk 签名 = md5(str(sid) + 云帧享KEY)，播放 baoming = 自己的包名。
    → 播放不再跨租户（乐逗源因自身播放门 10405/10306 才借道云帧享）。

★ 协议来源（真机脱壳 + 实测校验，非猜测）
  · 配置：GET https://ss.trgfd.cn/cache/index/com.youkevideo.app.json
          实测：textURL = otherURL = https://js.trgfd.cn
                resourceURL = https://img.zqykfz.cn
                channels = [首页, 剧集, 电影, 综艺, 动漫, 少儿, 纪录片]
                ranks    = [热播榜, 飙升榜, 热搜榜, 新片榜, 剧集, 电影, 综艺, 动漫, 少儿, 纪录片]
                xinRanks = 热播/热搜/飙升/新片/高分 × [全部, 大陆剧, 美剧, 韩剧, 英剧,
                          泰剧, 日剧, 台剧, 港剧, 电影, 国内综艺, 国外综艺, 国漫, 日漫, 少儿, 纪录片]
  · 首页模块：GET {base}/cache/channel/首页.json
  · 榜单分页：GET {base}/cache/xinrank/<榜名>/<类型>/<页>.json   （1 起，每页 10 条）
  · 筛选表：GET {base}/cache/filterOptions/filter.json
            （本租户实测**完整下发** type/region/year，少儿另有 nianling + xilie）
  · 搜索：  GET {base}/vc/api/search/?keyword=<kw>            （返回数组，50 条）
  · 详情：  GET {base}/cache/videos/<vid>.json  → AES-256-GCM(DETAIL_KEY) 密文，
            Base64 → iv=前12B, ct=其余, GCM 128bit-tag；解出 playUrlList
            每集自带 ji 编号（★ 新版服务端只认 isjiid=1 + ji=<编号>）
  · 播放：  GET {base}/vc/api/video/playurl?sid=<vid>&ji=<编号>&jiIndex=<0基序号>&t=0&y=0
                 &isjiid=1&androidId=<deviceCode>&newDeviceCode=<newDeviceCode>
                 &modelName=<机型>&b=<令牌>&version=3.2.0&baoming=com.youkevideo.app
                 &channel=fenxiang
             Header: vuk = md5( str(sid) + KEY )
             返回 data.url = m3u8 直链（带 sign & t 防盗链参数）
  · 设备注册：POST {base}/vc/api/device/isnew（App SplashActivity 同款字段）
              POST {base}/vc/api/device/check（打卡）
              POST {base}/vc/api/getadjson（播放前武装，与 App 会话形状一致）

★ 铁律（沿用乐逗源踩坑固化，逐条保留）
   1) 判族优先：此为「内容走 CDN 静态 JSON + 播放走 API 签名」的短剧型 App，
      不属 V6/V7 面板族；先看它请求什么，再决定写什么。
   2) 分页参数在路径里（/1.json,/2.json），不是 query。
   3) ji 是**每集独立编号**（isjiid=1），0 基序号只作为 jiIndex 与兜底。
   4) 签名只对 sid 做：vuk=md5(sid+KEY)。别把全部参数串进去。
   5) 交付形态必须是 class Spider，不是 CLI。
   6) 【集数】优先用详情 playUrlList 长度；回落时解析 newchapter/serialDesc 文本，
      且**只认紧跟在 集/话/期 后面的数字**——否则综艺的更新日期 "20261008"
      会被当集数（参考版就有这个坑，会算出 2000 万集）。
   7) 【播放 id】集号分隔必须用 `@`，**绝不能用 `|`**：影视仓/TVBox 会把 `|` 之后
      当作 header/播放器标志截掉，`43157|0` 只剩 `43157` → 恒播第 1 集。
   8) 【设备身份】播放成败的真正开关：随机新设备会被服务器回**占位广告片**
      v.trgfd.cn/66.m3u8（code 10301，还不报错）；用 App 真机 deviceCode+
      newDeviceCode+b（见 DEFAULT_DEV / PHONE_DEV）即可直出真链，且**免注册**
      （注册接口 vc/api/device/isnew 有 IP 限流 429）。
   9) 【分类】内容是 CDN **预生成静态 json**：某些筛选组合根本没生成，
      命中空必须逐级回退，否则列表空白。
  10) 【筛选必须生效】zhaopian 返回加密数据、静态解不开，所以分类改走明文榜单
      xinrank：排序→切榜（最热/最新/评分→热播榜/新片榜/高分榜）；类型/地区→
      优先映射榜单第二维（大陆剧/美剧/…/国内综艺/国漫/…），映射不上走客户端
      过滤（class/region/year 字段，最多扫 60 条）；筛空则逐级放宽兜底。
  11) 【集数过期自愈】vod_id 里打包 ts；详情页打开时若元数据超过 24h（或无 ts
      的旧数据），按片名搜最新条目刷新集数并重打包（历史记录自动痊愈）。

对接 sites：
  {"key":"云帧享","name":"云帧享","type":3,"api":"./云帧享.py",
   "searchable":1,"quickSearch":1,"filterable":1,"ext":{}}
"""

import base64
import os
import hashlib
import json
import re
import urllib.parse
import urllib.request

try:
    from base.spider import Spider as BaseSpider
except Exception:
    class BaseSpider(object):
        def __init__(self, *a, **k):
            pass

        def fetch(self, url, headers=None, timeout=10):
            return _http_get(url, headers, timeout)

        def getProxyUrl(self, *a, **k):
            return ""


# ============================================================================
# 常量（实测值）
# ============================================================================
PKG = "com.youkevideo.app"
UA = "QingmanLslandApp/1.0"
# 云帧享租户 apiKey（32 位）：vuk 签名盐 + 播放响应 GCM 解密钥
KEY = "8uiju6talkolp98lll7VH7yuDxih7ujh"
# App 常量 a8.a.c：/cache/videos 详情解密钥
DETAIL_KEY = "JPT5fjptd0qi1TZZxu53cA7XI2TvQkol"
# 播放租户 = 自身（本源不再跨租户；乐逗源才因播放门借道云帧享）
PLAY_PKG = PKG
PLAY_KEY = KEY
MODEL = "HONOR AGT-AN00"          # 注册与播放统一的机型串（两次必须一致）
DIAG_TAG = "yzx320v1"
PLAY_UA = "okhttp/4.12.0"         # App 的 OkHttp 默认 UA（详情/播放请求用）
VER = "3.3.0"
CHANNEL = "fenxiang"
# 设备令牌 b 失配时服务端**不报错**，只回这个广告占位片 —— 必须显式识别
PLAY_PLACEHOLDER = "v.trgfd.cn/66.m3u8"
_DEV = {}

try:
    _DEV_CACHE = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                              "yzx_dev.json")
except Exception:
    _DEV_CACHE = "yzx_dev.json"

BASE = "https://js.trgfd.cn"                       # apiUrl.otherURL（实测）
CFG_URLS = [
    "https://ss.trgfd.cn/cache/index/%s.json" % PKG,
    "https://ss.dcggffw.top/cache/index/%s.json" % PKG,
]
# 频道（= App 顶部导航，与配置 channels 一致；推荐走首页模块）
CHANNELS = ["剧集", "电影", "综艺", "动漫", "少儿", "纪录片"]
# 每个频道在 URL 里的层级槽位（值 None = 固定"全部"）。
# ⚠ 各频道层数不同：常规频道 3 层（类型/地区/年代），少儿多两层（年龄/系列）
CHANNEL_SLOTS = {
    "剧集": ["type", "region", "year"],
    "电影": ["type", "region", "year"],
    "综艺": ["type", "region", "year"],
    "动漫": ["type", "region", "year"],
    "纪录片": ["type", "region", "year"],
    "少儿": ["type", None, "year", "nianling", "xilie"],
}
FILTER_NAMES = {"type": "类型", "region": "地区", "year": "年代",
                "nianling": "年龄", "xilie": "系列"}
# 榜单（App 的"榜单"页；与频道不同的另一套源）
RANKS = ["热播榜", "热搜榜", "飙升榜", "新片榜", "高分榜"]
# 频道 → 榜单接口可用的类型名（zhaopian 某些筛选组合在 CDN 未预生成时兜底用）
CH_RANK_TYPE = {"剧集": "大陆剧", "电影": "电影", "综艺": "国内综艺",
                "动漫": "国漫", "少儿": "少儿", "纪录片": "纪录片"}
_RANK_TYPE_LIST = ["全部", "大陆剧", "美剧", "韩剧", "英剧", "泰剧", "日剧", "台剧",
                   "港剧", "电影", "国内综艺", "国外综艺", "国漫", "日漫", "少儿", "纪录片"]
RANK_TYPES = {r: list(_RANK_TYPE_LIST) for r in RANKS}
XINRANK_TYPES = set(_RANK_TYPE_LIST)
# 排序 → 榜单（筛选"排序"实际切换榜单；三榜实测皆明文可用，每页 10 条）
SORT_RANK = {"最热": "热播榜", "最新": "新片榜", "评分": "高分榜"}
# 地区 → 榜单类型（榜单第二维是粗粒度；能命中就直接走榜单维度，比客户端过滤更准）
REGION_RANK = {
    "剧集": {"大陆": "大陆剧", "美国": "美剧", "韩国": "韩剧", "英国": "英剧",
             "泰国": "泰剧", "日本": "日剧", "台湾": "台剧", "香港": "港剧"},
    "综艺": {"大陆": "国内综艺"},
    "动漫": {"大陆": "国漫", "日本": "日漫"},
}
# filter.json 在本租户**完整下发** region/year，下面仅作兜底
FILTER_REGIONS = ["全部", "大陆", "香港", "台湾", "美国", "日本", "韩国", "泰国",
                  "英国", "法国", "印度", "其他"]
FILTER_YEARS = ["全部", "2026", "2025", "2024", "2023", "2022", "2021", "2020",
                "2019", "2018", "2017", "2016", "2015", "2014", "2013", "更早"]
FILTER_NIANLING = ["全部", "0-1", "2-3", "4-6", "7-10", "11-14"]
FILTER_XILIE = ["全部", "小猪佩奇", "汪汪队", "猪猪侠", "喜羊羊与灰太狼", "超级飞侠",
                "猫和老鼠", "海绵宝宝", "小马宝莉", "迷你特攻队", "托马斯", "芭比"]
# 客户端过滤时最多扫描的榜单条数（10 条/页 → 最多 6 页），控制筛选翻页延迟
FILTER_SCAN_MAX = 60

# ★ 集数兜底：接口的 total/serial 在部分条目为 None/0，真实集数写在
#   newchapter / serialDesc（如 "全24集" / "更新至15集"）。
#   ⚠ 必须要求数字后跟 集/话/期 单位 —— 否则 "20261008"（综艺更新日期）
#     会被当集数（参考版就有这个坑）。
_EP_RE = re.compile(r"(\d+)\s*[集話话期]")
# 播放 id 用 @ 分隔（绝不用 | ：影视仓会截掉 | 后面的内容，导致永远第 1 集）
SEP = "@"

# ★★ App 真机设备身份。实测：deviceCode+newDeviceCode 用 App 这套真值，
#   即使 b 为空也能取到真直链；而"随机生成的新设备"会被服务器回占位广告片
#   （v.trgfd.cn/66.m3u8, code 10301）。默认直接用真机身份，不依赖限流注册。
PHONE_DEV = {
    # 用户本机云帧享 App 的真实身份（HttpCanary 抓包 getadjson 请求体实锤）
    "deviceCode": "db59fff7a05bc2d0",
    "newDeviceCode": "006294042338",
    "b": "f99b9dfe3c8acb4d2e78175397c64b43261a97fa5739af93f51aeb02c1e218b0",
}
DEFAULT_DEV = {
    # 公开种子（旧源作者真机身份，uid 2530783）——仅作最后兜底
    "deviceCode": "1db12ef7dde7cdf8",
    "newDeviceCode": "022253078369",
    "b": "198323d38641129c1b380c152765af09697ad56abce7b52d4ca116fd17644642",
}

PROXY_PREFIX = "http://127.0.0.1:9978/proxy?do=py&action=proxy&type=cover&url="


# ============================================================================
# 纯 Python AES-256-GCM 解密（零依赖；用于详情与偶发的加密响应）
# ============================================================================
class _AES(object):
    """仅需 AES 加密（GCM 的 CTR + GHASH 都基于分组加密）。"""

    def __init__(self, key):
        self._ks = self._expand(key)
        self._nk = len(key) // 4
        self._nr = self._nk + 6

    @staticmethod
    def _sbox():
        p = q = 1
        sbox = [0] * 256
        while True:
            p = p ^ ((p << 1) & 0xFF) ^ (0x1B if p & 0x80 else 0)
            q ^= (q << 1) & 0xFF
            q ^= (q << 2) & 0xFF
            q ^= (q << 4) & 0xFF
            q &= 0xFF
            if q & 0x80:
                q ^= 0x09
            q &= 0xFF
            x = q ^ ((q << 1) | (q >> 7)) ^ ((q << 2) | (q >> 6)) \
                ^ ((q << 3) | (q >> 5)) ^ ((q << 4) | (q >> 4))
            sbox[p] = (x ^ 0x63) & 0xFF
            if p == 1:
                break
        sbox[0] = 0x63
        return sbox

    def _expand(self, key):
        sbox = _AES._SBOX
        nk = len(key) // 4
        nr = nk + 6
        w = [list(key[4 * i:4 * i + 4]) for i in range(nk)]
        rcon = 1
        for i in range(nk, 4 * (nr + 1)):
            t = list(w[i - 1])
            if i % nk == 0:
                t = t[1:] + t[:1]
                t = [sbox[b] for b in t]
                t[0] ^= rcon
                rcon = ((rcon << 1) ^ (0x1B if rcon & 0x80 else 0)) & 0xFF
            elif nk > 6 and i % nk == 4:
                t = [sbox[b] for b in t]
            w.append([w[i - nk][j] ^ t[j] for j in range(4)])
        return w

    def encrypt_block(self, block):
        """标准 AES 分组加密（state 为列主序的 16 字节扁平数组）。"""
        sbox = _AES._SBOX
        ks, nr = self._ks, self._nr
        s = list(block)

        def xt(a):
            return ((a << 1) ^ 0x1B) & 0xFF if a & 0x80 else (a << 1) & 0xFF

        def add_rk(r):
            rk = b"".join(bytes(x) for x in ks[r * 4:r * 4 + 4])
            for i in range(16):
                s[i] ^= rk[i]

        add_rk(0)
        for rnd in range(1, nr):
            for i in range(16):
                s[i] = sbox[s[i]]
            t = list(s)
            for c in range(4):                 # ShiftRows
                for r in range(4):
                    s[4 * c + r] = t[4 * ((c + r) % 4) + r]
            for c in range(4):                 # MixColumns
                a0, a1, a2, a3 = s[4 * c:4 * c + 4]
                s[4 * c + 0] = xt(a0) ^ (xt(a1) ^ a1) ^ a2 ^ a3
                s[4 * c + 1] = a0 ^ xt(a1) ^ (xt(a2) ^ a2) ^ a3
                s[4 * c + 2] = a0 ^ a1 ^ xt(a2) ^ (xt(a3) ^ a3)
                s[4 * c + 3] = (xt(a0) ^ a0) ^ a1 ^ a2 ^ xt(a3)
            add_rk(rnd)
        for i in range(16):
            s[i] = sbox[s[i]]
        t = list(s)
        for c in range(4):
            for r in range(4):
                s[4 * c + r] = t[4 * ((c + r) % 4) + r]
        add_rk(nr)
        return bytes(s)


_AES._SBOX = _AES._sbox()


def _ghash(h, data):
    def mul(x, y):
        z, v = 0, y
        for i in range(127, -1, -1):
            if (x >> i) & 1:
                z ^= v
            if v & 1:
                v = (v >> 1) ^ (0xE1 << 120)
            else:
                v >>= 1
        return z
    y = 0
    for i in range(0, len(data), 16):
        blk = data[i:i + 16].ljust(16, b"\x00")
        y = mul(y ^ int.from_bytes(blk, "big"), h)
    return y


def aes_gcm_decrypt(key, iv, ct, aad=b""):
    """AES-GCM 解密（ct 含 16 字节 tag）。失败抛异常。"""
    aes = _AES(key)
    h = int.from_bytes(aes.encrypt_block(b"\x00" * 16), "big")
    if len(iv) == 12:
        j0 = iv + b"\x00\x00\x00\x01"
    else:
        j0 = int.from_bytes(iv, "big").to_bytes(16, "big")
    body, tag = ct[:-16], ct[-16:]
    out = bytearray()
    ctr = int.from_bytes(j0, "big")
    for i in range(0, len(body), 16):
        ks = aes.encrypt_block((ctr + 1 + i // 16).to_bytes(16, "big"))
        blk = body[i:i + 16]
        out += bytes(a ^ b for a, b in zip(blk, ks))
    lb = (len(aad) * 8).to_bytes(8, "big") + (len(body) * 8).to_bytes(8, "big")
    pad_a = aad + b"\x00" * (-len(aad) % 16)
    pad_c = body + b"\x00" * (-len(body) % 16)
    s = _ghash(h, pad_a + pad_c + lb)
    real = int.from_bytes(aes.encrypt_block(j0), "big") ^ s
    if real.to_bytes(16, "big") != tag:
        raise ValueError("gcm tag mismatch")
    return bytes(out)


def maybe_decrypt(key, body):
    """按 App 侧逻辑：Base64 → 前12B iv → GCM；失败返回原文。"""
    if not body or body[:1] in "[{":
        return body
    try:
        raw = base64.b64decode(body.strip(), validate=False)
        if len(raw) < 28:
            return body
        return aes_gcm_decrypt(key.encode("utf-8"), raw[:12], raw[12:]).decode("utf-8")
    except Exception:
        return body


def _dec_json(key, body):
    """严格解密 + JSON（失败返回 None），用于 /cache/videos 详情。"""
    try:
        raw = base64.b64decode((body or "").strip(), validate=False)
        if len(raw) < 28:
            return None
        txt = aes_gcm_decrypt(key.encode("utf-8"), raw[:12], raw[12:]).decode("utf-8")
        return json.loads(txt)
    except Exception:
        return None


# ============================================================================
# HTTP
# ============================================================================
def _http_get(url, headers=None, timeout=12):
    h = {
        "User-Agent": UA,
        "Accept": "*/*",
        "Accept-Encoding": "identity",
        "Connection": "keep-alive",
    }
    if headers:
        h.update(headers)
    req = urllib.request.Request(url, headers=h, method="GET")
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.read()


def _jget(url, headers=None, timeout=12):
    raw = _http_get(url, headers, timeout)
    txt = raw.decode("utf-8", "ignore")
    try:
        return json.loads(txt)
    except Exception:
        d = maybe_decrypt(KEY, txt)
        try:
            return json.loads(d)
        except Exception:
            return None


def _http_post_json(url, obj, timeout=12):
    data = json.dumps(obj, ensure_ascii=False).encode("utf-8")
    req = urllib.request.Request(url, data=data, method="POST", headers={
        "User-Agent": UA,
        "Content-Type": "application/json; charset=utf-8",
        "Accept": "*/*",
        "Accept-Encoding": "identity",
    })
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read().decode("utf-8", "ignore"))


def vuk_of(sid):
    """播放签名：md5(str(sid) + PLAY_KEY)。只对 sid 做，别把全部参数串进去。"""
    return hashlib.md5((str(sid) + PLAY_KEY).encode("utf-8")).hexdigest()


def _q(s):
    return urllib.parse.quote(str(s))


def _ep_count(it):
    """推断总集数（详情页拉不到 playUrlList 时的兜底）。

    优先级：total/serial（有就用）→ newchapter/serialDesc/remarks 文本里的
    "全N集"/"更新至N集"/"共N期" → 0（未知，调用方按 1 集处理）。
    只认数字后紧跟 集/话/期 的，避免把日期 "20261008" 当成集数。
    """
    for k in ("total", "serial"):
        try:
            v = int((it or {}).get(k) or 0)
        except Exception:
            v = 0
        if v > 0:
            return v
    for k in ("newchapter", "serialDesc", "remarks", "jibeizhushow"):
        nums = _EP_RE.findall(str((it or {}).get(k) or ""))
        if nums:                 # "第1-24集" 只匹配到紧邻"集"的 24，取最后一个即最大值
            try:
                v = int(nums[-1])
            except Exception:
                v = 0
            if v > 0:
                return v
    return 0


# ============================================================================
# Spider
# ============================================================================
class Spider(BaseSpider):

    def __init__(self):
        self.base = BASE
        self.res_base = "https://img.zqykfz.cn"
        self.ext_root = {}
        self.last_error = ""
        self._fdef = None          # filter.json 解析缓存
        self._rank_cache = {}      # (榜, 类型, 页) → 原始条目列表；筛选翻页复用
        self._dbg_last = ""
        # 设备身份：默认用用户本机 App 的真实身份（免注册、直出真链）
        self.dev = dict(PHONE_DEV)
        self._ident_ready = False   # 本进程是否已做过 isnew 刷新+打卡

    def getName(self):
        return "云帧享"

    def getDependence(self):
        """部分壳（默影视等）启动时会探测 getDependence，缺了整源被跳过。"""
        return []

    def __getattr__(self, name):
        """壳探测未知方法（getHomeContent 等别名）时给安全 stub，避免
        AttributeError 导致整源不显示。只兜底 __getattr__ 未定义的名字。"""
        if name.startswith("get") and len(name) > 3:
            alias = name[3].lower() + name[4:]
            real = getattr(type(self), alias, None)
            if callable(real):
                return real.__get__(self, type(self))
        if name.startswith("__") and name.endswith("__"):
            raise AttributeError(name)
        return lambda *a, **k: ({} if name.startswith("get")
                                else ([] if "Content" in name else None))

    # ---------------- 初始化：拉远程配置 + 载入设备身份 ----------------
    def init(self, extend=""):
        cfg = None
        for u in CFG_URLS:
            try:
                cfg = _jget(u)
                if cfg:
                    break
            except Exception as e:
                self.last_error = str(e)
        if isinstance(cfg, dict):
            app = cfg.get("app") or {}
            other = app.get("otherURL") or app.get("textURL")
            if other:
                self.base = str(other).rstrip("/")
            res = app.get("resourceURL")
            if res:
                self.res_base = str(res).rstrip("/")
            try:
                for r in (cfg.get("xinRanks") or []):
                    n, ty = r.get("name"), r.get("types")
                    if n in RANK_TYPES and ty:
                        RANK_TYPES[n] = list(ty)
                        XINRANK_TYPES.update(ty)
            except Exception:
                pass
        # 身份优先级：落盘的已刷新身份(v3) > 内置本机身份 > ext 显式指定
        try:
            with open(_DEV_CACHE) as _f:
                _dc = json.load(_f)
            if _dc.get("v") == 3 and _dc.get("b"):
                for _k in ("deviceCode", "newDeviceCode", "b", "uid"):
                    if _dc.get(_k):
                        self.dev[_k] = str(_dc[_k])
        except Exception:
            pass
        try:
            if isinstance(extend, str) and extend.strip().startswith("{"):
                ex = json.loads(extend)
                for k in ("deviceCode", "newDeviceCode", "b"):
                    if ex.get(k):
                        self.dev[k] = str(ex[k])
        except Exception:
            pass
        return None

    # ---------------- 设备身份（对齐 App 生命周期） ----------------
    def _save_dev(self):
        try:
            _sv = dict(self.dev)
            _sv["v"] = 3
            with open(_DEV_CACHE, "w") as _f:
                json.dump(_sv, _f)
        except Exception:
            pass

    def _isnew(self, device_code, new_code):
        """App 原样字段注册/刷新（SplashActivity$a 逐行核对版）。"""
        body = {
            "packageName": PLAY_PKG, "baoming": PLAY_PKG, "version": VER,
            "channel": CHANNEL, "uid": 0, "userName": "",
            "modelName": MODEL, "isOld000": 0,
            "deviceCode": device_code, "newDeviceCode": new_code or "",
        }
        try:
            raw = _http_post_json("%s/vc/api/device/isnew" % self.base, body)
            return (raw or {}).get("data") or None
        except Exception:
            return None

    def _ensure_identity(self):
        """学 App 冷启动：拿已存身份调 isnew 刷新（b 若被轮换则更新并落盘），
        再 device/check 打卡。每进程只做一次；失败不阻断播放（用现有 b 继续）。"""
        if self._ident_ready:
            return
        self._ident_ready = True
        d = self._isnew(self.dev.get("deviceCode") or "",
                        self.dev.get("newDeviceCode") or "")
        if d and d.get("b"):
            changed = str(d["b"]) != (self.dev.get("b") or "")
            self.dev["b"] = str(d["b"])
            if d.get("newDeviceCode"):
                self.dev["newDeviceCode"] = str(d["newDeviceCode"])
            if d.get("uid"):
                self.dev["uid"] = str(d["uid"])
            if changed:
                self._save_dev()
        self._device_check()

    def _register_fresh(self):
        """全新设备注册（App 原样字段）。成功 True 并落盘。"""
        import random
        code = "".join(random.choice("0123456789abcdef") for _ in range(16))
        d = self._isnew(code, "")
        if d and d.get("b"):
            self.dev = {"deviceCode": code,
                        "newDeviceCode": str(d.get("newDeviceCode") or ""),
                        "b": str(d["b"])}
            if d.get("uid"):
                self.dev["uid"] = str(d["uid"])
            self._save_dev()
            return True
        return False

    def _device_check(self):
        try:
            _http_post_json("%s/vc/api/device/check" % self.base, {
                "deviceCode": self.dev.get("deviceCode") or "",
                "newDeviceCode": self.dev.get("newDeviceCode") or "",
                "b": self.dev.get("b") or "",
                "uid": int(self.dev.get("uid") or 0)})
            return True
        except Exception:
            return False

    def _fuli_txt(self):
        try:
            r = _http_post_json("%s/vc/api/fuli/fuli-info" % self.base, {
                "deviceCode": self.dev.get("deviceCode") or "",
                "newDeviceCode": self.dev.get("newDeviceCode") or "",
                "b": self.dev.get("b") or "",
                "uid": int(self.dev.get("uid") or 0)})
            d = (r or {}).get("data") or {}
            return "uid=%s jinbi=%s touping=%s xiazai=%s" % (
                d.get("uid"), d.get("jinbi"), d.get("toupingcishu"),
                d.get("xiazaicishu"))
        except Exception as e:
            return "fuli异常:%s" % str(e)[:30]

    # ---------------- 工具 ----------------
    def _pic(self, it):
        p = (it.get("fengmiantu") or "").strip()
        if not p:
            p = (it.get("dahengtu") or "").strip()
        if not p:
            return ""
        if p.startswith("//"):
            p = "https:" + p
        elif p.startswith("/"):
            p = self.res_base + p
        return p

    @staticmethod
    def _pack(vid, total, name, pic, cls, region, year, score, actor, blurb):
        import time as _time
        meta = {
            "n": name, "p": pic, "c": cls, "r": region, "y": year,
            "s": score, "a": actor, "d": (blurb or "")[:600], "t": int(total or 0),
            "ts": int(_time.time()),  # 打包时间：详情页借此判断集数是否过期
        }
        b = base64.urlsafe_b64encode(
            json.dumps(meta, ensure_ascii=False).encode("utf-8")).decode("ascii")
        return "%s|%s" % (vid, b.rstrip("="))

    def _unpack(self, vod_id):
        try:
            a, b = str(vod_id).split("|", 1)
            b += "=" * (-len(b) % 4)
            return a, json.loads(base64.urlsafe_b64decode(b).decode("utf-8"))
        except Exception:
            return str(vod_id), {}

    def _to_vod(self, it):
        vid = it.get("videoId")
        if vid is None:
            return None
        total = _ep_count(it)
        name = it.get("videoName") or ""
        pic = self._pic(it)
        cls = it.get("class") or it.get("typeName") or ""
        remark = it.get("remarks") or it.get("serialDesc") or it.get("newchapter") or ""
        return {
            "vod_id": self._pack(vid, total, name, pic, cls, it.get("region"),
                                 it.get("year"), it.get("score"), it.get("actor"),
                                 it.get("blurb") or it.get("shortBlurb")),
            "vod_name": name,
            "vod_pic": pic,
            "vod_remarks": remark,
            "vod_year": str(it.get("year") or ""),
            "vod_area": str(it.get("region") or ""),
            "vod_actor": it.get("actor") or "",
            "vod_content": it.get("blurb") or it.get("shortBlurb") or "",
            "type_name": it.get("typeName") or "",
            "vod_score": str(it.get("score") or ""),
        }

    def _list(self, items):
        out = []
        for it in (items or []):
            if not isinstance(it, dict):
                continue
            v = self._to_vod(it)
            if v:
                out.append(v)
        return out

    # ---------------- 1. 首页：分类 + 筛选 ----------------
    def homeContent(self, filter=False):
        cats = [{"type_id": c, "type_name": c} for c in CHANNELS]
        cats += [{"type_id": r, "type_name": r} for r in ["热播榜", "新片榜", "高分榜"]]
        fmap = self._filter_defs()
        filters = {}
        for c in CHANNELS:
            fl = []
            for key in CHANNEL_SLOTS.get(c, []):
                if not key:
                    continue
                vals = (fmap.get(c) or {}).get(key) or ["全部"]
                if len(vals) > 1:
                    fl.append({"key": key, "name": FILTER_NAMES.get(key, key),
                               "value": [{"n": v, "v": v} for v in vals]})
            sorts = (fmap.get(c) or {}).get("sort") or ["最热", "最新", "评分"]
            fl.append({"key": "sort", "name": "排序",
                       "value": [{"n": s, "v": s} for s in sorts]})
            filters[c] = fl
        for r in ["热播榜", "新片榜", "高分榜"]:
            filters[r] = [{"key": "type", "name": "类型",
                           "value": [{"n": t, "v": t} for t in
                                     RANK_TYPES.get(r, _RANK_TYPE_LIST)]}]
        return {"class": cats, "filters": filters}

    def _filter_defs(self):
        """读 /cache/filterOptions/filter.json → 每频道的 类型/地区/年代/年龄/系列/排序"""
        if self._fdef is not None:
            return self._fdef
        out = {}
        try:
            f = _jget("%s/cache/filterOptions/filter.json" % self.base)
            for ch in (f or []):
                if not isinstance(ch, dict):
                    continue
                types = ["全部"]
                for x in (ch.get("children") or []):
                    if isinstance(x, dict) and x.get("name") and x["name"] != "全部":
                        types.append(x["name"])
                out[ch.get("name")] = {
                    "type": types,
                    "region": ch.get("region") or list(FILTER_REGIONS),
                    "year": ch.get("year") or list(FILTER_YEARS),
                    "nianling": ch.get("nianling") or list(FILTER_NIANLING),
                    "xilie": ch.get("xilie") or list(FILTER_XILIE),
                    "sort": ch.get("sort") or ["最热", "最新", "评分"],
                }
        except Exception as e:
            self.last_error = str(e)
        self._fdef = out
        return out

    def homeVideoContent(self):
        """首页"推荐" = /cache/channel/首页.json 的模块数据（轮播/热门推荐/电影/…）"""
        try:
            mods = _jget("%s/cache/channel/%s.json" % (self.base, _q("首页")))
            vids = []
            for m in (mods or []):
                if isinstance(m, dict):
                    vids.extend(self._list(m.get("data")))
            return {"list": vids}
        except Exception:
            return {"list": []}

    # ---------------- 2. 分类列表 ----------------
    def _get_list(self, url):
        try:
            data = _jget(url)
        except Exception as e:
            self.last_error = str(e)
            return []
        if isinstance(data, dict):
            data = data.get("data") or data.get("list") or []
        return self._list(data if isinstance(data, list) else [])

    @staticmethod
    def _page(vids, pg):
        n = len(vids)
        return {"list": vids, "page": pg,
                "pagecount": pg + 1 if n >= 10 else pg,
                "limit": 10, "total": 9999 if n >= 10 else n}

    def _rank_raw(self, rank, rtype, pg):
        """取榜单原始条目（实例级缓存，筛选翻页复用；失败返回 []）。"""
        key = (rank, rtype, int(pg))
        hit = self._rank_cache.get(key)
        if hit is not None:
            return hit
        try:
            data = _jget("%s/cache/xinrank/%s/%s/%d.json" % (
                self.base, _q(rank), _q(rtype), key[2]))
        except Exception as e:
            self.last_error = str(e)
            data = None
        raw = [it for it in (data if isinstance(data, list) else [])
               if isinstance(it, dict)]
        if len(self._rank_cache) > 80:
            self._rank_cache.clear()
        self._rank_cache[key] = raw
        return raw

    @staticmethod
    def _match_raw(it, genre, region, year, nianling, xilie):
        """客户端筛选：类型看 class 字段（逗号分隔多值），地区/年代看 region/year，
        少儿另有 nianling/xilie（走片名/类型文本匹配）。"""
        if genre and genre != "全部":
            cls = "%s %s" % (it.get("class") or "", it.get("typeName") or "")
            if genre not in cls:
                return False
        if region and region != "全部":
            if region not in str(it.get("region") or ""):
                return False
        if year and year != "全部":
            y = str(it.get("year") or "")
            if year.endswith("年代"):
                if not y.startswith(year[:2]):
                    return False
            elif "-" in year:               # "2015-2011" / "2010-2000"
                lo, hi = year.split("-", 1)
                try:
                    if not (int(hi) <= int(y) <= int(lo)):
                        return False
                except Exception:
                    if not y.startswith(year[:3]):
                        return False
            elif y != year:
                return False
        name = str(it.get("videoName") or "")
        if xilie and xilie != "全部":      # 少儿"系列"（小猪佩奇/汪汪队/…）按片名命中
            if xilie not in name:
                return False
        if nianling and nianling != "全部":  # 年龄分段无字段可依，不做硬过滤
            pass
        return True

    def _scan_rank(self, rank, rtype, pg, genre, region, year, nianling=None,
                   xilie=None):
        """按筛选扫描榜单：攒够 pg 页的量；返回分页结构（与 _page 同格式）。"""
        PAGE = 10
        pg = int(pg or 1)
        want = pg * PAGE
        acc, rpage, scanned = [], 0, 0
        rank_alive, last_full = True, False
        while len(acc) < want and scanned < FILTER_SCAN_MAX and rank_alive:
            rpage += 1
            raw = self._rank_raw(rank, rtype, rpage)
            if not raw:
                rank_alive = False
                break
            scanned += len(raw)
            last_full = len(raw) >= PAGE
            for it in raw:
                if self._match_raw(it, genre, region, year, nianling, xilie):
                    acc.append(it)
            if not last_full:
                rank_alive = False
        vids = self._list(acc)
        page = vids[(pg - 1) * PAGE:pg * PAGE]
        more = len(vids) > pg * PAGE or (rank_alive and last_full)
        return {"list": page, "page": pg, "pagecount": pg + 1 if more else pg,
                "limit": PAGE, "total": 9999 if more else len(vids)}

    def categoryContent(self, tid, pg, filter=False, extend=None):
        """
        频道走明文榜单（zhaopian 返回加密数据，静态解不开）：
          排序 → 切榜（最热/最新/评分 → 热播榜/新片榜/高分榜）
          类型/地区 → 优先映射到榜单第二维，映射不上走客户端过滤
        榜单分类：{base}/cache/xinrank/<榜>/<类型>/<页>.json
        命中空逐级回退，绝不返回空白列表。
        """
        pg = int(pg or 1)
        ex = extend if isinstance(extend, dict) else {}

        if tid in RANKS or tid in RANK_TYPES:
            rtype = ex.get("type") or "全部"
            if rtype not in XINRANK_TYPES:
                rtype = "全部"
            vids = self._get_list("%s/cache/xinrank/%s/%s/%d.json" % (
                self.base, _q(tid), _q(rtype), pg))
            if not vids and rtype != "全部":      # 类型不适用 → 退回"全部"
                vids = self._get_list("%s/cache/xinrank/%s/%s/%d.json" % (
                    self.base, _q(tid), _q("全部"), pg))
            return self._page(vids, pg)

        if tid not in CHANNEL_SLOTS:
            return self._page([], pg)

        rank = SORT_RANK.get((ex.get("sort") or "最热").strip(), "热播榜")
        ftype = (ex.get("type") or "全部").strip()
        fregion = (ex.get("region") or "全部").strip()
        fyear = (ex.get("year") or "全部").strip()
        fnianling = (ex.get("nianling") or "全部").strip()
        fxilie = (ex.get("xilie") or "全部").strip()

        if ftype in XINRANK_TYPES and ftype != "全部":
            rtype, genre = ftype, None            # 类型直达榜单维度
        else:
            rtype = (REGION_RANK.get(tid) or {}).get(fregion)
            if not rtype and tid == "综艺" and fregion not in ("全部", "大陆"):
                rtype = "国外综艺"
            rtype = rtype or CH_RANK_TYPE.get(tid, "全部")
            genre = None if ftype in ("全部", "") else ftype

        res = self._scan_rank(rank, rtype, pg, genre, fregion, fyear,
                              fnianling, fxilie)
        # 兜底：筛选后空白、但榜单本身有货 → 逐步放宽，绝不返回空白列表
        if not res["list"] and (genre or fregion != "全部" or fyear != "全部"
                                or fxilie != "全部"):
            res = self._scan_rank(rank, rtype, pg, None, "全部", "全部")
        if not res["list"]:
            res = self._scan_rank("热播榜", CH_RANK_TYPE.get(tid, "全部"), pg,
                                  None, "全部", "全部")
        return res

    # ---------------- 3. 详情 ----------------
    def _refresh_meta(self, vid, m):
        """集数自愈：packed 元数据超过 24h（或无时间戳的旧数据）时，按片名搜最新
        条目刷新集数/简介。搜不到同 videoId 则原样返回。新鲜数据直接返回，无开销。"""
        import time as _time
        try:
            ts = int(m.get("ts") or 0)
        except Exception:
            ts = 0
        if _time.time() - ts < 24 * 3600:
            return m
        name = (m.get("n") or "").strip()
        if not name:
            return m
        try:
            cands = (self.searchContent(name, quick=True) or {}).get("list") or []
        except Exception:
            return m
        for v in cands:
            vvid, vm = self._unpack(v.get("vod_id") or "")
            if str(vvid) == str(vid) and vm.get("t"):
                vm["ts"] = int(_time.time())
                return vm
        return m

    def _video_detail(self, vid):
        """GET {base}/cache/videos/<vid>.json → AES-256-GCM(DETAIL_KEY) 解密。
        返回 dict（含 playUrlList[{name, beizhu, ji}]）或 None。"""
        try:
            raw = _http_get("%s/cache/videos/%s.json" % (self.base, vid),
                            {"User-Agent": PLAY_UA})
            return _dec_json(DETAIL_KEY, raw.decode("utf-8", "ignore"))
        except Exception:
            return None

    def detailContent(self, array):
        if not array:
            return {"list": []}
        raw = array[0] if isinstance(array, (list, tuple)) else array
        vid, m = self._unpack(raw)
        # ★ 优先拉 App 同款详情（每集带真实 ji 编号，播放必需）
        det = self._video_detail(vid)
        plist = (det or {}).get("playUrlList") or []
        if det and plist:
            m = {
                "n": det.get("videoName") or det.get("name") or m.get("n"),
                "p": det.get("fengmiantu") or m.get("p"),
                "c": det.get("typeName") or m.get("c"),
                "r": det.get("region") or m.get("r"),
                "y": det.get("year") or m.get("y"),
                "s": det.get("score") or m.get("s"),
                "a": det.get("actor") or m.get("a"),
                "d": det.get("blurb") or m.get("d"),
                "t": len(plist),
            }
            plays = []
            for i, ep in enumerate(plist):
                ep = ep or {}
                nm = str(ep.get("name") or (i + 1))
                label = ("第%s集" % nm) if nm.isdigit() else nm
                if ep.get("beizhu"):
                    label = "%s(%s)" % (label, ep.get("beizhu"))
                ji = ep.get("ji")
                # ★ 用 @ 分隔（绝不用 | ：影视仓会截断 → 恒播第 1 集）
                plays.append("%s$%s%s%s%s%d" % (
                    label, vid, SEP, ji if ji is not None else "-", SEP, i))
            raw = self._pack(vid, len(plist), m.get("n"), m.get("p"), m.get("c"),
                             m.get("r"), m.get("y"), m.get("s"), m.get("a"),
                             m.get("d"))
            vod = {
                "vod_id": raw,
                "vod_name": m.get("n") or "",
                "vod_pic": m.get("p") or "",
                "vod_year": str(m.get("y") or ""),
                "vod_area": str(m.get("r") or ""),
                "vod_actor": m.get("a") or "",
                "vod_score": str(m.get("s") or ""),
                "vod_content": m.get("d") or "",
                "vod_remarks": det.get("serialDesc") or det.get("remarks") or
                               (("全%d集" % len(plist)) if len(plist) > 1 else "1集"),
                "type_name": m.get("c") or "",
                "vod_play_from": "云帧享",
                "vod_play_url": "#".join(plays),
            }
            return {"list": [vod]}
        # ★ 集数自愈：历史记录里的旧集数（如已下架/集数变化）打开时自动刷新
        m = self._refresh_meta(vid, m)
        total = int(m.get("t") or 0)
        if total <= 0:
            total = 1
        plays = ["第%d集$%s%s%d" % (i + 1, vid, SEP, i) for i in range(total)]
        # 用刷新后的元数据重打包，历史记录下次打开就是新的
        raw = self._pack(vid, total, m.get("n"), m.get("p"), m.get("c"),
                         m.get("r"), m.get("y"), m.get("s"), m.get("a"),
                         m.get("d"))
        vod = {
            "vod_id": raw,
            "vod_name": m.get("n") or "",
            "vod_pic": m.get("p") or "",
            "vod_year": str(m.get("y") or ""),
            "vod_area": str(m.get("r") or ""),
            "vod_actor": m.get("a") or "",
            "vod_score": str(m.get("s") or ""),
            "vod_content": m.get("d") or "",
            "vod_remarks": ("全%d集" % total) if total > 1 else "1集",
            "type_name": m.get("c") or "",
            "vod_play_from": "云帧享",
            "vod_play_url": "#".join(plays),
        }
        return {"list": [vod]}

    # ---------------- 4. 搜索 ----------------
    def searchContent(self, key, quick=False, pg="1"):
        url = "%s/vc/api/search/?keyword=%s" % (self.base, _q(key))
        try:
            data = _jget(url)
        except Exception as e:
            self.last_error = str(e)
            data = None
        if isinstance(data, dict):
            data = data.get("data") or data.get("list")
        return {"list": self._list(data if isinstance(data, list) else [])}

    def searchContentPage(self, key, quick, pg):
        return self.searchContent(key, quick, pg)

    # ---------------- 5. 播放 ----------------
    def _play_once(self, vid, ji, ji_index=0, is_jiid=True):
        """发一次 playurl，返回 (url, data_code)。
        传输层用 http.client 按 OkHttp 的线格式逐头发送（头顺序/集合与 App 的
        裸 OkHttp 一致），响应支持明文/GCM 密文。"""
        import http.client
        import gzip as _gz
        params = [
            ("sid", str(vid)), ("ji", str(ji)), ("jiIndex", str(ji_index)),
            ("t", "0"), ("y", "0"), ("isjiid", "1" if is_jiid else "0"),
            ("androidId", self.dev.get("deviceCode") or "0000000000000000"),
            ("modelName", MODEL),
            ("newDeviceCode", self.dev.get("newDeviceCode") or ""),
            ("b", self.dev.get("b") or ""),
            ("version", VER), ("baoming", PLAY_PKG), ("channel", CHANNEL),
        ]
        path = "/vc/api/video/playurl?" + urllib.parse.urlencode(params)
        host = self.base.split("://", 1)[-1].split("/")[0]
        body = b""
        try:
            conn = http.client.HTTPSConnection(host, 443, timeout=15)
            conn.putrequest("GET", path, skip_host=True,
                            skip_accept_encoding=True)
            conn.putheader("vuk", vuk_of(vid))
            conn.putheader("Host", host)
            conn.putheader("Connection", "Keep-Alive")
            conn.putheader("Accept-Encoding", "gzip")
            conn.putheader("User-Agent", PLAY_UA)
            conn.endheaders()
            resp = conn.getresponse()
            body = resp.read()
            if (resp.getheader("Content-Encoding") or "") == "gzip":
                try:
                    body = _gz.decompress(body)
                except Exception:
                    pass
            conn.close()
        except Exception as e:
            # raw 直发异常（证书/网络栈差异）→ 回落 urllib 再试一次，
            # 不能让传输怪癖把整条播放链带崩（仅异常时触发）。
            self._dbg_last = "raw异常:%s→urllib回落" % str(e)[:40]
            try:
                d2 = _jget("%s%s" % (self.base, path),
                           {"vuk": vuk_of(vid), "User-Agent": PLAY_UA})
                if d2 is not None:
                    self._dbg_last = json.dumps(d2, ensure_ascii=False)[:260]
                    data = (d2 or {}).get("data") or {}
                    play = data.get("url") or ""
                    arr = data.get("urlarr") or []
                    if not play and isinstance(arr, list) and arr:
                        play = ((arr[0] or {}).get("url")
                                if isinstance(arr[0], dict) else arr[0])
                    return (play or ""), data.get("code")
            except Exception:
                pass
            return "", None
        text = body.decode("utf-8", "ignore") if isinstance(body, bytes) else str(body)
        d = None
        try:
            d = json.loads(text)
        except Exception:
            d = _dec_json(PLAY_KEY, text)          # App 同款：先试 GCM 解密
        if d is None:
            self._dbg_last = "响应不可解析:%s" % text[:120]
            return "", None
        self._dbg_last = json.dumps(d, ensure_ascii=False)[:260]
        data = (d or {}).get("data") or {}
        code = data.get("code")
        play = data.get("url") or ""
        arr = data.get("urlarr") or []
        if not play and isinstance(arr, list) and arr:
            play = ((arr[0] or {}).get("url")
                    if isinstance(arr[0], dict) else arr[0])
        return (play or ""), code

    def _play_via_framework(self, vid, ji, ji_index=0, is_jiid=True):
        """用壳子自带的 self.fetch 发 playurl —— 走壳自己的网络栈
        （不是 Python 的 TLS 指纹）。不可用返回 ("", None)。"""
        params = [
            ("sid", str(vid)), ("ji", str(ji)), ("jiIndex", str(ji_index)),
            ("t", "0"), ("y", "0"), ("isjiid", "1" if is_jiid else "0"),
            ("androidId", self.dev.get("deviceCode") or "0000000000000000"),
            ("modelName", MODEL),
            ("newDeviceCode", self.dev.get("newDeviceCode") or ""),
            ("b", self.dev.get("b") or ""),
            ("version", VER), ("baoming", PLAY_PKG), ("channel", CHANNEL),
        ]
        url = "%s/vc/api/video/playurl?%s" % (
            self.base, urllib.parse.urlencode(params))
        try:
            text = self.fetch(url, headers={"vuk": vuk_of(vid),
                                            "User-Agent": PLAY_UA})
        except Exception:
            return "", None
        if text is None:
            return "", None
        if not isinstance(text, str):
            try:
                text = text.decode("utf-8", "ignore")
            except Exception:
                text = str(text)
        d = None
        try:
            d = json.loads(text)
        except Exception:
            d = _dec_json(PLAY_KEY, text)
        if d is None:
            return "", None
        self._dbg_last = json.dumps(d, ensure_ascii=False)[:260]
        data = (d or {}).get("data") or {}
        play = data.get("url") or ""
        arr = data.get("urlarr") or []
        if not play and isinstance(arr, list) and arr:
            play = ((arr[0] or {}).get("url")
                    if isinstance(arr[0], dict) else arr[0])
        return (play or ""), data.get("code")

    def _ad_warmup(self):
        """App 在使用中会周期性调 getadjson（带本机身份）——播放前照做，
        让服务器侧看到与 App 一致的会话形状。"""
        try:
            _http_post_json("%s/vc/api/getadjson" % self.base, {
                "packageName": PLAY_PKG, "version": VER, "channel": CHANNEL,
                "deviceCode": self.dev.get("deviceCode") or "",
                "newDeviceCode": self.dev.get("newDeviceCode") or "",
                "b": self.dev.get("b") or ""})
            return True
        except Exception:
            return False

    def playerContent(self, flag, id, vipFlags=None):
        # ===== 播放链：本机身份 → 三级兜底 =====
        raw = str(id)
        vid, ji, ji_index = raw, 0, 0
        parts = raw.split(SEP)
        if len(parts) >= 3:
            vid = parts[0]
            try:
                ji_index = int(parts[2])
            except Exception:
                ji_index = 0
            if parts[1] not in ("-", ""):
                try:
                    ji = int(parts[1])
                except Exception:
                    ji = ji_index
            else:
                ji = ji_index
        elif SEP in raw:
            a, b = raw.split(SEP, 1)
            vid = a
            try:
                ji = ji_index = int(b)
            except Exception:
                ji = ji_index = 0
        elif "|" in raw:
            a, b = raw.split("|", 1)
            vid = a
            try:
                ji = ji_index = int(b)
            except Exception:
                ji = ji_index = 0
        log = []
        play = ""

        def _round(tag, jv, mode, dev=None):
            """一轮 = 先 getadjson 武装、紧接着 playurl（窗口只有约 3 秒，
            中间不能插入任何请求）。dev 非空时临时切换身份。"""
            nonlocal play
            _old = None
            if dev is not None:
                _old = dict(self.dev)
                self.dev = dict(dev)
            try:
                self._ad_warmup()
                p, c = self._play_once(vid, jv, ji_index, mode)
            except Exception as e:
                p, c = "", None
                log.append("%s异常:%s" % (tag, str(e)[:30]))
            if dev is not None and not (p and PLAY_PLACEHOLDER not in p):
                self.dev = _old
            log.append("%s code=%s url=%s" % (tag, c, (p[:36] + "..") if p else "空"))
            if p and PLAY_PLACEHOLDER not in p:
                play = p

        # A: 本机身份，贴脸连发三轮（ji 模式）
        for _i in range(3):
            _round("A%d本机ji" % (_i + 1), ji, True)
            if play:
                break
        if not play:
            _round("A本机序号", ji_index, False)
        # B: 全新设备兜底（注册后同样先武装再打）
        if not play:
            if self._register_fresh():
                self._device_check()
                for _i in range(2):
                    _round("B%d新设备ji" % (_i + 1), ji, True)
                    if play:
                        break
            else:
                log.append("B注册失败")
        # C: 种子兜底
        if not play:
            _round("C种子ji", ji, True, dev=DEFAULT_DEV)
        hdr = json.dumps({"User-Agent": PLAY_UA}, ensure_ascii=False)
        if play:
            return {"parse": 0, "playUrl": "", "url": play, "header": hdr}
        msg = "[%s] sid=%s ji=%s idx=%d | %s | 账号:%s | 末次响应:%s" % (
            DIAG_TAG, vid, ji, ji_index, " ; ".join(log),
            self._fuli_txt(), getattr(self, "_dbg_last", ""))
        return {"parse": 0, "playUrl": "", "url": "", "header": hdr, "msg": msg}

    def isVideoFormat(self, url):
        return any(url.lower().split("?")[0].endswith(e) for e in
                   (".m3u8", ".mp4", ".mkv", ".flv", ".ts")) or ".m3u8?" in url.lower()

    def manualVideoCheck(self):
        return False

    # ---------------- 6. 封面本地代理 ----------------
    def localProxy(self, param):
        try:
            url = param.get("url") if isinstance(param, dict) else None
            if not url:
                return [404, "text/plain", b""]
            raw = _http_get(url, {"User-Agent": UA}, 15)
            head = raw[:4]
            if head[:3] == b"\xff\xd8\xff":
                mime = "image/jpeg"
            elif head[:4] == b"\x89PNG":
                mime = "image/png"
            elif head[:4] == b"RIFF":
                mime = "image/webp"
            elif head[:3] == b"GIF":
                mime = "image/gif"
            else:
                mime = "image/jpeg"
            return [200, mime, raw]
        except Exception:
            return [404, "text/plain", b""]


# ============================================================================
# 模块级转发层（部分壳子按函数名加载）
# ============================================================================
_spider = Spider()


def getName():
    return "云帧享"


def init(extend=""):
    return _spider.init(extend)


def homeContent(filter=False):
    return _spider.homeContent(filter)


def homeVideoContent():
    return _spider.homeVideoContent()


def categoryContent(tid, pg, filter=False, extend=None):
    return _spider.categoryContent(tid, pg, filter, extend)


def detailContent(array):
    return _spider.detailContent(array)


def searchContent(key, quick=False, pg="1"):
    return _spider.searchContent(key, quick, pg)


def searchContentPage(key, quick, pg):
    return _spider.searchContentPage(key, quick, pg)


def playerContent(flag, id, vipFlags=None):
    return _spider.playerContent(flag, id, vipFlags)


def isVideoFormat(url):
    return _spider.isVideoFormat(url)


def manualVideoCheck():
    return False


def localProxy(param):
    return _spider.localProxy(param)


# ============================================================================
# 自检：python 云帧享.py
# ============================================================================
if __name__ == "__main__":
    print("=" * 62)
    print(" 云帧享 TVBox 源 自检")
    print("=" * 62)

    # 0) AES-GCM 正确性（NIST 向量）
    try:
        pt = aes_gcm_decrypt(
            bytes.fromhex("00000000000000000000000000000000"),
            bytes.fromhex("000000000000000000000000"),
            bytes.fromhex("0388dace60b6a392f328c2b971b2fe78") +
            bytes.fromhex("ab6e47d42cec13bdf53a67b21257bddf"))
        assert pt == b"\x00" * 16, pt
        print("[OK] AES-256/128-GCM 自校验通过（NIST 向量）")
    except Exception as e:
        print("[!!] AES-GCM 自校验失败:", e)

    s = Spider()
    s.init()
    print("[OK] 配置基址:", s.base, "| 资源:", s.res_base)
    print("[OK] 设备身份: deviceCode=%s newDeviceCode=%s b=%s..." %
          (s.dev.get("deviceCode"), s.dev.get("newDeviceCode"),
           (s.dev.get("b") or "")[:16]))

    hc = s.homeContent(True)
    print("[OK] 分类:", [c["type_name"] for c in hc["class"]])
    for k, v in hc["filters"].items():
        print("     筛选[%s]: %s" % (k, [(x["name"], len(x["value"])) for x in v]))

    hv = s.homeVideoContent()
    print("[OK] 首页推荐:", len(hv.get("list") or []), "条")

    for ch, ext in [("电影", {"type": "喜剧", "region": "全部", "year": "全部", "sort": "最热"}),
                    ("剧集", {"type": "全部", "region": "全部", "year": "全部", "sort": "最新"}),
                    ("少儿", {"type": "全部", "nianling": "4-6", "xilie": "全部", "sort": "最热"})]:
        cc = s.categoryContent(ch, 1, False, ext)
        v0 = cc["list"][0] if cc["list"] else {}
        print("[OK] 频道[%s]: %d 条 | 示例: %s %s" %
              (ch, len(cc["list"]), v0.get("vod_name"), v0.get("vod_remarks")))

    # —— 集数推断单元校验（防"日期当集数"的坑）——
    for desc, want in [("全24集", 24), ("更新至15集", 15), ("20261008", 0),
                       ("已完结", 0), ("第1-24集", 24), ("共12期", 12)]:
        got = _ep_count({"newchapter": desc})
        print("   [集数] %-10s -> %-3d %s" % (desc, got,
              "OK" if got == want else "!! 期望%d" % want))

    sc = s.searchContent("醉梦")
    hit = next((v for v in sc["list"] if "醉梦" in v["vod_name"]), None)
    if hit:
        dc = s.detailContent([hit["vod_id"]])["list"][0]
        urls = dc["vod_play_url"].split("#")
        vid = hit["vod_id"].split("|")[0]
        print("[OK] 醉梦: %s | %d 集 | 首/末: %s / %s" %
              (dc["vod_name"], len(urls), urls[0], urls[-1]))
        print("     %s" % ("选集正常(>1且用@)" if len(urls) > 1 and "@" in urls[0]
                           else "⚠ 仍只出 1 集"))
        for i in (0, len(urls) - 1):
            pid = urls[i].split("$", 1)[1]
            pc = s.playerContent("云帧享", pid)
            u = pc.get("url") or ""
            print("     播放第%d集: %s %s" % (i + 1,
                  "真链" if u and PLAY_PLACEHOLDER not in u else "⚠ 占位", u[:78]))
    else:
        print("[--] 未搜到醉梦")

    print("[OK] 搜索(喜剧):", len(s.searchContent("喜剧")["list"]), "条")
    print("=" * 62)
    print(" 自检完成")
