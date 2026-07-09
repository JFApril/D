/* =========================================================================
 *   常量
 * ========================================================================= */
const HOST = 'https://shutu16.com';
const UA = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/140.0.0.0 Safari/537.36';
const LOGO = 'https://shutu16.com/favicon.ico';

/* =========================================================================
 *   工具函数
 * ========================================================================= */
function safeJson(t, d) {
  try { return JSON.parse(t || '{}'); } catch (e) { return d || {}; }
}

function getHeaders(token) {
  const h = {
    'User-Agent': UA,
    'Referer': HOST + '/',
    'Accept': 'application/json, text/plain, */*',
    'Accept-Language': 'zh-CN,zh;q=0.9'
  };
  if (token) h['token'] = token;
  return h;
}

/* ── 网络请求 ── */
async function fetchText(url, token, timeout) {
  const hd = getHeaders(token);
  const to = timeout || 15000;
  try {
    if (typeof Java !== 'undefined' && Java && Java.req) {
      const r = await Java.req(url, { headers: hd, timeout: to });
      if (typeof r === 'string') return r;
      return String((r && (r.body || r.content || r.data)) || '');
    }
    const r2 = await req(url, { headers: hd, timeout: to });
    if (typeof r2 === 'string') return r2;
    return String((r2 && (r2.content || r2.body || r2.data)) || '');
  } catch (e) {
    return '';
  }
}

async function fetchJson(url, token) {
  try { return JSON.parse(await fetchText(url, token) || '{}'); } catch (e) { return {}; }
}

async function postJson(url, body, token) {
  const hd = getHeaders(token);
  hd['Content-Type'] = 'application/json';
  try {
    if (typeof Java !== 'undefined' && Java && Java.req) {
      const r = await Java.req(url, { headers: hd, method: 'POST', body: JSON.stringify(body), timeout: 10000 });
      if (typeof r === 'string') return JSON.parse(r);
      return JSON.parse(String((r && (r.body || r.content || r.data)) || '{}'));
    }
    const r2 = await req(url, { headers: hd, method: 'POST', body: JSON.stringify(body), timeout: 10000 });
    if (typeof r2 === 'string') return JSON.parse(r2);
    return JSON.parse(String((r2 && (r2.content || r2.body || r2.data)) || '{}'));
  } catch (e) {
    return { code: -1, message: String(e) };
  }
}

/* ── Token 管理 ── */
let _token = null;
let _tokenTime = 0;

async function ensureToken() {
  const now = Date.now();
  if (_token && (now - _tokenTime) < 1800000) return _token;
  try {
    const r = await postJson(HOST + '/api/connect', {});
    if (r && r.code === 0 && r.data && r.data.token) {
      _token = r.data.token;
      _tokenTime = now;
      return _token;
    }
    return null;
  } catch (e) {
    return null;
  }
}

/* ── 获取当天日期 ── */
function todayStr() {
  const d = new Date();
  return d.getFullYear() + '-' +
    String(d.getMonth() + 1).padStart(2, '0') + '-' +
    String(d.getDate()).padStart(2, '0');
}

/* ── 比赛数据 ── */
async function fetchMatchesByDate(dateStr) {
  const token = await ensureToken();
  if (!token) return [];
  const url = HOST + '/api/v2/match-on-date?date=' + (dateStr || todayStr());
  const data = await fetchJson(url, token);
  if (data && data.code === 0 && data.data && Array.isArray(data.data.list)) {
    const matches = [];
    for (const comp of data.data.list) {
      if (comp.match_list && Array.isArray(comp.match_list)) {
        for (const m of comp.match_list) {
          matches.push({
            ...m,
            competition_name: comp.name,
            competition_logo: comp.logo,
            competition_id: comp.id
          });
        }
      }
    }
    return matches;
  }
  if (Array.isArray(data)) return data;
  if (data && data.list) return data.list;
  return [];
}

