 ============================================================================
 *   常量
 * ============================================================================ */
//const HOST = 'https://www.lingshid.net';
const HOST = 'https://www.cnrbc.com';
const LOGO = 'https://www.cnrbc.com/favicon.ico';
const UA = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/140.0.0.0 Safari/537.36';

/* ============================================================================
 *   工具函数
 * ============================================================================ */
function clean(s) {
    return String(s || '').replace(/<script[\s\S]*?<\/script>/gi, '')
        .replace(/<style[\s\S]*?<\/style>/gi, '')
        .replace(/<[^>]+>/g, '')
        .replace(/&nbsp;/g, ' ').replace(/&amp;/g, '&')
        .replace(/&quot;/g, '"').replace(/&#39;/g, "'")
        .replace(/\s+/g, ' ').trim();
}

function absUrl(url) {
    if (!url) return LOGO;
    url = String(url).trim();
    if (/^https?:\/\//i.test(url)) return url;
    if (url.indexOf('//') === 0) return 'https:' + url;
    if (url[0] === '/') return HOST + url;
    return HOST + '/' + url;
}

function safeJson(t, d) {
    try {
        return JSON.parse(t || '{}');
    } catch (e) {
        return d || {};
    }
}

function getHeaders() {
    return {
        'User-Agent': UA,
        'Referer': HOST + '/',
        'Accept': '*/*',
        'Accept-Language': 'zh-CN,zh;q=0.9'
    };
}

/* ── 网络请求 ── */
async function fetchText(url, timeout) {
    const hd = getHeaders();
    const to = timeout || 10000;
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

async function fetchHtml(url) {
    return await fetchText(url, 10000);
}

/* ── 从HTML解析单场比赛 ── */
function parseOneMatch(block) {
    if (!block) return null;

    // 1. 提取 href（完整URL）和 title
    const hrefM = /href="(https?:\/\/[^"]*\/detail\/\d+)"/.exec(block);
    const titleM = /title="([^"]*)"/.exec(block);
    if (!hrefM) return null;

    const vodId = hrefM[1];
    const rawTitle = titleM ? clean(titleM[1]) : '';

    // 去掉末尾日期 (2026-06-26 ) → 只保留"主队 vs 客队"
    let displayName = rawTitle.replace(/\s*\(\d{4}-\d{1,2}-\d{1,2}\s*\)\s*$/, '').trim();

    // 2. 提取 data-time 属性（日期）
    let dateStr = '';
    const dateM = /data-time\s*=\s*"([^"]*)"/.exec(block);
    if (dateM) dateStr = dateM[1].trim();

    // 3. 提取主队Logo —— 找 team zhudui 中的 img src
    let pic = LOGO;
    const zhuduiM = /<div\s+class="team\s+zhudui"[^>]*>([\s\S]*?)<\/div>\s*<div\s+class="center"/.exec(block);
    if (zhuduiM) {
        const zhuduiHtml = zhuduiM[1];
        const imgM = /<img[^>]*src="([^"]+)"[^>]*>/.exec(zhuduiHtml);
        if (imgM) pic = absUrl(imgM[1]);
    }

    // 4. 提取联赛名和时间
    let league = '';
    let time = '';
    const infoM = /<em>([^<]*)<\/em>\s*<i>([^<]*)<\/i>/.exec(block);
    if (infoM) {
        league = clean(infoM[1]);
        time = clean(infoM[2]);
    }

    // 5. 判断是否正在直播中 —— 仅检测 zb_green 类
    let isLive = false;
    if (block.includes('zb_green')) isLive = true;

    // 备注 = 🟢 + 联赛名 + 日期 + 时间
    let remark = '';
    if (isLive) remark = '🟢 ';
    if (league) remark += league;
    if (dateStr) remark += ' ' + dateStr;
    if (time) remark += ' ' + time;
    remark = remark.trim();

    // 运动类型判断（通过图标sport_1=足球 sport_2=篮球）
    let sportType = 'football';
    if (block.includes('sport_2.png')) sportType = 'basketball';

    return {
        vod_id: vodId,
        vod_name: displayName || rawTitle,
        vod_pic: pic,
        vod_remarks: remark,
        vod_content: (league || '体育直播') + '\n' + displayName,
        type_name: league || '全部',
        _sport: sportType,
        _league: league
    };
}

