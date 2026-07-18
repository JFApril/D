// 74体育直播 V10.0 - 完整翻译Python信号处理逻辑
const HOST = 'https://www.74001.tv';
const LOGO = 'https://www.74003.tv/~static/www/img/logon.png';
const PLAY_HOST = 'https://play.74001.tv';
const UA = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/140.0.0.0 Safari/537.36';
const CHECK_KEY = '925-310-suijishu';
const ENCODE_MAP = 'UT9kQDKZsjIOezPXha7xYG5Jyfg2b8Fv4ASmCw1B0HoRu6cr3WtVnlLpEqMidN';

function getHeaders(ref) {
    return {
        'User-Agent': UA,
        'Referer': ref || HOST + '/',
        'Accept': '*/*',
        'Accept-Language': 'zh-CN,zh;q=0.9'
    };
}

async function fetchText(url, ref) {
    const hd = getHeaders(ref || HOST + '/');
    try {
        if (typeof Java !== 'undefined' && Java && Java.req) {
            const r = await Java.req(url, { headers: hd });
            if (typeof r === 'string') return r;
            const code = Number((r && (r.statusCode || r.status || r.code)) || 0);
            const loc = r && r.headers && r.headers.location;
            if (loc && code >= 300 && code < 400) return fetchText(absUrl(loc, url), ref);
            return String((r && (r.body || r.content || r.data)) || '');
        }
        const r2 = await req(url, { headers: hd });
        if (typeof r2 === 'string') return r2;
        const code2 = Number((r2 && (r2.statusCode || r2.status || r2.code)) || 0);
        const loc2 = r2 && r2.headers && r2.headers.location;
        if (loc2 && code2 >= 300 && code2 < 400) return fetchText(absUrl(loc2, url), ref);
        return String((r2 && (r2.content || r2.body || r2.data)) || '');
    } catch (e) {
        return '';
    }
}

