// 球吧体育 V6.0 - peek不行，ys，ysc可以
const HOST = 'https://www.qiuba001.vip';
const API = HOST + '/api';
const UA = 'Mozilla/5.0 (Linux; Android 13; Pixel 7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/140.0.0.0 Mobile Safari/537.36';

function getHeaders(ref) {
    return {
        'User-Agent': UA,
        'Referer': ref || HOST + '/',
        'Accept': 'application/json, text/plain, */*',
        'Accept-Language': 'zh-CN,zh;q=0.9',
        'Origin': HOST
    };
}

function getVideoHeaders() {
    return {
        'User-Agent': UA,
        'Referer': HOST + '/',
        'Origin': HOST,
        'Accept': '*/*',
        'Accept-Language': 'zh-CN,zh;q=0.9'
    };
}

async function fetchJson(url, method, body) {
    const hd = getHeaders();
    const isPost = method && method.toUpperCase() === 'POST';
    if (isPost) hd['Content-Type'] = 'application/json';
    const bodyStr = body ? (typeof body === 'string' ? body : JSON.stringify(body)) : '';
    
    // 方式1: Java.req（优先）
    if (typeof Java !== 'undefined' && Java && Java.req) {
        try {
            const opts = { headers: hd, method: isPost ? 'POST' : 'GET' };
            if (bodyStr) opts.body = bodyStr;
            const r = await Java.req(url, opts);
            if (typeof r === 'string') return JSON.parse(r);
            if (r && typeof r === 'object') {
                const code = Number((r.statusCode || r.status || r.code) || 0);
                const body = String((r.body || r.content || r.data) || '');
                if (code >= 200 && code < 300 && body) return JSON.parse(body);
                if (body) return JSON.parse(body);
            }
        } catch (e) {}
    }
    
    // 方式2: req函数
    if (typeof req === 'function') {
        try {
            const opts = { headers: hd, method: isPost ? 'POST' : 'GET' };
            if (bodyStr) opts.body = bodyStr;
            const r = await req(url, opts);
            if (typeof r === 'string') return JSON.parse(r);
            if (r && typeof r === 'object') {
                const code = Number((r.statusCode || r.status || r.code) || 0);
                const body = String((r.content || r.body || r.data) || '');
                if (code >= 200 && code < 300 && body) return JSON.parse(body);
                if (body) return JSON.parse(body);
            }
        } catch (e) {}
    }
    
    // 方式3: fetch
    if (typeof fetch === 'function') {
        try {
            const opts = { method: isPost ? 'POST' : 'GET', headers: hd };
            if (isPost && bodyStr) opts.body = bodyStr;
            const resp = await fetch(url, opts);
            const text = await resp.text();
            if (text) return JSON.parse(text);
        } catch (e) {}
    }
    
    return {};
}