/* ── 获取比赛详情 ── */
async function fetchMatchDetail(type, cid, mid) {
  const token = await ensureToken();
  if (!token) return null;
  const url = HOST + '/api/v2/match-live/' + type + '/' + cid + '/' + mid;
  const data = await fetchJson(url, token);
  if (data && data.code === 0 && data.data) {
    return data.data;
  }
  return null;
}

/* ── 获取直播流（POST 方式），带重试 ── */
async function fetchLiveStream(type, cid, mid) {
  const token = await ensureToken();
  if (!token) return null;
  // 尝试多种 body 格式
  const bodies = [
    { types: type, cid: cid, mid: mid },
    { type: type, cid: cid, mid: mid },
    { types: String(type), cid: String(cid), mid: String(mid) },
    { stream_type: type, competition_id: cid, match_id: mid }
  ];
  for (const body of bodies) {
    try {
      const data = await postJson(HOST + '/api/v2/match-live-stream', body, token);
      if (data && data.code === 0 && data.data) {
        return data.data;
      }
      // 如果 code===2 说明 session 有问题，重连再试
      if (data && data.code === 2) {
        _token = null; // 强制重连
        const newToken = await ensureToken();
        if (newToken) {
          const retry = await postJson(HOST + '/api/v2/match-live-stream', body, newToken);
          if (retry && retry.code === 0 && retry.data) {
            return retry.data;
          }
        }
      }
    } catch (e) { /* continue */ }
  }
  return null;
}

/* ── 从 lives 数组提取播放 URL（全面字段覆盖） ── */
function extractPlayUrls(lives) {
  const urls = [];
  if (!lives || !Array.isArray(lives) || lives.length === 0) return urls;
  const fieldPriority = [
    'platform_studio_url', // 直链（match-live API）
    'url', 'link', 'src', 'play_url', 'stream_url',
    'hls_url', 'flv_url', 'm3u8_url',
    'stream_link', 'live_url', 'video_url',
    'stream_token'         // 仅路径标识，需构造页面 URL
  ];
  for (let i = 0; i < lives.length; i++) {
    const live = lives[i];
    if (!live) continue;
    const name = live.name || live.title || live.label || '线路' + (i + 1);
    let found = false;
    for (const f of fieldPriority) {
      const val = live[f];
      if (val && typeof val === 'string' && val.trim()) {
        const trimmed = val.trim();
        // stream_token 不是完整 URL，构造页面 URL
        if (f === 'stream_token') {
          urls.push(name + '$' + HOST + '/live/' + trimmed);
        } else if (trimmed.startsWith('http://') || trimmed.startsWith('https://') || trimmed.startsWith('//')) {
          urls.push(name + '$' + trimmed);
        } else if (trimmed.startsWith('/')) {
          urls.push(name + '$' + HOST + trimmed);
        } else {
          urls.push(name + '$' + trimmed);
        }
        found = true;
        break;
      }
    }
    // 兜底：如果有 group 字段也试一下
    if (!found && live.group) {
      const groupPath = String(live.group).replace(/-/g, '/');
      urls.push(name + '$' + HOST + '/live/' + groupPath);
    }
  }
  return urls;
}