function absUrl(u, base) {
    if (!u) return '';
    if (/^https?:\/\//i.test(u)) return u;
    try {
        const b = new URL(base);
        if (u.startsWith('//')) return b.protocol + u;
        return b.origin + (u.startsWith('/') ? '' : '/') + u;
    } catch (e) { return u; }
}

function randomString(length) {
    const chars = 'ABCDEFGHJKMNPQRSTWXYZabcdefhijkmnprstwxyz2345678';
    let r = '';
    for (let i = 0; i < length; i++) r += chars[Math.floor(Math.random() * chars.length)];
    return r;
}

function newSrc(s, pos, ins) { return s.substring(0, pos) + ins + s.substring(pos); }

function encodeSignal(s) {
    let result = '';
    for (let i = 0; i < s.length; i++) {
        const ch = s[i];
        const idx = ENCODE_MAP.indexOf(ch);
        const c = idx !== -1 ? ENCODE_MAP[(idx + 3) % 62] : ch;
        result += ENCODE_MAP[Math.floor(Math.random() * 62)] + c + ENCODE_MAP[Math.floor(Math.random() * 62)];
    }
    return result;
}

function decryptSignal(b64Str) {
    if (!b64Str) return null;
    try {
        let urlDecoded = b64Str.replace(/\\\//g, '/').replace(/_/g, '/').replace(/-/g, '+');
        if (urlDecoded.length % 4 !== 0) urlDecoded += '='.repeat(4 - (urlDecoded.length % 4));
        const decoded = atob(urlDecoded);
        const parts = decoded.split('::');
        if (parts.length < 2) return null;
        const key = parts[0];
        let val = parts[1];
        if (key !== CHECK_KEY) return null;
        val = val.replace(/ftp/g, 'http');
        if (val.indexOf(':**') !== -1) val = val.replace(':**', '://');
        else if (val.indexOf('**') !== -1) {
            const idx = val.indexOf('**');
            if (idx >= 4 && val.substring(idx - 4, idx) === 'http') val = val.substring(0, idx - 4) + 'http://' + val.substring(idx + 2);
            else val = val.replace('**', '://');
        }
        val = val.replace(/\*/g, '/').replace(/&amp/g, 'www').replace(/&nbsp/g, 'com').replace(/!/g, '.');
        if (!val.startsWith('http')) return null;
        return val;
    } catch (e) { return null; }
}

function cleanText(s) {
    return String(s || '')
        .replace(/<script[\s\S]*?<\/script>/gi, '')
        .replace(/<style[\s\S]*?<\/style>/gi, '')
        .replace(/<[^>]+>/g, '')
        .replace(/&nbsp;/g, ' ').replace(/&amp;/g, '&').replace(/"/g, '"').replace(/&#39;/g, "'")
        .replace(/\s+/g, ' ').trim();
}

function extractSecrtFromLive(matchId) {
    return fetchText(HOST + '/live/' + matchId, HOST).then(html => {
        if (!html) return '';
        let m = /data-secrt\s*=\s*["']([^"']*)["']/i.exec(html);
        if (m && m[1]) return m[1];
        m = /secrt\s*=\s*["']([^"']*)["']/i.exec(html);
        if (m && m[1]) return m[1];
        m = /<iframe[^>]*data-secrt\s*=\s*["']([^"']*)["']/i.exec(html);
        if (m && m[1]) return m[1];
        return '';
    }).catch(() => '');
}

function extractSignals(html) {
    const signals = [];
    if (!html) return signals;
    let pcStart = html.indexOf('id="pcmode"');
    if (pcStart === -1) pcStart = 0;
    let pcEnd = html.indexOf('id="wapmode"', pcStart);
    if (pcEnd === -1) pcEnd = html.length;
    const block = html.substring(pcStart, pcEnd);
    const ddPattern = /<dd[^>]*>[\s\S]*?<\/dd>/gi;
    let ddMatch;
    while ((ddMatch = ddPattern.exec(block)) !== null) {
        const ddHtml = ddMatch[0];
        const typeM = /cg-bf-zfr\s*=\s*["'](\d)["']/i.exec(ddHtml);
        const signalType = typeM ? typeM[1] : '0';
        let nzgc = '';
        const nzgcM = /nz-g-c\s*=\s*["']([^"']*)["']/i.exec(ddHtml);
        if (nzgcM && nzgcM[1]) nzgc = nzgcM[1];
        if (!nzgc) {
            const nzgcM2 = /nz-g-ca\s*=\s*["']([^"']*)["']/i.exec(ddHtml);
            if (nzgcM2 && nzgcM2[1]) nzgc = nzgcM2[1];
        }
        if (nzgc && (nzgc.indexOf('%3D') !== -1 || nzgc.indexOf('%3d') !== -1)) {
            try { nzgc = decodeURIComponent(nzgc); } catch (e) {}
        }
        const nameM = /class\s*=\s*["'][^"']*diss[^"']*["'][^>]*>([^<]*)</i.exec(ddHtml);
        const rawName = nameM ? cleanText(nameM[1]) : '';
        let signalName = '';
        if (rawName) {
            const parts = rawName.split('/');
            for (let p of parts) {
                p = p.trim();
                if (p.indexOf('播') !== -1) { signalName = p; break; }
            }
            if (!signalName) signalName = rawName.split('/')[0].trim();
        }
        if (!signalName) signalName = '直播' + (signals.length + 1);
        const frmM = /zr-cg-t\s*=\s*["']([^"']*)["']/i.exec(ddHtml);
        const wfM = /zr-zfr-y\s*=\s*["']([^"']*)["']/i.exec(ddHtml);
        const yrM = /zfr-c-at\s*=\s*["']([^"']*)["']/i.exec(ddHtml);
        signals.push({
            type: signalType,
            nzgc: nzgc,
            name: signalName,
            frm: frmM ? frmM[1] : '',
            wf: wfM ? wfM[1] : '',
            yr: yrM ? yrM[1] : ''
        });
    }
    return signals;
}

async function buildSignalUrl(sig, matchId) {
    if (sig.type === '0') {
        try {
            let secrt = await extractSecrtFromLive(matchId);
            if (!secrt) secrt = 'UT9k';
            const fullSecrt = 'w42Fw5' + secrt;
            const bn = encodeSignal(fullSecrt);
            const d = randomString(5);
            const minS = randomString(4);
            const right = randomString(8);
            const sfk = d + newSrc(sig.nzgc, 4, minS) + right;
            const frm = sig.frm || '1';
            const wf = sig.wf || '';
            const yr = sig.yr || '1';
            const playUrl = PLAY_HOST + '/?sfk=' + sfk + '&frm=' + frm + '&wf=' + wf + '&yr=' + yr + '&bn=' + bn;
            const m3u8 = await getM3u8FromPlay(playUrl);
            if (m3u8) return m3u8;
            return playUrl;
        } catch (e) { return ''; }
    } else {
        const dec = decryptSignal(sig.nzgc);
        if (dec && (dec.startsWith('http://') || dec.startsWith('https://'))) return dec;
        return '';
    }
}

function getM3u8FromPlay(playUrl) {
    return fetchText(playUrl, HOST).then(html => {
        if (!html) return null;
        let encodedData = '';
        let nzxxM = /no-zw-zxx\s*=\s*["']([^"']*)["']/i.exec(html);
        if (nzxxM && nzxxM[1]) { encodedData = nzxxM[1]; }
        else {
            nzxxM = /nozwxx\s*=\s*["']([^"']*)["']/i.exec(html);
            if (nzxxM && nzxxM[1]) { encodedData = nzxxM[1]; }
            else {
                const possible = html.match(/\w+\s*=\s*["']([a-f0-9]{20,})["']/gi);
                if (possible && possible.length > 0) {
                    let maxLen = 0;
                    for (const p of possible) {
                        const valM = /["']([a-f0-9]{20,})["']/i.exec(p);
                        if (valM && valM[1].length > maxLen) { maxLen = valM[1].length; encodedData = valM[1]; }
                    }
                }
                if (!encodedData) return null;
            }
        }
        try {
            const step1 = hexToStr(encodedData);
            const step2 = atob(step1);
            const step3 = hexToStr(step2);
            let finalUrl = decodeURIComponent(step3);
            if (!finalUrl.startsWith('http')) finalUrl = 'https:' + finalUrl;
            if (finalUrl.startsWith('http') && (finalUrl.indexOf('m3u8') !== -1 || finalUrl.indexOf('flv') !== -1 || finalUrl.indexOf('mp4') !== -1))
                return finalUrl;
            return null;
        } catch (e) { return null; }
    }).catch(() => null);
}

function hexToStr(hex) {
    let str = '';
    for (let i = 0; i < hex.length; i += 2) {
        str += String.fromCharCode(parseInt(hex.substring(i, i + 2), 16));
    }
    return str;
}

// ========== 旧版接口(返回JSON字符串) ==========

async function init(cfg) {}

async function home(filter) {
    return JSON.stringify({
        class: [
            { type_id: '0', type_name: '🔥热门' },
            { type_id: '1', type_name: '⚽足球' },
            { type_id: '2', type_name: '🏀篮球' },
            { type_id: '3', type_name: '🏟综合体育' }
        ],
        filters: {}
    });
}

async function homeVod() {
    return await category('0', 1, false, {});
}

async function category(tid, pg, filter, extend) {
    tid = String((extend && extend.cateId) || tid || '0');
    pg = parseInt(pg) || 1;
    const html = await fetchText(HOST + '/?_t=' + Date.now());
    if (!html) return JSON.stringify({ code: 1, msg: '获取失败', page: 1, pagecount: 1, limit: 100, total: 0, list: [] });

    const allMatches = [];
    let pos = 0;
    while (true) {
        const aStart = html.indexOf('<a', pos);
        if (aStart === -1) break;
        const aEnd = html.indexOf('</a>', aStart);
        if (aEnd === -1) break;
        const block = html.substring(aStart, aEnd + 4);
        pos = aEnd + 4;

        const hrefM = /href\s*=\s*["'](?:\/bofang\/|\/live\/)(\d+)["']/i.exec(block);
        if (!hrefM) continue;
        const mid = hrefM[1];

        let dateStr = '';
        const dateM = /nzw-o-t\s*=\s*["']([^"']*)["']/i.exec(block);
        if (dateM) {
            const dm = /^(\d{4}-\d{2}-\d{2})/.exec(dateM[1].trim());
            if (dm) dateStr = dm[1].substring(5);
        }

        let fenlei = '0';
        const flM = /fenlei_(\d)\.png/.exec(block);
        if (flM) fenlei = flM[1];
        if (tid === '1' && fenlei !== '1') continue;
        if (tid === '2' && fenlei !== '2') continue;
        if (tid === '3' && (fenlei === '1' || fenlei === '2')) continue;

        let league = '';
        const emM = /<em>([^<]*)<\/em>/i.exec(block);
        if (emM) league = cleanText(emM[1]);

        let timeVal = '';
        const iM = /<i>([^<]*)<\/i>/i.exec(block);
        if (iM) {
            const iv = cleanText(iM[1]);
            if (/^\d{2}:\d{2}$/.test(iv)) timeVal = iv;
        }

        let isLive = false;
        if (dateStr && timeVal) {
            const dp = dateStr.split('-');
            const tp = timeVal.split(':');
            if (dp.length === 2 && tp.length === 2) {
                try {
                    const now = new Date();
                    const nowYear = now.getFullYear();
                    const mt = new Date(nowYear, parseInt(dp[0]) - 1, parseInt(dp[1]), parseInt(tp[0]), parseInt(tp[1]), 0).getTime();
                    if (mt <= now.getTime()) isLive = true;
                } catch (e) {}
            }
        }

        let shortName = '';
        let vodPic = '';
        const titleMatch = /section[^>]*class\s*=\s*["'][^"']*titlematch[^"']*["']/i.exec(block);
        if (titleMatch) {
            const tm = /<p[^>]*class\s*=\s*["'][^"']*title[^"']*["'][^>]*>([^<]*)<\/p>/i.exec(block);
            shortName = tm ? cleanText(tm[1]) : (league || '体育直播');
            vodPic = LOGO;
        } else {
            const homeM = /class\s*=\s*["'][^"']*team[^"']*zhudui[^"']*["'][^>]*>[\s\S]*?<p>([^<]*)<\/p>/i.exec(block);
            const awayM = /class\s*=\s*["'][^"']*team[^"']*kedui[^"']*["'][^>]*>[\s\S]*?<p>([^<]*)<\/p>/i.exec(block);
            let homeTeam = homeM ? cleanText(homeM[1]) : '';
            let awayTeam = awayM ? cleanText(awayM[1]) : '';

            if (!homeTeam && !awayTeam) {
                const allP = block.match(/<p>([^<]*)<\/p>/gi) || [];
                const candidates = [];
                for (const p of allP) {
                    const m2 = /<p>([^<]*)<\/p>/i.exec(p);
                    const c = m2 ? cleanText(m2[1]) : '';
                    if (c && c !== 'VS' && c !== '视频直播' && c !== league && !/^\d{2}:\d{2}$/.test(c)) candidates.push(c);
                }
                if (candidates.length >= 2) { homeTeam = candidates[0]; awayTeam = candidates[1]; }
                else if (candidates.length === 1) { homeTeam = candidates[0]; }
            }
            if (!homeTeam && !awayTeam) continue;

            const allOpPics = [];
            const opPicPattern = /op-zfr-a-g\s*=\s*["']([^"']*)["']/gi;
            let opM;
            while ((opM = opPicPattern.exec(block)) !== null) allOpPics.push(opM[1]);
            let homePic = allOpPics.length >= 1 ? allOpPics[0] : '';
            let awayPic = allOpPics.length >= 2 ? allOpPics[1] : '';

            vodPic = homePic || awayPic || LOGO;
            if (vodPic && !vodPic.startsWith('http')) vodPic = HOST + vodPic;
            shortName = homeTeam + ' vs ' + awayTeam;
        }

        const prefix = dateStr ? '[' + dateStr + '] ' : '';
        const liveP = isLive ? '🟢 ' : '';
        const remarks = liveP + prefix + (league ? league + ' ' : '') + (timeVal || '');

        let vodId = '74|' + mid + '|' + encodeURIComponent(shortName);
        if (!vodPic || !vodPic.startsWith('http')) vodPic = LOGO;

        allMatches.push({
            vod_id: vodId,
            vod_name: shortName,
            vod_pic: vodPic,
            vod_remarks: remarks,
            _date: dateStr,
            _time: timeVal || '99:99'
        });
    }

    allMatches.sort((a, b) => {
        if (a._date !== b._date) return a._date < b._date ? -1 : 1;
        return a._time < b._time ? -1 : 1;
    });
    for (const m of allMatches) { delete m._date; delete m._time; }

    return JSON.stringify({ code: 1, msg: '赛程列表', page: pg, pagecount: 1, limit: 100, total: allMatches.length, list: allMatches });
}

async function detail(ids) {
    const vid = String((Array.isArray(ids) ? ids[0] : ids) || '');
    const parts = vid.split('|');
    if (parts.length < 2 || parts[0] !== '74') return JSON.stringify({ code: 1, list: [] });

    const matchId = parts[1];
    const name = parts.length > 2 ? decodeURIComponent(parts.slice(2).join('|')) : '体育直播';
    const iframeUrl = HOST + '/live/' + matchId;
    const liveUrl = HOST + '/bofang/' + matchId;

    let signals = [];
    let html = await fetchText(iframeUrl, HOST);
    if (html) signals = extractSignals(html);

    if (signals.length === 0) {
        const html2 = await fetchText(liveUrl, HOST);
        if (html2) {
            const iframeM = /src\s*=\s*["']([^"']*)["']/i.exec(html2);
            if (iframeM && iframeM[1]) {
                let iframeSrc = iframeM[1];
                if (!iframeSrc.startsWith('http')) iframeSrc = iframeSrc.startsWith('/') ? HOST + iframeSrc : HOST + '/' + iframeSrc;
                if (iframeSrc !== iframeUrl) {
                    const html3 = await fetchText(iframeSrc, HOST);
                    if (html3) signals = extractSignals(html3);
                }
            }
        }
    }

    const playLines = [];
    if (signals.length > 0) {
        const totalSignals = signals.length;
        for (let i = 0; i < signals.length; i++) {
            const s = signals[i];
            const sName = s.name || ('直播' + (i + 1));
            let sUrl = await buildSignalUrl(s, matchId);
            if (!sUrl) sUrl = liveUrl;
            playLines.push(sName + '$' + sUrl);
        }
    } else {
        playLines.push(name + '$' + liveUrl);
    }

    return JSON.stringify({
        code: 1, msg: '直播详情', page: 1, pagecount: 1, limit: 1, total: 1,
        list: [{
            vod_id: vid,
            vod_name: name,
            vod_pic: LOGO,
            vod_remarks: signals.length > 0 ? signals.length + '个信号源' : '暂无信号',
            vod_play_from: '74直播',
            vod_play_url: playLines.join('#'),
            vod_content: '74体育 · ' + name
        }]
    });
}

async function play(flag, id, flags) {
    let url = String(id || '');
    if (url.indexOf('play.74001.tv') !== -1 && url.indexOf('sfk=') !== -1) {
        const m3u8 = await getM3u8FromPlay(url);
        if (m3u8) return JSON.stringify({ parse: 0, url: m3u8, header: getHeaders(HOST + '/') });
    }
    if (url.indexOf('.m3u8') !== -1 || url.indexOf('.flv') !== -1 || url.indexOf('.mp4') !== -1) {
        return JSON.stringify({ parse: 0, url: url, header: getHeaders(HOST + '/') });
    }
    if (url.startsWith('http://') || url.startsWith('https://')) {
        if (url.indexOf('sportsteam368.com') !== -1) return JSON.stringify({ parse: 1, url: url, header: getHeaders(HOST + '/') });
        if (url.indexOf('play.74001.tv') !== -1 && url.indexOf('sfk=') !== -1) return JSON.stringify({ parse: 1, url: url, header: getHeaders(HOST + '/') });
        if (url.indexOf('stream.sports3.win') !== -1 && url.indexOf('.m3u8') !== -1) return JSON.stringify({ parse: 0, url: url, header: getHeaders(HOST + '/') });
    }
    return JSON.stringify({ parse: 1, url: url, header: getHeaders(HOST + '/') });
}

async function search(wd, quick, pg) {
    return JSON.stringify({ code: 1, msg: '无搜索', page: 1, pagecount: 1, limit: 20, total: 0, list: [] });
}

// ========== 新版接口(返回对象) ==========

async function homeContent(filter) {
    try { return JSON.parse(await home(filter)); }
    catch (e) { return { class: [], filters: {} }; }
}

async function homeVideoContent() {
    try { return JSON.parse(await category('0', 1, false, {})); }
    catch (e) { return { code: 1, msg: '获取失败', page: 1, pagecount: 1, limit: 100, total: 0, list: [] }; }
}

async function categoryContent(tid, pg, filter, extend) {
    try { return JSON.parse(await category(tid, pg, filter, extend)); }
    catch (e) { return { code: 1, msg: '获取失败', page: 1, pagecount: 1, limit: 100, total: 0, list: [] }; }
}

async function detailContent(ids) {
    try { return JSON.parse(await detail(ids)); }
    catch (e) { return { code: 1, list: [] }; }
}

async function playerContent(flag, id, flags) {
    try { return JSON.parse(await play(flag, id, flags)); }
    catch (e) { return { parse: 0, url: id || '', header: '' }; }
}

async function searchContent(wd, quick, pg) {
    try { return JSON.parse(await search(wd, quick, pg)); }
    catch (e) { return { code: 1, msg: '无搜索', page: 1, pagecount: 1, limit: 20, total: 0, list: [] }; }
}

export function __jsEvalReturn() {
    return {
        init, home, homeVod, category, detail, play, search,
        homeContent, homeVideoContent, categoryContent, detailContent, playerContent, searchContent
    };
}