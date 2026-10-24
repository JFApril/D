#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
极速追剧 (jisuzhuiju.com) —— TVBox py 源
=========================================
站点为 SSR 网页站，播放地址由服务端接口 /api/play-url 统一解析（直连 m3u8）。

线路：详情页自带多条线路（腾讯官方 qq / 自建 covip / 极速 jsm3u8 等），
播放时实时调站点解析接口拿真实地址。

功能：首页推荐 / 分类浏览(电视剧·电影·动漫·综艺，支持分页) / 搜索(片名+演员) / 多线路播放
"""

from __future__ import annotations

import json
import re
import ssl
import urllib.parse
import urllib.request

try:
    from base.spider import Spider as _BaseSpider
except Exception:
    try:
        from base.Spider import Spider as _BaseSpider  # noqa
    except Exception:
        _BaseSpider = object

UA = ("Mozilla/5.0 (Linux; Android 13) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/120.0.0.0 Mobile Safari/537.36")

BASE = "https://jisuzhuiju.com"

_SSL_CTX = ssl.create_default_context()
_SSL_CTX.check_hostname = False
_SSL_CTX.verify_mode = ssl.CERT_NONE

# 分类 → channel id（/filter?channel=N）
CATEGORIES = [("电视剧", "1"), ("电影", "2"), ("动漫", "3"), ("综艺", "4")]
CAT_BY_NAME = dict(CATEGORIES)

# 线路 key → 展示名（详情页/播放页 tab 顺序：腾讯官方 / 自建 / 普通线路）
LINE_NAMES = {"qq": "官方线路", "covip": "自建线路", "jsm3u8": "极速线路",
              "qiyi": "奇艺线路"}


def _http_get(url, timeout=12, referer=None):
    h = {"User-Agent": UA}
    if referer:
        h["Referer"] = referer
    req = urllib.request.Request(url, headers=h)
    with urllib.request.urlopen(req, timeout=timeout, context=_SSL_CTX) as resp:
        return resp.read().decode("utf-8", "ignore")


# ---------------------------------------------------------------- HTML 解析
_CARD_RE = re.compile(
    r'<a href="/detail/(\d+)\.html"[^>]*>.*?'
    r'(?:<img[^>]+src="([^"]+)"[^>]*alt="([^"]*)封面|)'
    r'.*?(?:vod-badge[^>]*>([^<]+)</span>|)'
    r'.*?vod-title[^>]*>([^<]+)<'
    r'(?:.*?vod-subtitle[^>]*>([^<]+)<|)'
    r'.*?</a>', re.S)


def _clean(s):
    return re.sub(r"\s+", "", s or "").strip()


def _parse_cards(html):
    """通用卡片解析：filter 页 / 首页（按 <a href="/detail/ 分段）"""
    out, seen = [], set()
    starts = [m for m in re.finditer(r'<a href="/detail/(\d+)\.html"', html)]
    for i, m in enumerate(starts):
        vid = m.group(1)
        if vid in seen:
            continue
        end = starts[i + 1].start() if i + 1 < len(starts) else min(len(html), m.end() + 1500)
        blk = html[m.end():end]
        title = ""
        tm = re.search(r'vod-title[^>]*>([^<]+)<', blk)
        if tm:
            title = _clean(tm.group(1))
        else:
            am = re.search(r'alt="([^"]*?)封面', blk)
            if am:
                title = _clean(am.group(1))
        if not title:
            continue
        seen.add(vid)
        pic = ""
        pm = re.search(r'<img[^>]+src="([^"]+)"', blk)
        if pm:
            pic = pm.group(1)
        remark = ""
        rm = re.search(r'vod-badge[^>]*>([^<]+)<', blk)
        if rm:
            remark = _clean(rm.group(1))
        sub = ""
        sm = re.search(r'vod-subtitle[^>]*>([^<]+)<', blk)
        if sm:
            sub = _clean(sm.group(1))
        out.append({
            "vod_id": vid,
            "vod_name": title,
            "vod_pic": pic,
            "vod_remarks": remark,
            "type_name": sub,
        })
    return out