/* ── 从HTML解析全部比赛 ── */
function parseMatches(html) {
    const matches = [];
    if (!html) return matches;

    const cardRegex = /<a\s+class="clearfix\s*"[^>]*href="(https?:\/\/[^"]*\/detail\/\d+)"[^>]*>([\s\S]*?)<\/a>/g;
    let m;
    while ((m = cardRegex.exec(html)) !== null) {
        const block = m[0];

        // 跳过非直播卡片
        if (!block.includes('video-icon') && !block.includes('视频直播')) continue;

        const match = parseOneMatch(block);
        if (match) matches.push(match);
    }

    return matches;
}

/* ── 从详情页提取播放地址 ── */
function extractPlayUrl(html) {
    if (!html) return '';

    // 方式1: data-play 属性
    let m = /data-play\s*=\s*["']([^"']+)["']/.exec(html);
    if (m) return m[1];

    // 方式2: playurl 变量
    m = /playurl\s*[:=]\s*["']([^"']+)["']/.exec(html);
    if (m) return m[1];

    // 方式3: iframe src 包含 .m3u8
    m = /<iframe[^>]+src=["']([^"']*\.m3u8[^"']*)["']/.exec(html);
    if (m) return m[1];

    // 方式4: video src 包含 .m3u8
    m = /<video[^>]+src=["']([^"']*\.m3u8[^"']*)["']/.exec(html);
    if (m) return m[1];

    // 方式5: 任意 .m3u8 链接
    m = /https?:\/\/[^"'\s]+\.m3u8[^"'\s]*/.exec(html);
    if (m) return m[0];

    // 方式6: vid 参数
    m = /vid\s*[:=]\s*["']([^"']+)["']/.exec(html);
    if (m) {
        const vid = m[1];
        if (vid.length > 5) return 'https://play.cnrbc.com/play/' + vid + '.m3u8';
    }

    return '';
}

/* ============================================================================
 *   分类定义
 * ============================================================================ */
function getClasses() {
    return [{
            type_id: 'all',
            type_name: '全部'
        },
        {
            type_id: 'zuqiu',
            type_name: '⚽ 足球'
        },
        {
            type_id: 'lanqiu',
            type_name: '🏀 篮球'
        }
    ];
}

function isFootball(league, sport) {
    if (sport === 'football') return true;
    if (sport === 'basketball') return false;
    const name = (league || '').toLowerCase();
    if (/篮球|nba|wnba|cba|nbl|basketball/.test(name)) return false;
    return true;
}

function isBasketball(league, sport) {
    if (sport === 'basketball') return true;
    const name = (league || '').toLowerCase();
    return /篮球|nba|wnba|cba|nbl|basketball/.test(name);
}

/* ============================================================================
 *   爬虫接口
 * ============================================================================ */
async function init(cfg) {}

async function home(filter) {
    return JSON.stringify({
        class: getClasses(),
        filters: {},
        style: {
            type: 'list',
            ratio: 1
        }
    });
}

async function homeVod() {
    return await category('all', 1, {}, {});
}

async function category(tid, pg, filter, extend) {
    tid = String((extend && extend.cateId) || tid || 'all');
    pg = parseInt(pg) || 1;
    let list = [];

    try {
        // 统一用首页解析
        const html = await fetchHtml(HOST);
        if (!html) {
            return JSON.stringify({
                code: 1,
                msg: 'ok',
                page: 1,
                pagecount: 1,
                limit: 30,
                total: 0,
                list: [],
                style: {
                    type: 'list',
                    ratio: 1
                }
            });
        }

        let matches = parseMatches(html);

        // 用 _sport 字段进行过滤
        if (tid !== 'all') {
            matches = matches.filter(item => {
                const league = item._league || '';
                const sport = item._sport || '';
                if (tid === 'zuqiu') return isFootball(league, sport);
                if (tid === 'lanqiu') return isBasketball(league, sport);
                return true;
            });
        }

        list = matches;

    } catch (e) {
        // 静默
    }

    return JSON.stringify({
        code: 1,
        msg: '赛程列表',
        page: pg,
        pagecount: 1,
        limit: 200,
        total: list.length,
        list: list,
        style: {
            type: 'list',
            ratio: 1
        }
    });
}

async function detail(ids) {
    const id = String(Array.isArray(ids) ? ids[0] : ids || '');
    if (!id) {
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

    try {
        const html = await fetchHtml(id);
        if (!html) {
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

        // 提取名称：严格从详情页HTML中提取"主队 vs 客队"
        let name = '';

        // 从页面中找 h1 或 h2 标题标签
        const hM = /<h[12][^>]*>([\s\S]*?)<\/h[12]>/i.exec(html);
        if (hM) {
            let hText = clean(hM[1]);
            // 匹配 "主队 vs 客队"
            const vsM = /^(.+?)\s*(?:vs|VS)\s*(.+?)$/.exec(hText);
            if (vsM) {
                name = vsM[1].trim() + ' vs ' + vsM[2].trim();
            }
        }

        // fallback: 从 title 中提取
        if (!name) {
            const titleM = /<title>([^<]+)<\/title>/.exec(html);
            if (titleM) {
                let t = clean(titleM[1]);
                // 严格匹配 "球队名 vs 球队名"（最多各3个词，且不含站点关键词）
                const strictVs = /^(?:[A-Za-z\u4e00-\u9fa5][A-Za-z\u4e00-\u9fa5\s()]*?)\s+(?:vs|VS)\s+(?:[A-Za-z\u4e00-\u9fa5][A-Za-z\u4e00-\u9fa5\s()]*?)$/;
                const m = strictVs.exec(t);
                if (m) {
                    name = m[0].trim();
                } else {
                    // 宽松匹配：找 "主队-vs-客队" 或 "主队 vs 客队"
                    const looseVs = /^(.+?)\s*[-–—]\s*(?:vs|VS)\s*[-–—]\s*(.+?)(?:\s*\([\d\-]+\))?\s*$/;
                    const m2 = looseVs.exec(t);
                    if (m2) {
                        name = m2[1].trim() + ' vs ' + m2[2].trim();
                    }
                }
            }
        }

        // 最后fallback
        if (!name) name = '直播';

        const playUrl = extractPlayUrl(html);

        let pic = LOGO;
        const picM = /<img[^>]*src="([^"]*)"[^>]*class="lazy"[^>]*>/.exec(html);
        if (picM) pic = absUrl(picM[1]);

        const vod = {
            vod_id: id,
            vod_name: name,
            vod_pic: pic,
            vod_remarks: '',
            vod_content: name || '体育直播',
            vod_play_from: '310直播',
            vod_play_url: playUrl ? '直播地址$' + playUrl : '暂无信号$' + HOST
        };

        return JSON.stringify({
            code: 1,
            msg: '直播详情',
            page: 1,
            pagecount: 1,
            limit: 1,
            total: 1,
            list: [vod]
        });
    } catch (e) {
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
}

async function search(wd, quick, pg) {
    return JSON.stringify({
        code: 1,
        msg: '搜索',
        page: 1,
        pagecount: 1,
        limit: 20,
        total: 0,
        list: []
    });
}

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

/* ============================================================================
 *   包装函数（统一响应格式）
 * ============================================================================ */
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

/* ============================================================================
 *   引擎导出 — 全局函数模式
 * ============================================================================ */
export function __jsEvalReturn() {
    return {
        init: init,
        home: home,
        homeVod: homeVod,
        category: category,
        search: search,
        detail: detail,
        play: play,
        homeContent: homeContent,
        homeVideoContent: homeVideoContent,
        categoryContent: categoryContent,
        detailContent: detailContent,
        searchContent: searchContent,
        playerContent: playerContent
    };
}