/* ── 抓取 SPA 页面 JS 并搜索流 URL 模式 ── */
async function scrapeStreamUrlFromPage(streamToken) {
  if (!streamToken) return null;
  const pageUrl = HOST + '/live/' + streamToken;
  try {
    const html = await fetchText(pageUrl, null, 8000);
    if (!html) return null;
    // 查找主 JS bundle URL
    const jsMatch = html.match(/src="\/assets\/(index-[^"]+\.js)"/);
    if (!jsMatch) return null;
    const jsUrl = HOST + '/assets/' + jsMatch[1];
    // 抓取 JS bundle — 太大只取前 200KB
    const jsContent = await fetchText(jsUrl, null, 10000);
    if (!jsContent) return null;
    // 查找常见流 URL 模式
    const patterns = [
      /https?:\/\/[^'"\s]*?pull[^'"\s]*?\.(flv|m3u8|mp4)(\?[^'"\s]*)?/gi,
      /https?:\/\/[^'"\s]*?\.(flv|m3u8|mp4)\?[^'"\s]*/gi,
      /https?:\/\/[^'"\s]*?(live|stream|play)[^'"\s]*?\.(flv|m3u8|mp4)(\?[^'"\s]*)?/gi,
      /"url"\s*:\s*"https?:\/\/[^"]+\.(flv|m3u8|mp4)[^"]*"/gi,
      /'url'\s*:\s*'https?:\/\/[^']+\.(flv|m3u8|mp4)[^']*'/gi
    ];
    for (const pat of patterns) {
      pat.lastIndex = 0;
      const match = pat.exec(jsContent);
      if (match) {
        // 清理转义
        let url = match[0].replace(/^["']?\s*(?:url\s*:\s*)?["']?/i, '').replace(/["']\s*$/g, '');
        if (url.startsWith('http') || url.startsWith('//')) {
          if (url.startsWith('//')) url = 'https:' + url;
          return url;
        }
      }
    }
    return null;
  } catch (e) {
    return null;
  }
}

/* ── 从 target 对象全面提取可能的流 URL ── */
function extractFallbackUrls(target) {
  const urls = [];
  if (!target) return urls;
  // 检查 target 直接字段
  const directFields = ['url', 'stream_url', 'play_url', 'link', 'src', 'pull_url', 'cdn_url', 'video_url', 'hls_url', 'flv_url', 'm3u8_url', 'stream_link', 'live_url'];
  for (const f of directFields) {
    const val = target[f];
    if (val && typeof val === 'string' && val.trim()) {
      if (val.startsWith('http') || val.startsWith('//')) {
        urls.push('线路$' + val);
      }
    }
  }
  // 检查嵌套对象
  if (target.stream && typeof target.stream === 'object') {
    for (const f of directFields.concat(['token', 'path'])) {
      const val = target.stream[f];
      if (val && typeof val === 'string' && val.trim()) {
        if (val.startsWith('http') || val.startsWith('//')) {
          urls.push('线路$' + val);
        }
      }
    }
  }
  // 检查 data 对象
  if (target.data && typeof target.data === 'object') {
    for (const f of directFields) {
      const val = target.data[f];
      if (val && typeof val === 'string' && val.trim()) {
        if (val.startsWith('http') || val.startsWith('//')) {
          urls.push('线路$' + val);
        }
      }
    }
  }
  return urls;
}

/* ── 构造播放解析用的 header ── */
function makePlayHeader() {
  return {
    'User-Agent': UA,
    'Referer': HOST + '/',
    'Origin': HOST
  };
}

/* ── 状态判断 ── */
function isLive(status) { return status === 0; }
function isFinished(status) { return status === 2; }
function isUpcoming(status) { return status === 1; }