def _parse_search(html):
    """搜索结果条目：按 <div class="search-item"> 分段解析"""
    out, seen = [], set()
    starts = [m for m in re.finditer(r'<div class="search-item">', html)]
    for i, m in enumerate(starts):
        end = starts[i + 1].start() if i + 1 < len(starts) else len(html)
        blk = html[m.end():end]
        im = re.search(r'href="/detail/(\d+)\.html" class="search-item-poster".*?<img[^>]+src="([^"]+)"',
                       blk, re.S)
        if not im:
            continue
        vid, pic = im.group(1), im.group(2)
        if vid in seen:
            continue
        tm = re.search(r'class="search-item-title[^"]*">([^<]+)<', blk)
        if not tm:
            continue
        seen.add(vid)
        ym = re.findall(r'·\s*(\d{4})\s*·', blk)
        tm2 = re.search(r'search-meta-value">([^<]+)</span>\s*</div>\s*<div class="search-meta-item',
                        blk, re.S)
        out.append({
            "vod_id": vid,
            "vod_name": _clean(tm.group(1)),
            "vod_pic": pic,
            "vod_remarks": (ym[0] if ym else ""),
            "type_name": _clean(tm2.group(1)) if tm2 else "",
        })
    return out


def _parse_detail(html):
    """详情页：基本信息 + 各线路选集"""
    d = {}
    tm = re.search(r'<h1[^>]*>([^<]+)</h1>', html)
    d["vod_name"] = _clean(tm.group(1)) if tm else ""
    pm = re.search(r'og:image"\s+content="([^"]+)"', html)
    d["vod_pic"] = pm.group(1) if pm else ""

    def _field(label):
        m = re.search(label + r'[：:]\s*</span>\s*(?:<[^>]+>)*([^<]{1,80})', html)
        return _clean(m.group(1)) if m else ""

    d["vod_actor"] = _field("主演")
    d["vod_director"] = _field("导演")
    d["vod_area"] = _field("地区")
    d["vod_year"] = _field("年份")
    gm = re.search(r'(?:类型|分类)[：:]\s*</span>\s*(?:<[^>]+>)*([^<]{1,60})', html)
    d["type_name"] = _clean(gm.group(1)) if gm else ""
    dm = re.search(r'og:description"\s+content="([^"]+)"', html)
    d["vod_content"] = dm.group(1).strip() if dm else ""

    # 各线路选集：/vodplay/{id}-{from}-{idx}.html
    lines, urls, order = [], [], []
    eps = {}
    for m in re.finditer(r'/vodplay/(\d+)-([A-Za-z0-9]+)-(\d+)\.html', html):
        vod, key, idx = m.group(1), m.group(2), m.group(3)
        if key not in eps:
            eps[key] = []
            order.append(key)
        if (idx not in [e[0] for e in eps[key]]):
            eps[key].append((idx, f"{vod}${key}${idx}"))
    for key in order:
        lst = eps[key]
        lst.sort(key=lambda x: int(x[0]))
        label = LINE_NAMES.get(key, f"线路·{key}")
        lines.append(label)
        urls.append("#".join(f"第{int(idx)}集${pid}" for idx, pid in lst))
    d["lines"], d["urls"] = lines, urls
    return d