function cleanText(s) {
    return String(s || '').replace(/<[^>]+>/g, '').replace(/&nbsp;/g, ' ').replace(/&amp;/g, '&').replace(/"/g, '"').replace(/&#39;/g, "'").replace(/\s+/g, ' ').trim();
}

function formatTime(isoStr) {
    if (!isoStr) return '';
    try {
        const d = new Date(isoStr);
        const utc8 = new Date(d.getTime() + 8 * 3600 * 1000);
        const mm = String(utc8.getUTCMonth() + 1).padStart(2, '0');
        const dd = String(utc8.getUTCDate()).padStart(2, '0');
        const hh = String(utc8.getUTCHours()).padStart(2, '0');
        const mi = String(utc8.getUTCMinutes()).padStart(2, '0');
        return mm + '-' + dd + ' ' + hh + ':' + mi;
    } catch (e) {
        return isoStr.split('T')[1] ? isoStr.split('T')[1].substring(0, 5) : '';
    }
}

function getStatus(status) {
    const map = { 'live': '🔴', 'not_started': '⚪', 'finished': '⚫' };
    return map[status] || '';
}

function parseMatch(item) {
    try {
        const matchId = String(item.id || '');
        const homeTeam = item.home_team || {};
        const awayTeam = item.away_team || {};
        const comp = item.competition || {};
        const homeName = homeTeam.name || '主队';
        const awayName = awayTeam.name || '客队';
        const compName = comp.name || '未知联赛';
        const status = item.status || 'not_started';
        const homeScore = item.home_score;
        const awayScore = item.away_score;
        const score = (homeScore !== null && awayScore !== null) ? homeScore + ':' + awayScore : 'vs';
        const signalCount = item.signal_count || 0;
        const startTime = item.start_time || '';
        const timeStr = formatTime(startTime);
        const statusText = getStatus(status);
        
        let name = homeName + ' vs ' + awayName;
        if (status === 'live') name = homeName + ' ' + score + ' ' + awayName;
        
        let remarks = statusText;
        if (timeStr) remarks += ' ' + timeStr;
        if (compName) remarks += ' ' + compName;
        if (signalCount > 0) remarks += ' | ' + signalCount + '路';
        
        const pic = homeTeam.logo || awayTeam.logo || '';
        
        return {
            vod_id: matchId,
            vod_name: name,
            vod_pic: pic,
            vod_remarks: remarks
        };
    } catch (e) {
        return null;
    }
}

async function getMatches(tid, pg) {
    let url = API + '/matches?page=' + pg + '&page_size=20';
    if (tid && tid !== '0') url += '&category_id=' + tid;
    
    const data = await fetchJson(url);
    let items = [];
    
    if (data && data.items && Array.isArray(data.items)) {
        items = data.items;
    } else if (Array.isArray(data)) {
        items = data;
    } else if (data && data.data && Array.isArray(data.data)) {
        items = data.data;
    }
    
    return items.map(parseMatch).filter(Boolean);
}

// ========== 公开接口 ==========

async function init(cfg) {}

async function home(filter) {
    return JSON.stringify({
        class: [
            { type_id: '1', type_name: '足球' },
            { type_id: '2', type_name: '篮球' }
        ],
        filters: {}
    });
}

async function homeVod() {
    return await category('1', 1, false, {});
}

async function category(tid, pg, filter, extend) {
    tid = String((extend && extend.cateId) || tid || '1');
    pg = parseInt(pg) || 1;
    
    try {
        const list = await getMatches(tid, pg);
        return JSON.stringify({
            code: 1,
            msg: '数据列表',
            page: pg,
            pagecount: Math.ceil(list.length / 20) || 1,
            limit: 20,
            total: list.length,
            list: list
        });
    } catch (e) {
        return JSON.stringify({
            code: 1,
            msg: '获取失败',
            page: pg,
            pagecount: 1,
            limit: 20,
            total: 0,
            list: []
        });
    }
}

async function detail(ids) {
    const id = String(Array.isArray(ids) ? ids[0] : ids || '');
    if (!id) return JSON.stringify({ code: 1, list: [] });
    
    try {
        const matchData = await fetchJson(API + '/matches/' + id);
        if (!matchData) return JSON.stringify({ code: 1, list: [] });
        
        const parsed = parseMatch(matchData);
        if (!parsed) return JSON.stringify({ code: 1, list: [] });
        
        // 获取信号列表
        const signalData = await fetchJson(API + '/matches/' + id + '/signals');
        let signals = [];
        if (signalData && signalData.signals) signals = signalData.signals;
        else if (Array.isArray(signalData)) signals = signalData;
        
        // 构建播放列表
        const playLines = [];
        if (signals.length > 0) {
            for (let i = 0; i < signals.length; i++) {
                const sig = signals[i];
                const sourceId = sig.source_id || '';
                const displayName = sig.display_name || ('信号' + (i + 1));
                const sigStatus = sig.status || '';
                let prefix = '⚪';
                if (sigStatus === 'recommended_online') prefix = '⭐';
                else if (sigStatus === 'online') prefix = '🟢';
                playLines.push(prefix + ' ' + displayName + '$qiuba|' + id + '|' + sourceId);
            }
        } else {
            playLines.push('默认直播$qiuba|' + id + '|default');
        }
        
        return JSON.stringify({
            code: 1,
            list: [{
                vod_id: id,
                vod_name: parsed.vod_name,
                vod_pic: parsed.vod_pic,
                vod_remarks: parsed.vod_remarks,
                vod_play_from: '球吧体育',
                vod_play_url: playLines.join('#')
            }]
        });
    } catch (e) {
        return JSON.stringify({ code: 1, list: [] });
    }
}

async function search(wd, quick, pg) {
    pg = parseInt(pg) || 1;
    
    try {
        const allMatches = await getMatches('0', 1);
        const keywordLower = wd.toLowerCase();
        const results = allMatches.filter(m => m.vod_name.toLowerCase().includes(keywordLower));
        
        return JSON.stringify({
            code: 1,
            msg: '搜索结果',
            page: pg,
            pagecount: Math.ceil(results.length / 20) || 1,
            limit: 20,
            total: results.length,
            list: results.slice((pg - 1) * 20, pg * 20)
        });
    } catch (e) {
        return JSON.stringify({
            code: 1,
            msg: '搜索失败',
            page: pg,
            pagecount: 1,
            limit: 20,
            total: 0,
            list: []
        });
    }
}

async function play(flag, id, flags) {
    const url = String(id || '');
    
    // 处理 qiuba|matchId|sourceId 格式
    if (url.indexOf('qiuba|') === 0) {
        const parts = url.split('|');
        if (parts.length >= 3) {
            const matchId = parts[1];
            let sourceId = parts[2];
            
            // 如果是默认信号，获取第一个在线信号
            if (sourceId === 'default') {
                const signalData = await fetchJson(API + '/matches/' + matchId + '/signals');
                let signals = [];
                if (signalData && signalData.signals) signals = signalData.signals;
                else if (Array.isArray(signalData)) signals = signalData;
                
                if (signals.length > 0) {
                    // 优先选择推荐在线的信号
                    for (const sig of signals) {
                        if (sig.status === 'recommended_online') {
                            sourceId = sig.source_id || '';
                            break;
                        }
                    }
                    if (sourceId === 'default') sourceId = signals[0].source_id || '';
                }
            }
            
            // 获取播放地址
            if (sourceId && sourceId !== 'default') {
                const sessionData = await fetchJson(API + '/play/session', 'POST', { source_id: sourceId });
                if (sessionData && sessionData.real_url_encrypted) {
                    const encrypted = sessionData.real_url_encrypted;
                    if (encrypted.indexOf('crawler_b64:') === 0) {
                        const b64 = encrypted.split(':', 2)[1];
                        if (b64) {
                            try {
                                // 尝试多种解码方式
                                let m3u8 = '';
                                if (typeof atob === 'function') {
                                    m3u8 = atob(b64);
                                } else if (typeof Buffer === 'function') {
                                    m3u8 = Buffer.from(b64, 'base64').toString('utf-8');
                                } else {
                                    // 手动解码
                                    const chars = 'ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789+/';
                                    const lookup = {};
                                    for (let i = 0; i < 64; i++) lookup[chars[i]] = i;
                                    
                                    let result = '';
                                    const padded = b64.replace(/-/g, '+').replace(/_/g, '/');
                                    const pad = padded.length % 4;
                                    const str = pad ? padded + '='.repeat(4 - pad) : padded;
                                    
                                    for (let i = 0; i < str.length; i += 4) {
                                        const a = lookup[str.charAt(i)] || 0;
                                        const b = lookup[str.charAt(i + 1)] || 0;
                                        const c = str.charAt(i + 2) === '=' ? 0 : (lookup[str.charAt(i + 2)] || 0);
                                        const d = str.charAt(i + 3) === '=' ? 0 : (lookup[str.charAt(i + 3)] || 0);
                                        
                                        const triplet = (a << 18) + (b << 12) + (c << 6) + d;
                                        result += String.fromCharCode((triplet >> 16) & 0xFF);
                                        if (str.charAt(i + 2) !== '=') result += String.fromCharCode((triplet >> 8) & 0xFF);
                                        if (str.charAt(i + 3) !== '=') result += String.fromCharCode(triplet & 0xFF);
                                    }
                                    m3u8 = result;
                                }
                                
                                if (m3u8 && (m3u8.indexOf('.m3u8') !== -1 || m3u8.indexOf('.mp4') !== -1 || m3u8.indexOf('.flv') !== -1)) {
                                    return JSON.stringify({
                                        parse: 0,
                                        url: m3u8,
                                        header: getVideoHeaders()
                                    });
                                }
                            } catch (e) {}
                        }
                    }
                }
            }
            
            // 降级到播放页面
            return JSON.stringify({
                parse: 1,
                url: HOST + '/live/' + matchId,
                header: getVideoHeaders()
            });
        }
    }
    
    // 直链处理
    if (url.indexOf('.m3u8') !== -1 || url.indexOf('.mp4') !== -1 || url.indexOf('.flv') !== -1) {
        return JSON.stringify({
            parse: 0,
            url: url,
            header: getVideoHeaders()
        });
    }
    
    return JSON.stringify({
        parse: 1,
        url: url,
        header: getVideoHeaders()
    });
}

// ========== 导出接口 ==========

async function homeContent(filter) {
    try { return JSON.parse(await home(filter)); }
    catch (e) { return { class: [], filters: {} }; }
}

async function homeVideoContent() {
    try { return JSON.parse(await category('1', 1, false, {})); }
    catch (e) { return { code: 1, msg: '获取失败', page: 1, pagecount: 1, limit: 20, total: 0, list: [] }; }
}

async function categoryContent(tid, pg, filter, extend) {
    try { return JSON.parse(await category(tid, pg, filter, extend || {})); }
    catch (e) { return { code: 1, msg: '获取失败', page: Number(pg), pagecount: 1, limit: 20, total: 0, list: [] }; }
}

async function detailContent(ids) {
    try { return JSON.parse(await detail(ids)); }
    catch (e) { return { code: 1, list: [] }; }
}

async function searchContent(wd, quick, pg) {
    try { return JSON.parse(await search(wd, quick, pg)); }
    catch (e) { return { code: 1, msg: '搜索失败', page: Number(pg || 1), pagecount: 1, limit: 20, total: 0, list: [] }; }
}

async function playerContent(flag, id, flags) {
    try { return JSON.parse(await play(flag, id, flags)); }
    catch (e) { return { parse: 0, url: id || '', header: '' }; }
}

export function __jsEvalReturn() {
    return {
        init,
        home,
        homeVod,
        category,
        detail,
        play,
        search,
        homeContent,
        homeVideoContent,
        categoryContent,
        detailContent,
        playerContent,
        searchContent
    };
}