/* ── 构建 VOD（列表用） ── */
function buildVod(match) {
  if (!match) return null;
  const id = String(match.id || match.match_id || '0');
  const type = match.type || 1;
  const cid = match.cid || match.competition_id || 0;
  const homeTeam = match.host_team_name || match.home || match.team1 || '';
  const awayTeam = match.away_team_name || match.away || match.team2 || '';
  const leagueName = match.competition_name || match.name || '';
  const matchTime = match.match_time || match.time || '';
  const status = match.status;
  const hasLive = match.has_live || 0;
  const homeLogo = match.host_team_logo || '';

  // 格式化时间
  let datePart = '', timePart = '';
  if (matchTime) {
    const parts = matchTime.split(' ');
    if (parts.length >= 2) {
      datePart = parts[0];
      timePart = parts[1].substring(0, 5);
    } else if (parts.length === 1) {
      timePart = parts[0].substring(0, 5);
    }
  }

  // 构建 remark
  let remark = '';
  let prefix = '';
  if (isLive(status)) {
    prefix = hasLive ? '🟢 ' : '📅 ';
  } else if (isFinished(status)) {
    prefix = '✅ ';
  } else {
    prefix = '📅 ';
  }

  let timeDisplay = '';
  if (datePart && timePart) {
    timeDisplay = datePart.substring(5) + ' ' + timePart;
  } else if (timePart) {
    timeDisplay = timePart;
  }

  if (timeDisplay && leagueName) {
    remark = prefix + timeDisplay + ' ' + leagueName;
  } else if (leagueName) {
    remark = prefix + leagueName;
  } else if (timeDisplay) {
    remark = prefix + timeDisplay;
  } else {
    remark = prefix + '体育直播';
  }

  const pic = homeLogo || LOGO;
  const vodId = 'fl|' + type + '|' + cid + '|' + id;

  return {
    vod_id: vodId,
    vod_name: homeTeam + ' vs ' + awayTeam,
    vod_pic: pic,
    vod_remarks: remark,
    vod_content: (leagueName || '体育直播') + '\n' + homeTeam + ' vs ' + awayTeam + '\n时间: ' + matchTime,
    type_name: leagueName || '全部'
  };
}

/* ── 分类定义 ── */
function getClasses() {
  return [
    { type_id: 'all', type_name: '全部' },
    { type_id: 'live', type_name: '🟢 直播中' },
    { type_id: 'hot', type_name: '🔥 热门' },
    { type_id: 'football', type_name: '⚽ 足球' },
    { type_id: 'basketball', type_name: '🏀 篮球' }
  ];
}

function isHotLeague(name) {
  if (!name) return false;
  const kw = ['世界杯','world cup','中超','csl','英超','premier league',
    '西甲','laliga','德甲','bundesliga','意甲','serie a','法甲','ligue 1',
    '欧冠','ucl','欧联','uefa','nba','wnba','cba','nbl',
    '中冠','中甲','美职联','mls','巴西甲','brasileirao',
    '夏季联赛','summer league','欧锦','亚洲杯'];
  const lower = name.toLowerCase();
  for (const k of kw) {
    if (lower.includes(k)) return true;
  }
  return false;
}

function isFootballLeague(name, type) {
  if (type === 1) return true;
  if (type === 2) return false;
  if (!name) return true;
  const lower = name.toLowerCase();
  const fbKw = ['football','soccer','足球','fifa','uefa','copa',
    'league','联赛','杯','cup','championship','premier','serie','liga',
    'bundes','eredivisie','ligue','mls','k联赛','j联赛','csl'];
  for (const k of fbKw) {
    if (lower.includes(k)) return true;
  }
  return false;
}

function isBasketballLeague(name, type) {
  if (type === 2) return true;
  if (type === 1) return false;
  if (!name) return false;
  const lower = name.toLowerCase();
  const bkKw = ['basketball','篮球','nba','wnba','cba','nbl',
    'euroleague','欧篮','ncaa','vba','kbl','b联赛','pba'];
  for (const k of bkKw) {
    if (lower.includes(k)) return true;
  }
  return false;
}

/* =========================================================================
 *   爬虫接口
 * ========================================================================= */
async function init(cfg) { }

async function home(filter) {
  return JSON.stringify({ class: getClasses(), filters: {} });
}

async function homeVod() {
  return await category('all', 1, {}, {});
}

async function category(tid, pg, filter, extend) {
  tid = String((extend && extend.cateId) || tid || 'all');
  pg = parseInt(pg) || 1;
  let list = [];

  try {
    const matches = await fetchMatchesByDate(todayStr());

    for (let i = 0; i < matches.length; i++) {
      const m = matches[i];
      if (!m) continue;
      const leagueName = m.competition_name || m.name || '';
      const mtype = m.type || 1;

      if (tid === 'live' && !isLive(m.status)) continue;
      if (tid === 'hot' && !isHotLeague(leagueName)) continue;
      if (tid === 'football' && !isFootballLeague(leagueName, mtype)) continue;
      if (tid === 'basketball' && !isBasketballLeague(leagueName, mtype)) continue;

      const vod = buildVod(m);
      if (vod) list.push(vod);
    }
  } catch (e) { }

  return JSON.stringify({
    code: 1, msg: '赛程列表', page: pg, pagecount: 1,
    limit: 200, total: list.length, list
  });
}

