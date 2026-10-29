// ============================================================
// zuqiu200直播爬虫 v3 (CatVod格式)
// v3: 修复队徽路径 足球/篮球前缀改回 football|basketball/team (v2 误用 team/ 致404)
// v2: 数据源切换 c5 livehouse -> c7 match/list (官方流videoUrl+主播解说)
// ============================================================

const API_HOST = 'https://enskweeseey8kp2frvb06.k8v4dh4.app';
const HOST = 'https://zuqiu200.app';
const UA = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36';

// ========== 工具函数 ==========
function getHeaders() {
    return {
        'User-Agent': UA,
        'Referer': HOST + '/',
        'Origin': HOST,
        'Accept': 'application/json, text/plain, */*',
        'Accept-Language': 'zh-CN,zh;q=0.9,en;q=0.8'
    };
}

async function fetchJson(url) {
    try {
        const hd = getHeaders();
        if (typeof Java !== 'undefined' && Java && Java.req) {
            const r = await Java.req(url, { headers: hd });
            if (typeof r === 'string') return JSON.parse(r);
            const code = Number((r && (r.statusCode || r.status || r.code)) || 0);
            const body = String((r && (r.body || r.content || r.data)) || '');
            if (code >= 200 && code < 300 && body) return JSON.parse(body);
            return {};
        }
        const r2 = await req(url, { headers: hd });
        if (typeof r2 === 'string') return JSON.parse(r2);
        const code2 = Number((r2 && (r2.statusCode || r2.status || r2.code)) || 0);
        const body2 = String((r2 && (r2.content || r2.body || r2.data)) || '');
        if (code2 >= 200 && code2 < 300 && body2) return JSON.parse(body2);
        return {};
    } catch (e) {
        return {};
    }
}

function fmtTime(tsSec) {
    if (!tsSec) return '';
    try {
        const d = new Date(tsSec * 1000);
        const pad = n => String(n).padStart(2, '0');
        return pad(d.getMonth() + 1) + '-' + pad(d.getDate()) + ' ' + pad(d.getHours()) + ':' + pad(d.getMinutes());
    } catch (e) {
        return '';
    }
}

function getLogoUrl(sportId, logo) {
    if (!logo) return '';
    if (logo.indexOf('http') === 0) return logo;
    if (logo.indexOf('/') > -1) return 'https://img0.aiscore.com/' + logo;
    const prefix = {1: 'football/team/', 2: 'basketball/team/', 3: 'v2/team/', 4: 'volleyball/team/', 5: 'v2/team/'};
    return 'https://img0.aiscore.com/' + (prefix[sportId] || 'football/team/') + logo;
}

// ========== 分类 ==========
function getClasses() {
    return [
        { type_id: '1', type_name: '足球' },
        { type_id: '2', type_name: '篮球' },
        { type_id: '3', type_name: '网球' },
        { type_id: '4', type_name: '排球' },
        { type_id: 'all', type_name: '全部' }
    ];
}

// ========== 获取赛程数据 ==========
function todayStr(offsetDays) {
    const d = new Date(Date.now() + (offsetDays || 0) * 86400000);
    const pad = n => String(n).padStart(2, '0');
    return d.getFullYear() + '-' + pad(d.getMonth() + 1) + '-' + pad(d.getDate());
}

async function fetchMatchList(dateStr) {
    const json = await fetchJson(API_HOST + '/api/c7/business/match/list?lang=zh&date=' + dateStr);
    if (json && json.success && json.data && json.data.records) return json.data.records;
    return [];
}

async function getMatchRecords() {
    let records = await fetchMatchList(todayStr(0));
    if (!records.length) records = await fetchMatchList(todayStr(1));
    if (!records.length) records = await fetchMatchList(todayStr(-1));
    return records;
}

function fmtScore(m) {
    if (m.sportId === 5) {
        const inn = (m.ckScores && m.ckScores.innings) || [];
        const p1 = inn[0] ? inn[0].runs + '/' + inn[0].wickets : '';
        const p2 = inn[1] ? inn[1].runs + '/' + inn[1].wickets : '';
        return p1 || p2 ? p1 + ' ' + p2 : '';
    }
    const h = m.homeScores || [], a = m.awayScores || [];
    const hs = h.length ? h[h.length - 1] : 0;
    const as = a.length ? a[a.length - 1] : 0;
    return (h.length || a.length) ? hs + '-' + as : '';
}

async function getLivestreams() {
    const records = await getMatchRecords();
    const now = Math.floor(Date.now() / 1000);
    const result = [];
    const seen = new Set();
    for (let i = 0; i < records.length; i++) {
        const m = records[i];
        const home = (m.homeTeam && m.homeTeam.teamName) || '';
        const away = (m.awayTeam && m.awayTeam.teamName) || '';
        if (!home || !away) continue;
        const league = (m.competition && m.competition.competitionName) || '';
        const matchId = m.matchId || '';
        const mt = m.matchTime || 0;
        const anchors = m.anchorAppointmentVoList || [];
        let url = '';
        const vu = m.videoUrl || '';
        if (vu.indexOf('http') === 0) url = vu;
        for (let j = 0; !url && j < anchors.length; j++) {
            const s1 = anchors[j].playStreamAddress || '', s2 = anchors[j].playStreamAddress2 || '';
            if (s1.indexOf('.m3u8') > -1) { url = s1; break; }
            if (s2.indexOf('.m3u8') > -1) { url = s2; break; }
        }
        for (let j = 0; !url && j < anchors.length; j++) {
            const s1 = anchors[j].playStreamAddress || '', s2 = anchors[j].playStreamAddress2 || '';
            if (s1.indexOf('http') === 0) { url = s1; break; }
            if (s2.indexOf('http') === 0) { url = s2; break; }
        }
        const isLive = !!url;
        const isSoon = !url && Math.abs(mt - now) <= 1800;
        if (!isLive && !isSoon) continue;
        const timeStr = fmtTime(mt);
        const score = fmtScore(m);
        const prefix = isLive ? '🔴 ' : '⏳ ';
        const parts = [];
        if (timeStr) parts.push(timeStr);
        if (league) parts.push(league);
        if (score) parts.push(score);
        parts.unshift(prefix);
        const key = matchId || (home + away + league);
        if (seen.has(key)) continue;
        seen.add(key);
        result.push({
            vod_id: matchId,
            vod_name: home + ' vs ' + away,
            vod_pic: getLogoUrl(m.sportId, (m.homeTeam && m.homeTeam.logo) || ''),
            vod_play_from: league || '直播',
            vod_play_url: url || '',
            vod_remarks: parts.join(' '),
            sport_id: String(m.sportId || ''),
            _mt: mt,
            _live: isLive ? 1 : 0
        });
    }
    result.sort((x, y) => (y._live - x._live) || (x._mt - y._mt));
    return result;
}

