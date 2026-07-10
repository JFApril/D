/*
 * 74体育直播🏟 — 74001.tv 爬虫源 (cat源)
 * @version v7.3.0
 * @updated 2026-06-24 23:00
 * @header({searchable:0,filterable:1,quickSearch:0})
 *
 * ⚡ 信号名：从 <span class="diss"> 提取，含 / 取含「播」字部分（v3.0.3 逻辑）
 * ⚡ 直播判定：比赛时间 ≤ 当前时间 → 🟢 绿点
 * ⚡ 信号URL解密失败时用 liveUrl 兜底
 * ⚡ 分类过滤：🔥全部 ⚽足球(fenlei_1) 🏀篮球(fenlei_2) 🏟综合(其他)
 */

const HOST = 'https://www.74001.tv';
const LOGO = 'https://www.74003.tv/~static/www/img/logon.png';
const UA = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/140.0.0.0 Safari/537.36';
const CHECK_KEY = '925-310-suijishu';

/* ===== 工具函数 ===== */
function clean(s) {
    return String(s || '').replace(/<script[\s\S]*?<\/script>/gi, '').replace(/<style[\s\S]*?<\/style>/gi, '')
        .replace(/<[^>]+>/g, '').replace(/&nbsp;/g, ' ').replace(/&amp;/g, '&')
        .replace(/&quot;/g, '"').replace(/&#39;/g, "'").replace(/\s+/g, ' ').trim();
}

function absUrl(url) {
    if (!url) return LOGO;
    url = String(url).trim();
    if (/^https?:\/\//i.test(url)) return url;
    if (url.indexOf('//') === 0) return 'https:' + url;
    if (url[0] === '/') return HOST.replace(/\/$/, '') + url;
    return HOST.replace(/\/$/, '') + '/' + url;
}

function safeJson(t, d) {
    try {
        return JSON.parse(t || '{}');
    } catch (e) {
        return d || {};
    }
}

function headers() {
    return {
        'User-Agent': UA,
        'Referer': HOST + '/',
        'Accept': '*/*',
        'Accept-Language': 'zh-CN,zh;q=0.9'
    };
}

async function fetchText(url, timeout) {
    const hd = headers();
    const to = timeout || 8000;
    try {
        if (typeof Java !== 'undefined' && Java && Java.req) {
            const r = await Java.req(url, {
                headers: hd,
                timeout: to
            });
            if (typeof r === 'string') return r;
            return String((r && (r.body || r.content || r.data)) || '');
        }
        const r2 = await req(url, {
            headers: hd,
            timeout: to
        });
        if (typeof r2 === 'string') return r2;
        return String((r2 && (r2.content || r2.body || r2.data)) || '');
    } catch (e) {
        return '';
    }
}

/* ===== 信号解密 ===== */
function decryptSignal(b64) {
    if (!b64) return null;
    try {
        var urlDecoded = decodeURIComponent(b64);
        var r = atob(urlDecoded).split('::');
        var t = r[0];
        var n = r[1];
        if (t !== CHECK_KEY) return null;
        n = n.replace(/ftp/g, 'http');
        n = n.replace(/\*/g, '/');
        n = n.replace(/&amp/g, 'www');
        n = n.replace(/&nbsp/g, 'com');
        n = n.replace(/!/g, '.');
        return n;
    } catch (e) {
        return null;
    }
}

/**
 * 从 /live/ 页面提取信号
 * v3.0.3 逻辑：名字含 / 时取含「播」字的部分；无则取第一个
 */
function extractSignalsFromLive(html) {
    const signals = [];
    if (!html) return signals;

    var pos = 0;
    while (true) {
        var ddStart = html.indexOf('<dd', pos);
        if (ddStart === -1) break;
        var ddEnd = html.indexOf('</dd>', ddStart);
        if (ddEnd === -1) break;
        var block = html.substring(ddStart, ddEnd + 5);
        pos = ddEnd + 5;

        var typeMatch = block.match(/cg-bf-zfr\s*=\s*["'](\d)["']/i);
        var signalType = typeMatch ? typeMatch[1] : '0';

        var nzgcMatch = block.match(/nz-g-c\s*=\s*["']([^"']*)["']/i);
        var nzgcVal = nzgcMatch ? nzgcMatch[1] : '';

        var nzgcAMatch = block.match(/nz-g-ca\s*=\s*["']([^"']*)["']/i);
        var nzgcAVal = nzgcAMatch ? nzgcAMatch[1] : '';

        var nzgcDMatch = block.match(/nz-g-cd\s*=\s*["']([^"']*)["']/i);
        var nzgcDVal = nzgcDMatch ? nzgcDMatch[1] : '';

        // 提取信号名：只取第一个 <span class="diss"> 的值
        var firstMatch = block.match(/<span[^>]*class\s*=\s*["'][^"']*diss[^"']*["'][^>]*>([^<]*)<\/span>/i);
        var rawName = firstMatch ? clean(firstMatch[1]) : '';

        // v3.0.3: 名字含 / 时取含「播」字的部分；无则取第一个
        var signalName = '';
        if (rawName) {
            var parts = rawName.split('/');
            for (var pi = 0; pi < parts.length; pi++) {
                var p = parts[pi].trim();
                if (p.indexOf('播') !== -1) {
                    signalName = p;
                    break;
                }
            }
            if (!signalName) signalName = parts[0].trim();
        }
        if (!signalName) {
            signalName = '直播' + (signals.length + 1);
        }

        var sig = {
            type: signalType,
            nzgc: nzgcVal,
            nzgcA: nzgcAVal,
            nzgcD: nzgcDVal,
            name: signalName
        };

        var url = decryptSignal(nzgcVal);
        if (url && (url.indexOf('http://') === 0 || url.indexOf('https://') === 0)) {
            sig.url = url;
            sig.playable = true;
        }
        // 备用：nz-g-ca
        if (!sig.playable && nzgcAVal) {
            var ca = nzgcAVal.replace(/\*/g, '/').replace(/&/g, '');
            if (ca.indexOf('http://') === 0 || ca.indexOf('https://') === 0) {
                sig.url = ca;
                sig.playable = true;
            }
        }
        // 备用：nz-g-cd
        if (!sig.playable && nzgcDVal) {
            var decD = decryptSignal(nzgcDVal);
            if (decD && (decD.indexOf('http://') === 0 || decD.indexOf('https://') === 0)) {
                sig.url = decD;
                sig.playable = true;
            }
        }

        signals.push(sig);
    }

    return signals;
}

/* ===== 分类定义 ===== */
function getClasses() {
    return [{
            type_id: '0',
            type_name: '🔥热门'
        },
        {
            type_id: '1',
            type_name: '⚽足球'
        },
        {
            type_id: '2',
            type_name: '🏀篮球'
        },
        {
            type_id: '3',
            type_name: '🏟综合体育'
        }
    ];
}

/* ===== 首页/分类 ===== */
async function init(cfg) {}
async function home(filter) {
    return JSON.stringify({
        class: getClasses(),
        filters: {}
    });
}
async function homeVod() {
    return await category('0', 1, {}, {});
}

async function category(tid, pg, filter, extend) {
    tid = String((extend && extend.cateId) || tid || '0');
    pg = parseInt(pg) || 1;
    let list = [];

    try {
        const html = await fetchText(HOST + '/?_t=' + Date.now());
        if (!html) return JSON.stringify({
            code: 1,
            msg: '获取首页失败',
            page: 1,
            pagecount: 1,
            limit: 100,
            total: 0,
            list: []
        });

        const allMatches = [];
        let pos = 0;

        while (true) {
            const aStart = html.indexOf('<a', pos);
            if (aStart === -1) break;
            const aEnd = html.indexOf('</a>', aStart);
            if (aEnd === -1) break;
            const block = html.substring(aStart, aEnd + 4);
            pos = aEnd + 4;

            const hrefMatch = block.match(/href\s*=\s*["'](?:\/bofang\/|\/live\/)(\d+)["']/i);
            if (!hrefMatch) continue;
            const id = hrefMatch[1];

            var dateStr = '';
            const dateMatch = block.match(/nzw-o-t\s*=\s*["']([^"']*)["']/i);
            if (dateMatch) {
                let raw = dateMatch[1].trim();
                const d = raw.match(/^(\d{4}-\d{2}-\d{2})/);
                if (d) dateStr = d[1].substring(5);
            }

            // v7.3.0: 时间比较判定已开赛
            var isLive = false;

            var fenlei = '0';
            var fenleiM = block.match(/fenlei_(\d)\.png/);
            if (fenleiM) fenlei = fenleiM[1];

            if (tid === '1' && fenlei !== '1') continue;
            if (tid === '2' && fenlei !== '2') continue;
            if (tid === '3' && (fenlei === '1' || fenlei === '2')) continue;

            var league = '';
            var emM = block.match(/<em>([^<]*)<\/em>/i);
            if (emM) league = clean(emM[1]);

            var time = '';
            var iM = block.match(/<i>([^<]*)<\/i>/i);
            if (iM) {
                var iVal = clean(iM[1]);
                if (/^\d{2}:\d{2}$/.test(iVal)) time = iVal;
            }

            // 🟢 时间比较
            if (dateStr && time) {
                var dateParts = dateStr.split('-');
                var timeParts = time.split(':');
                if (dateParts.length === 2 && timeParts.length === 2) {
                    var matchTime = new Date(2026, parseInt(dateParts[0], 10) - 1, parseInt(dateParts[1], 10),
                        parseInt(timeParts[0], 10), parseInt(timeParts[1], 10));
                    var now = new Date();
                    if (!isNaN(matchTime.getTime()) && matchTime <= now) {
                        isLive = true;
                    }
                }
            }

            var shortName, vodPic;
            const isTitleMatch = /section[^>]*class\s*=\s*["'][^"']*titlematch[^"']*["']/i.test(block);

            if (isTitleMatch) {
                var titleM = block.match(/<p[^>]*class\s*=\s*["'][^"']*title[^"']*["'][^>]*>([^<]*)<\/p>/i);
                shortName = titleM ? clean(titleM[1]) : (league || '体育直播');
                vodPic = LOGO;
            } else {
                var homeTeam = '',
                    awayTeam = '';

                var homeM = block.match(/<div[^>]*class\s*=\s*["'][^"']*team[^"']*zhudui[^"']*["'][^>]*>[\s\S]*?<p>([^<]*)<\/p>/i);
                var awayM = block.match(/<div[^>]*class\s*=\s*["'][^"']*team[^"']*kedui[^"']*["'][^>]*>[\s\S]*?<p>([^<]*)<\/p>/i);
                if (homeM) homeTeam = clean(homeM[1]);
                if (awayM) awayTeam = clean(awayM[1]);

                if (!homeTeam && !awayTeam) {
                    var allP = block.match(/<p>([^<]*)<\/p>/g);
                    if (allP && allP.length >= 2) {
                        var candidates = [];
                        for (var pi = 0; pi < allP.length; pi++) {
                            var pText = clean(allP[pi].replace(/<\/?p>/g, ''));
                            if (pText && pText !== 'VS' && pText !== '视频直播' && pText !== league && !/^\d{2}:\d{2}$/.test(pText)) {
                                candidates.push(pText);
                            }
                        }
                        if (candidates.length >= 2) {
                            homeTeam = candidates[0];
                            awayTeam = candidates[1];
                        } else if (candidates.length === 1) {
                            homeTeam = candidates[0];
                        }
                    }
                }

                if (!homeTeam && !awayTeam) continue;

                var homePic = '',
                    awayPic = '';
                var zBlock = block.match(/<div[^>]*class\s*=\s*["'][^"']*team[^"']*zhudui[^"']*["'][^>]*>[\s\S]*?<\/div>/i);
                if (zBlock) {
                    var imgM = zBlock[0].match(/op-zfr-a-g\s*=\s*["']([^"']*)["']/);
                    if (imgM) homePic = imgM[1];
                }
                var kBlock = block.match(/<div[^>]*class\s*=\s*["'][^"']*team[^"']*kedui[^"']*["'][^>]*>[\s\S]*?<\/div>/i);
                if (kBlock) {
                    var imgM2 = kBlock[0].match(/op-zfr-a-g\s*=\s*["']([^"']*)["']/);
                    if (imgM2) awayPic = imgM2[1];
                }

                vodPic = homePic || awayPic || LOGO;
                shortName = homeTeam + ' vs ' + awayTeam;
            }

            var datePrefix = dateStr ? '[' + dateStr + '] ' : '';
            var livePrefix = isLive ? '🟢 ' : '';
            var remarks = livePrefix + datePrefix + (league ? league + ' ' : '') + (time ? time : '');

            var vodId = '74|' + id + '|' + encodeURIComponent(shortName);

            allMatches.push({
                vod_id: vodId,
                vod_name: shortName,
                vod_pic: absUrl(vodPic),
                vod_remarks: remarks,
                _dateVal: dateStr || '',
                _timeVal: time || '99:99'
            });
        }

        allMatches.sort(function(a, b) {
            if (a._dateVal !== b._dateVal) return a._dateVal.localeCompare(b._dateVal);
            return a._timeVal.localeCompare(b._timeVal);
        });

        list = allMatches;
    } catch (e) {}

    return JSON.stringify({
        code: 1,
        msg: '赛程列表',
        page: pg,
        pagecount: 1,
        limit: 100,
        total: list.length,
        list
    });
}

/* ===== 详情 ===== */
async function detail(ids) {
    const id = String(Array.isArray(ids) ? ids[0] : ids || '');
    const parts = id.split('|');
    if (parts.length < 2 || parts[0] !== '74') {
        return JSON.stringify({
            code: 1,
            msg: 'ok',
            page: 1,
            pagecount: 1,
            limit: 1,
            total: 0,
            list: []
        });
    }

    const matchId = parts[1];
    const name = parts[2] ? decodeURIComponent(parts.slice(2).join('|')) : '体育直播';
    const signals = [];
    const liveUrl = HOST + '/live/' + matchId;

    try {
        const liveHtml = await fetchText(liveUrl, 10000);
        if (liveHtml) {
            const sigs = extractSignalsFromLive(liveHtml);
            for (const sig of sigs) {
                signals.push(sig);
            }
        }
    } catch (e) {}

    let playUrlStr;
    if (signals.length > 0) {
        var lines = [];
        for (var si = 0; si < signals.length; si++) {
            var s = signals[si];
            var sName = s.name || ('直播' + (si + 1));
            var sUrl;

            if (s.playable && s.url) {
                sUrl = s.url;
            } else {
                sUrl = liveUrl;
            }
            lines.push(sName + '$' + sUrl);
        }
        playUrlStr = lines.join('#');
    } else {
        playUrlStr = name + '$' + liveUrl;
    }

    return JSON.stringify({
        code: 1,
        msg: '直播详情',
        page: 1,
        pagecount: 1,
        limit: 1,
        total: 1,
        list: [{
            vod_id: id,
            vod_name: name,
            vod_pic: LOGO,
            vod_remarks: signals.length > 0 ? signals.length + '个信号源' : '暂无信号',
            vod_play_from: '74直播',
            vod_play_url: playUrlStr,
            vod_content: '74体育 · ' + name
        }]
    });
}

/* ===== 播放 ===== */
async function play(flag, id, flags) {
    const url = String(id || '');
    if (/\.(m3u8|flv|mp4)(\?|$)/i.test(url)) {
        return JSON.stringify({
            parse: 0,
            url: url,
            header: {
                'User-Agent': UA,
                'Referer': HOST + '/',
                'Origin': HOST
            }
        });
    }
    return JSON.stringify({
        parse: 1,
        url: url,
        header: {
            'User-Agent': UA,
            'Referer': HOST + '/',
            'Origin': HOST
        }
    });
}

async function search(wd, quick, pg) {
    return JSON.stringify({
        code: 1,
        msg: '无搜索',
        page: 1,
        pagecount: 1,
        limit: 20,
        total: 0,
        list: []
    });
}

/* ===== 导出包装 ===== */
async function homeContent(f) {
    return safeJson(await home(f), {
        class: [],
        filters: {}
    });
}
async function homeVideoContent() {
    return safeJson(await homeVod(), {
        list: []
    });
}
async function categoryContent(tid, pg, f, ext) {
    return safeJson(await category(tid, pg, f, ext || {}), {
        list: []
    });
}
async function detailContent(ids) {
    return safeJson(await detail(ids), {
        list: []
    });
}
async function searchContent(wd, q, pg) {
    return safeJson(await search(wd, q, pg || 1), {
        list: []
    });
}
async function playerContent(flag, id, flags) {
    return safeJson(await play(flag, id, flags), {
        parse: 1,
        url: id
    });
}

export function __jsEvalReturn() {
    return {
        init,
        home,
        homeVod,
        category,
        search,
        detail,
        play,
        homeContent,
        homeVideoContent,
        categoryContent,
        detailContent,
        searchContent,
        playerContent
    };
}