/**
 * 详情页 — 核心修复 V1.2
 * 
 * 策略（按优先级）：
 * 1. 平台直链：platform_studio_url（match-live API 最优先）
 * 2. 标准 URL 字段：url/link/src/play_url/stream_url
 * 3. match-live-stream POST API（多种 body 格式 + 自动重连）
 * 4. 列表数据的 lives 字段
 * 5. SPA 页面 JS 扫描（抓取主 JS bundle 搜索流 URL）
 * 6. stream_token 构造的页面 URL
 * 7. 最终兜底：暂无信号
 */
async function detail(ids) {
  const id = String(Array.isArray(ids) ? ids[0] : ids || '');
  const parts = id.split('|');
  let mtype = 1, cid = 0, mid = 0;
  if (parts.length >= 4) {
    mtype = parseInt(parts[1]) || 1;
    cid = parseInt(parts[2]) || 0;
    mid = parseInt(parts[3]) || 0;
  } else if (parts.length >= 2) {
    mid = parseInt(parts[1]) || 0;
  } else {
    mid = parseInt(id) || 0;
  }

  try {
    // 1) 从列表数据找到比赛（列表 API 确定可用）
    const matches = await fetchMatchesByDate(todayStr());
    let target = null;
    for (let i = 0; i < matches.length; i++) {
      const m = matches[i];
      if (!m) continue;
      if (String(m.id) === String(mid)) {
        target = { ...m };
        break;
      }
    }

    // 2) 尝试 detail API 获取最新 lives（含 platform_studio_url / stream_token）
    let detailLives = null;
    let streamToken = null;
    if (cid > 0 && mid > 0) {
      try {
        const detailData = await fetchMatchDetail(mtype, cid, mid);
        if (detailData) {
          if (detailData.lives && detailData.lives.length > 0) {
            detailLives = detailData.lives;
            // 记录第一个 live 的 stream_token 备用
            if (detailData.lives[0] && detailData.lives[0].stream_token) {
              streamToken = detailData.lives[0].stream_token;
            }
          }
          if (!target) target = {};
          Object.assign(target, detailData);
        }
      } catch (e) { /* ignore */ }
    }

    // 3) 尝试 live-stream POST 接口（多种 body 格式）
    if ((!detailLives || detailLives.length === 0) && cid > 0 && mid > 0) {
      try {
        const streamData = await fetchLiveStream(mtype, cid, mid);
        if (streamData) {
          if (streamData.lives && streamData.lives.length > 0) {
            detailLives = streamData.lives;
          }
          if (!target) target = {};
          Object.assign(target, streamData);
        }
      } catch (e) { /* ignore */ }
    }

    if (!target) {
      return JSON.stringify({ code: 1, msg: 'ok', page: 1, pagecount: 1, limit: 1, total: 0, list: [] });
    }

    // 4) 提取 lives
    const lives = detailLives || target.lives || [];
    let playUrls = extractPlayUrls(lives);

    // 5) 从 target 其他字段尝试提取
    if (playUrls.length === 0) {
      playUrls = extractFallbackUrls(target);
    }

    // 6) 尝试 SPA 页面 JS 扫描（找流 URL）
    if (playUrls.length === 0 && streamToken) {
      try {
        const scrapedUrl = await scrapeStreamUrlFromPage(streamToken);
        if (scrapedUrl) {
          playUrls.push('菲利体育$' + scrapedUrl);
        }
      } catch (e) { /* ignore */ }
    }

    // 7) 最终兜底
    if (playUrls.length === 0) {
      playUrls.push('暂无信号$' + HOST);
    }

    const homeTeam = target.host_team_name || target.home || target.team1 || '';
    const awayTeam = target.away_team_name || target.away || target.team2 || '';
    const leagueName = target.competition_name || target.name || '';
    const matchTime = target.match_time || target.time || '';
    const pic = target.host_team_logo || LOGO;
    const homeScore = target.score || '';
    const awayScore = target.half_score || '';

    const vod = {
      vod_id: id,
      vod_name: homeTeam + ' vs ' + awayTeam,
      vod_pic: pic,
      vod_remarks: (leagueName || '体育直播') + ' ' + (matchTime || ''),
      vod_content: (leagueName || '体育直播') + '\n' +
        homeTeam + ' vs ' + awayTeam + '\n' +
        '时间: ' + matchTime + '\n' +
        '比分: ' + (homeScore || '?') + ' - ' + (awayScore || '?'),
      vod_play_from: '菲利体育',
      vod_play_url: playUrls.join('#')
    };

    return JSON.stringify({
      code: 1, msg: '直播详情', page: 1, pagecount: 1, limit: 1, total: 1, list: [vod]
    });
  } catch (e) {
    return JSON.stringify({ code: 1, msg: 'ok', page: 1, pagecount: 1, limit: 1, total: 0, list: [] });
  }
}