class Spider(_BaseSpider):
    def __init__(self, *args, **kwargs):
        try:
            super().__init__(*args, **kwargs)
        except Exception:
            pass

    def getName(self):
        return "极速追剧"

    def init(self, extend=""):
        self.timeout = 12
        self._cache = {}

    def isVideoFormat(self, url):
        return False

    def manualVideoCheck(self):
        return False

    def destroy(self):
        pass

    # ---------------------------------------------------------- 首页
    def homeContent(self, flag):
        return {"class": [{"type_id": n, "type_name": n} for n, _ in CATEGORIES],
                "filters": {}}

    def homeVideoContent(self):
        try:
            html = _http_get(BASE + "/")
            return {"list": _parse_cards(html)[:24]}
        except Exception:
            return {"list": []}

    # ---------------------------------------------------------- 分类
    def categoryContent(self, tid, pg, filter, extend):
        pg = int(pg or 1)
        ch = CAT_BY_NAME.get(tid, "1")
        url = f"{BASE}/filter?channel={ch}&sort=hot&page={pg}"
        result = {"list": [], "page": pg, "pagecount": 9999, "limit": 12, "total": 9999}
        try:
            html = _http_get(url)
            result["list"] = _parse_cards(html)
            if not result["list"]:
                result["pagecount"] = 1
        except Exception:
            result["pagecount"] = 1
        return result

    # ---------------------------------------------------------- 详情
    def detailContent(self, ids):
        vid = str(ids[0])
        try:
            html = _http_get(f"{BASE}/detail/{vid}.html")
            d = _parse_detail(html)
        except Exception:
            d = {"vod_name": "", "vod_pic": "", "lines": [], "urls": []}
        return {"list": [{
            "vod_id": vid,
            "vod_name": d.get("vod_name", ""),
            "vod_pic": d.get("vod_pic", ""),
            "type_name": d.get("type_name", ""),
            "vod_year": d.get("vod_year", ""),
            "vod_area": d.get("vod_area", ""),
            "vod_actor": d.get("vod_actor", ""),
            "vod_director": d.get("vod_director", ""),
            "vod_content": d.get("vod_content", ""),
            "vod_remarks": "",
            "vod_play_from": "$$$".join(d.get("lines", [])),
            "vod_play_url": "$$$".join(d.get("urls", [])),
        }]}

    # ---------------------------------------------------------- 搜索
    def searchContent(self, key, quick=True, pg=1):
        return self._search(key)

    def searchContentPage(self, key, quick, pg=1):
        return self._search(key)

    def _search(self, key):
        try:
            q = urllib.parse.urlencode({"keyword": key, "field": "all"})
            html = _http_get(f"{BASE}/search?{q}")
            return {"list": _parse_search(html)}
        except Exception:
            return {"list": []}

    # ---------------------------------------------------------- 播放（服务端解析）
    def playerContent(self, flag, pid, vipFlags):
        url, parse = "", 1
        try:
            vodId, playFrom, idx = str(pid).split("$")
            api = (f"{BASE}/api/play-url?vodId={vodId}"
                   f"&playFrom={urllib.parse.quote(playFrom)}"
                   f"&index={urllib.parse.quote(idx)}")
            data = json.loads(_http_get(api, referer=f"{BASE}/detail/{vodId}.html"))
            if str(data.get("code")) == "200" and data.get("url"):
                url = data["url"]
                if re.search(r"\.(m3u8|mp4|flv)(\?|#|$)", url):
                    parse = 0
        except Exception:
            pass
        header = {"User-Agent": UA, "Referer": BASE + "/"}
        return {"parse": parse, "playUrl": "", "url": url, "header": header}

    def localProxy(self, param):
        return [200, "text/plain", "", ""]


# ---------------------------------------------------------------- 本地自测
if __name__ == "__main__":
    sp = Spider()
    sp.init()

    print("== 首页分类 ==")
    print([c["type_name"] for c in sp.homeContent(0)["class"]])

    print("\n== 首页推荐(前5) ==")
    for v in sp.homeVideoContent()["list"][:5]:
        print(" ", v["vod_name"], v["vod_remarks"], v["vod_id"])

    print("\n== 分类: 电视剧 第1页(前5) ==")
    r = sp.categoryContent("电视剧", 1, 0, {})
    print("共", len(r["list"]), "条")
    for v in r["list"][:5]:
        print(" ", v["vod_name"], v["vod_remarks"], v["vod_id"])

    print("\n== 搜索: 诛仙 ==")
    r = sp.searchContent("诛仙")
    for v in r["list"][:5]:
        print(" ", v["vod_name"], v["vod_id"])

    if r["list"]:
        det = sp.detailContent([r["list"][0]["vod_id"]])["list"][0]
        print("\n== 详情:", det["vod_name"], "==")
        print("线路:", det["vod_play_from"].replace("$$$", " | "))
        first = det["vod_play_url"].split("$$$")[0].split("#")[0].split("$", 1)[1]
        play = sp.playerContent("", first, "")
        print("第1集播放地址:", play["url"][:100], "parse:", play["parse"])
