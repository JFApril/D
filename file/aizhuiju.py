# -*- coding: utf-8 -*-
# ============================================================
# 爱追剧人(zhuijuren.com) OK影视爬虫插件
# 来源说明：www.aystv.cc 仅为 App 下载落地页，其数据服务端为
# 自研 Flutter API（host 不明文，无法直连）；本插件以其官网
# 追剧人 ZhuiJuRen.Com 网页版为数据源，内容一致。
# 基于 base.spider 协议，方法签名与模板3.py 一致。
# ============================================================
import re
import requests
from requests.adapters import HTTPAdapter
from requests.packages.urllib3.util.retry import Retry
requests.packages.urllib3.disable_warnings()

from base.spider import Spider

class Spider(Spider):
    def getName(self):
        return "爱追剧人"

    def init(self, extend=""):
        super().init(extend)
        self.site_url = "https://zhuijuren.com"
        self.headers = {
            "User-Agent": "Mozilla/5.0 (Linux; Android 10; Mobile) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/118.0.0.0 Mobile Safari/537.36",
            "Referer": self.site_url,
            "Accept-Language": "zh-CN,zh;q=0.9"
        }
        self.sess = requests.Session()
        self.sess.mount("https://", HTTPAdapter(max_retries=Retry(total=3, backoff_factor=1, status_forcelist=[500, 502, 503, 504])))
        self.sess.mount("http://", HTTPAdapter(max_retries=Retry(total=3, backoff_factor=1, status_forcelist=[500, 502, 503, 504])))
        self.page_size = 30
        self.total = 9999
        # 站点页面编码（GB18030/GBK）
        self.charset = "gb18030"
        # 分类映射：tid -> 分类页路径（首页分类导航）
        self.cate_map = {
            "/DianYing/": "电影",
            "/DianShiJu/": "剧集",
            "/DuanJu/": "短剧",
            "/DongMan/": "动漫",
            "/Hot/": "热榜",
            "/New/": "更新",
        }

    def fetch(self, url, timeout=12):
        try:
            res = self.sess.get(url, headers=self.headers, timeout=timeout, verify=False)
            return res
        except Exception:
            return None

    # ---------- 通用解析 ----------
    def _abs(self, url):
        """相对/大小写异常链接补全为绝对地址"""
        url = url.strip()
        if url.startswith("//"):
            return "https:" + url
        if url.lower().startswith(("http://", "https://")):
            return url
        return self.site_url + (url if url.startswith("/") else "/" + url)

    def _decode(self, res):
        if not res or not res.ok:
            return ""
        return res.content.decode(self.charset, errors="ignore")

    def _parse_list_item(self, item_html):
        """解析列表/搜索卡片，返回 (vod_id, name, pic, remarks)"""
        m = re.search(r'href="(/Video/\d+/")', item_html)
        title = re.search(r'title="([^"]+)"', item_html)
        pic_m = re.search(r'data-original="([^"]+)"', item_html)
        name_m = re.search(r'<strong>([^<]+)</strong>', item_html) or title
        note = re.search(r'class="module-item-note">([^<]*)</div>', item_html)
        if not (m and name_m):
            return None
        name = re.sub(r'\s+\d{4}$', '', name_m.group(1).strip())
        return (m.group(1), name,
                self._abs(pic_m.group(1)) if pic_m else "",
                note.group(1).strip() if note else "")

    # ---------- 首页分类 ----------
    def homeContent(self, filter):
        cate_list = [{"type_name": n, "type_id": t} for t, n in self.cate_map.items()]
        return {"class": cate_list}

    # ---------- 分类列表 ----------
    def categoryContent(self, tid, pg, filter, extend):
        pg = int(pg) if str(pg).isdigit() else 1
        # 第1页为 /DianYing/，后续页 /DianYing/2/ /DianYing/3/ ...
        if pg <= 1:
            list_url = self.site_url + tid
        else:
            list_url = self.site_url + tid.rstrip("/") + f"/{pg}/"
        res = self.fetch(list_url)
        raw_html = self._decode(res)
        # 解析所有列表容器 module-items（首页聚合页含多个分区 tab），拼接后只取卡片
        html = raw_html
        mboxes = re.findall(r'<div class="module-items[^"]*"[^>]*>([\s\S]*?)(?=<div class="module-(?:main|heading|items)[ "]|<div class="footer|</body)', raw_html)
        if mboxes:
            html = "".join(mboxes)
        video_list = []
        # 列表卡片：poster 卡片（列表/分类页）与 card 卡片（热榜/更新/搜索页）
        seen_id = set()
        # (1) poster 卡片：<a href="/Video/xxx/" title="..." class="module-poster-item module-item">...</a>
        for match in re.finditer(r'<a href="(/Video/\d+/)"[^>]*class="module-poster-item[^"]*"[^>]*>.*?</a>', html, re.S):
            item = match.group(0)
            parsed = self._parse_list_item(item)
            if parsed:
                v_id, v_name, v_pic, v_rm = parsed
                if v_id in seen_id:
                    continue
                seen_id.add(v_id)
                video_list.append({
                    "vod_id": self.site_url + v_id,
                    "vod_name": v_name,
                    "vod_pic": v_pic,
                    "vod_remarks": v_rm,
                })
        # (2) card 卡片：<div class="module-card-item module-item ...">...</div>
        for match in re.finditer(r'<div class="module-card-item module-item[^"]*"[^>]*>([\s\S]*?)(?=<div class="module-card-item[ ">]|<div class="module-heading|<div class="module-main|<div class="footer|</body|\Z)', html, re.S):
            parsed = self._parse_list_item(match.group(1))
            if parsed:
                v_id, v_name, v_pic, v_rm = parsed
                if v_id in seen_id:
                    continue
                seen_id.add(v_id)
                video_list.append({
                    "vod_id": self.site_url + v_id,
                    "vod_name": v_name,
                    "vod_pic": v_pic,
                    "vod_remarks": v_rm,
                })
        # 总页数：分页链接 /DianYing/N/（用整页原始 HTML 解析）
        pagecount = pg
        pag_out = re.findall(r'href="' + re.escape(tid.rstrip("/")) + r'/(\d+)/"[^>]*>\s*(\d+)\s*<', raw_html)
        if pag_out:
            pagecount = max(int(x[0]) for x in pag_out)
        if len(video_list):
            pagecount = max(pagecount, pg)
        # P1 为聚合首页无分页链接，保底翻页入口（实际总页数在 P2+ 页可见）
        if pg <= 1 and pagecount <= 1 and len(video_list):
            pagecount = 2
        return {
            "list": video_list,
            "page": pg,
            "pagecount": pagecount,
            "limit": self.page_size,
            "total": self.total
        }

    # ---------- 详情 ----------
    def detailContent(self, ids):
        vod_id = ids[0] if ids else ""
        if not vod_id:
            return {"list": [{"vod_name": "视频ID为空"}]}
        res = self.fetch(vod_id)
        html = self._decode(res)
        if not html:
            return {"list": [{"vod_id": vod_id, "vod_name": "视频详情解析失败"}]}
        # 片名
        name = ""
        m = re.search(r'<h1>([^<]+)</h1>', html)
        if m:
            name = re.sub(r'\s+\d{4}$', '', m.group(1).strip())
        elif m := re.search(r'<div class="module-info-heading">\s*<h1[^>]*>([^<]+)</h1>', html):
            name = re.sub(r'\s+\d{4}$', '', m.group(1).strip())
        # 海报
        pic = ""
        m = re.search(r'class="module-item-pic"><img[^>]*data-original="([^"]+)"', html) \
            or re.search(r'data-original="([^"]+)"[^>]*alt="' + re.escape(name) + '"', html)
        if m:
            pic = self._abs(m.group(1))
        # 简介
        intro = ""
        m = re.search(r'module-info-introduction-content">\s*<p>([\s\S]*?)</p>', html)
        if m:
            intro = re.sub(r'<[^>]+>', '', m.group(1)).strip()
        # 分类标签
        type_name = ""
        m = re.search(r'class="module-info-tag-link">\s*<a[^>]*href="(/DianYing/|/DianShiJu/|/DuanJu/|/DongMan/)"', html)
        if m:
            type_name = self.cate_map.get(m.group(1), "")
        # 导演/主演
        actor = ""
        m = re.search(r'class="module-info-item"[\s\S]{0,400}?<span class="module-info-item-title">(?:主演|演员)：</span>\s*<div class="module-info-item-content">([\s\S]*?)</div>', html)
        if m:
            actor = re.sub(r'<[^>]+>', '', m.group(1)).strip()
        # 选集列表：取第一个播放源分组（module-play-list-content）
        play_url = ""
        play_match = re.search(r'<div class="module-play-list-content[^"]*"[^>]*>([\s\S]*?)</div>\s*</div>', html)
        if play_match:
            eps = re.findall(r'<a class="module-play-list-link" href="(/OPlayer/\d+/\d+-\d+/)"[^>]*title="[^"]*"[^>]*>\s*<span>([^<]+)</span>\s*</a>', play_match.group(1))
            # 去重保序
            seen, items = set(), []
            for eurl, ename in eps:
                if ename in seen:
                    continue
                seen.add(ename)
                items.append(ename + "$" + self.site_url + eurl)
            if items:
                play_url = "#".join(items)
        play_from = "高清HD"
        detail_info = {
            "vod_id": vod_id,
            "vod_name": name or "未知名称",
            "vod_pic": pic,
            "vod_remarks": "",
            "type_name": type_name,
            "vod_content": intro,
            "vod_actor": actor,
            "vod_play_from": play_from,
            "vod_play_url": play_url,
        }
        return {"list": [detail_info]}

    # ---------- 搜索 ----------
    def searchContent(self, key, quick, pg=1):
        pg = int(pg) if str(pg).isdigit() else 1
        search_url = f"{self.site_url}/So/?S={requests.utils.quote(key.encode('gb18030'))}"
        res = self.fetch(search_url)
        raw_html = self._decode(res)
        # 只取搜索结果容器（module-card-items）内容，排除"大家都在搜"推荐
        html = raw_html
        mbox = re.search(r'<div class="module-items[^"]*"[^>]*>([\s\S]*?)(?=<div class="module-(?:main|heading|items)[ "]|<div class="footer|</body)', raw_html)
        if mbox:
            html = mbox.group(1)
        video_list = []
        # 搜索卡片：poster 与 card 两种形态
        seen_id = set()
        for match in re.finditer(r'<a href="(/Video/\d+/)"[^>]*class="module-poster-item[^"]*"[^>]*>.*?</a>', html, re.S):
            parsed = self._parse_list_item(match.group(0))
            if parsed:
                v_id, v_name, v_pic, v_rm = parsed
                if v_id in seen_id:
                    continue
                seen_id.add(v_id)
                video_list.append({
                    "vod_id": self.site_url + v_id,
                    "vod_name": v_name,
                    "vod_pic": v_pic,
                    "vod_remarks": v_rm,
                })
            if len(video_list) >= 40:
                break
        for match in re.finditer(r'<div class="module-card-item module-item[^"]*"[^>]*>([\s\S]*?)(?=<div class="module-card-item[ ">]|<div class="module-heading|<div class="module-main|<div class="footer|</body|\Z)', html, re.S):
            parsed = self._parse_list_item(match.group(1))
            if parsed:
                v_id, v_name, v_pic, v_rm = parsed
                if v_id in seen_id:
                    continue
                seen_id.add(v_id)
                video_list.append({
                    "vod_id": self.site_url + v_id,
                    "vod_name": v_name,
                    "vod_pic": v_pic,
                    "vod_remarks": v_rm,
                })
            if len(video_list) >= 40:
                break
        return {
            "list": video_list,
            "page": pg,
            "pagecount": 1 if video_list else pg,
            "limit": 40,
            "total": len(video_list) if len(video_list) < 999 else 999
        }

    # ---------- 播放解析 ----------
    def playerContent(self, flag, id, vipFlags):
        play_url = id.split("$")[1] if "$" in id else id
        if not play_url:
            return {"parse": 0, "url": "", "header": self.headers}
        try:
            # 1) 播放页 -> 注入脚本 src="/%5a%70%6c%61%79%65%72/?zz=..&C=..&S=..&N=标题"（URL编码，N 含中文）
            res = self.fetch(play_url)
            html = self._decode(res)
            m = re.search(r'document\.write\([^;]*?src="([^"]*%5a%70%6c%61%79%65%72[^"]*)"', html) \
                or re.search(r'src="(/%5a%70%6c%61%79%65%72/[^"]+)"', html)
            if not m:
                # 通用兜底：任意含 /%5a%70%6c%61%79%65%72 的 src
                m = re.search(r'(?:src|href)="([^"]*%5a%70%6c%61%79%65%72[^"]*)"', html)
            if not m:
                return {"parse": 0, "url": "", "header": self.headers}
            zpath = m.group(1)
            # 2) Zplayer 层（N 参数需 GBK 编码）
            zpath_dec = zpath
            if "%" in zpath:
                zpath_dec = re.sub(r'%[0-9a-fA-F]{2}', lambda x: bytes([int(x.group(0)[1:], 16)]).decode('latin-1'), zpath)
            parts = zpath_dec.split("&")
            enc_parts = []
            for p in parts:
                if p.startswith("N="):
                    enc_parts.append("N=" + requests.utils.quote(p[2:].encode('gb18030')))
                else:
                    enc_parts.append(p)
            zurl = self.site_url + "&".join(enc_parts)
            hdr = dict(self.headers)
            hdr["Referer"] = play_url
            res2 = self.sess.get(zurl, headers=hdr, timeout=12, verify=False)
            html2 = res2.content.decode(self.charset, errors="ignore").replace("\\/", "/").replace('\\"', '"')
            # 3) B 层（iframe 指向 /Zplayer/B/?zz=..&C=..&S=..）Referer 必须为 /Zplayer/ 路径
            bm = re.search(r'src="(/Zplayer/B/[^"]*)"', html2)
            if not bm:
                bm = re.search(r'Zplayer/B/\?[^"\'\s\\]*', html2)
            if not bm:
                return {"parse": 0, "url": "", "header": self.headers}
            bpath = bm.group(1)
            hdr2 = dict(self.headers)
            hdr2["Referer"] = self.site_url + "/Zplayer/"
            res3 = self.sess.get(self.site_url + bpath, headers=hdr2, timeout=12, verify=False)
            html3 = res3.content.decode("utf-8", errors="ignore")
            mm = re.search(r"src:\s*'([^']+)'", html3)
            if not mm:
                return {"parse": 0, "url": "", "header": self.headers}
            final_url = mm.group(1)
            hdr3 = dict(self.headers)
            hdr3["Referer"] = self.site_url + "/"
            return {"parse": 0, "url": final_url, "header": hdr3}
        except Exception:
            return {"parse": 0, "url": "", "header": self.headers}