async function resolveStream(matchId) {
    const records = await getMatchRecords();
    for (let i = 0; i < records.length; i++) {
        const m = records[i];
        if (m.matchId !== matchId) continue;
        const vu = m.videoUrl || '';
        if (vu.indexOf('http') === 0) return vu;
        const anchors = m.anchorAppointmentVoList || [];
        for (let j = 0; j < anchors.length; j++) {
            const s1 = anchors[j].playStreamAddress || '', s2 = anchors[j].playStreamAddress2 || '';
            if (s1.indexOf('.m3u8') > -1) return s1;
            if (s2.indexOf('.m3u8') > -1) return s2;
        }
        for (let j = 0; j < anchors.length; j++) {
            const s1 = anchors[j].playStreamAddress || '', s2 = anchors[j].playStreamAddress2 || '';
            if (s1.indexOf('http') === 0) return s1;
            if (s2.indexOf('http') === 0) return s2;
        }
        break;
    }
    return '';
}

// ========== 公开接口 ==========
async function init(cfg) {}

async function home(filter) {
    return JSON.stringify({
        class: getClasses(),
        filters: {}
    });
}

async function homeVod() {
    return await category('all', 1, false, {});
}

async function category(tid, pg, filter, extend) {
    tid = String((extend && extend.cateId) || tid || 'all');
    pg = parseInt(pg) || 1;
    let list = [];
    let total = 0;
    
    try {
        const allVideos = await getLivestreams();
        const filtered = tid === 'all' ? allVideos : allVideos.filter(v => v.sport_id === tid);
        total = filtered.length;
        const start = (pg - 1) * 20;
        list = filtered.slice(start, start + 20);
    } catch (e) {
        list = [];
    }
    
    return JSON.stringify({
        code: 1,
        msg: '数据列表',
        page: pg,
        pagecount: Math.ceil(total / 20) || 1,
        limit: 20,
        total: total,
        list: list
    });
}

async function detail(ids) {
    const id = String(Array.isArray(ids) ? ids[0] : ids || '');
    if (!id) return JSON.stringify({ code: 1, list: [] });
    
    try {
        const allVideos = await getLivestreams();
        for (let i = 0; i < allVideos.length; i++) {
            if (allVideos[i].vod_id === id) {
                const detail = Object.assign({}, allVideos[i]);
                return JSON.stringify({
                    code: 1,
                    list: [detail]
                });
            }
        }
    } catch (e) {}
    
    return JSON.stringify({ code: 1, list: [] });
}

async function search(wd, quick, pg) {
    pg = parseInt(pg) || 1;
    let results = [];
    let total = 0;
    
    try {
        const allVideos = await getLivestreams();
        const keywordLower = String(wd || '').toLowerCase();
        
        for (let i = 0; i < allVideos.length; i++) {
            const video = allVideos[i];
            if (video.vod_name.toLowerCase().includes(keywordLower) || video.vod_play_from.includes(String(wd || ''))) {
                results.push(video);
            }
        }
        total = results.length;
        const start = (pg - 1) * 20;
        results = results.slice(start, start + 20);
    } catch (e) {
        results = [];
    }
    
    return JSON.stringify({
        code: 1,
        msg: '搜索结果',
        page: pg,
        pagecount: Math.ceil(total / 20) || 1,
        limit: 20,
        total: total,
        list: results
    });
}

async function play(flag, id, flags) {
    let url = String(id || '');
    if (url) {
        try {
            const fresh = await resolveStream(url);
            if (fresh) url = fresh;
        } catch (e) {}
    }
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

// ========== 导出接口 ==========
async function homeContent(filter) {
    try {
        return JSON.parse(await home(filter));
    } catch (e) {
        return { class: [], list: [], filter: {} };
    }
}

async function homeVideoContent() {
    try {
        return JSON.parse(await category('all', 1, false, {}));
    } catch (e) {
        return { list: [] };
    }
}

async function categoryContent(tid, pg, filter, extend) {
    try {
        return JSON.parse(await category(tid, pg, filter, extend || {}));
    } catch (e) {
        return { list: [] };
    }
}

async function detailContent(ids) {
    try {
        return JSON.parse(await detail(ids));
    } catch (e) {
        return { list: [] };
    }
}

async function searchContent(wd, quick, pg) {
    try {
        return JSON.parse(await search(wd, quick, pg || 1));
    } catch (e) {
        return { list: [] };
    }
}

async function playerContent(flag, id, flags) {
    try {
        return JSON.parse(await play(flag, id, flags));
    } catch (e) {
        return { parse: 0, url: id || '', header: '' };
    }
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