async function search(wd, quick, pg) {
  const keyword = (wd || '').trim().toLowerCase();
  if (!keyword) {
    return JSON.stringify({ code: 1, msg: '搜索', page: 1, pagecount: 1, limit: 20, total: 0, list: [] });
  }

  try {
    const matches = await fetchMatchesByDate(todayStr());
    const list = [];

    for (let i = 0; i < matches.length; i++) {
      const m = matches[i];
      if (!m) continue;
      const homeTeam = m.host_team_name || '';
      const awayTeam = m.away_team_name || '';
      const leagueName = m.competition_name || m.name || '';
      const searchText = (homeTeam + ' ' + awayTeam + ' ' + leagueName).toLowerCase();

      if (searchText.indexOf(keyword) === -1) continue;

      const vod = buildVod(m);
      if (vod) list.push(vod);
    }

    return JSON.stringify({
      code: 1, msg: '搜索结果', page: pg || 1, pagecount: 1, limit: 50, total: list.length, list
    });
  } catch (e) {
    return JSON.stringify({ code: 1, msg: '搜索', page: 1, pagecount: 1, limit: 20, total: 0, list: [] });
  }
}

async function play(flag, id, flags) {
  const url = String(id || '');
  if (/\.(m3u8|flv|mp4)(\?|$)/i.test(url)) {
    return JSON.stringify({
      parse: 0, url: url,
      header: {
        'User-Agent': UA,
        'Referer': HOST + '/',
        'Origin': HOST
      }
    });
  }
  // 如果是页面 URL（无扩展名），尝试用 parse:1 解析
  return JSON.stringify({
    parse: 1, url: url,
    header: {
      'User-Agent': UA,
      'Referer': HOST + '/',
      'Origin': HOST
    }
  });
}

/* =========================================================================
 *   包装函数
 * ========================================================================= */
async function homeContent(f) {
  return safeJson(await home(f), { class: [], filters: {} });
}

async function homeVideoContent() {
  return safeJson(await homeVod(), { list: [] });
}

async function categoryContent(tid, pg, f, ext) {
  return safeJson(await category(tid, pg, f, ext || {}), { list: [] });
}

async function detailContent(ids) {
  return safeJson(await detail(ids), { list: [] });
}

async function searchContent(wd, q, pg) {
  return safeJson(await search(wd, q, pg || 1), { list: [] });
}

async function playerContent(flag, id, flags) {
  return safeJson(await play(flag, id, flags), { parse: 1, url: id });
}

/* =========================================================================
 *   引擎导出
 * ========================================================================= */
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
