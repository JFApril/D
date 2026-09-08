/*
@header({
  searchable: 0,
  filterable: 0,
  quickSearch: 0,
  title: '咖啡直播[体]',
  author: 'OpenClaw',
  lang: 'cat',
  style: { type: 'rect', ratio: 0.75 }
})
V1.6: 修复V1.5 master判定失效(^锚点正则无m标志, master以#EXTM3U开头永远匹配不上 → 直播线误判✅且·高清从未插入); 改indexOf识别master; 加debug日志跟踪变体提取
V1.5: master playlist变体解析 - hello.ooo0ooo.top是master(只含EXT-X-STREAM-INF指向aarray真流), 壳播放器不跟随变体选择播不出; 探测时解析变体media playlist作为独立线路(·高清)置顶
V1.4: 探测改req通道优先(isolate内fetch不走壳网络层且不可靠, V1.3误判全❌的根因); 3s超时; req返回status>=400判失效; 启发式顺序改 原声>archor>其他
V1.3: detail()接口手动跟随301重定向(ext配.com时API会301跳.cc, 壳req不跟随会拿空数据); 探测失败时按archor位置+原声优先启发式重排, 不再回退原始顺序
V1.2: detail()播放线路探测重排 - 并行探测m3u8(2.5s超时), 可用线路置顶, 失效线路标注❌排后(解决"直播信号失效但原声可用"时默认源挂掉的问题)
*/

let host = 'https://kafeizhibo.cc';
const UA = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/140.0.0.0 Safari/537.36';
const headers = {
  'User-Agent': UA,
  'Referer': host + '/pc',
  'Accept': 'application/json, text/plain, */*'
};

function safeJson(text, def) {
  try { return JSON.parse(text || '{}'); } catch (e) { return def || {}; }
}

function absUrl(url) {
  url = String(url || '').trim();
  if (!url) return '';
  if (/^https?:\/\//i.test(url)) return url;
  if (url.indexOf('//') === 0) return 'https:' + url;
  if (url.charAt(0) === '/') return host + url;
  return host + '/' + url;
}

function clean(s) {
  return String(s || '').replace(/<[^>]+>/g, '').replace(/\s+/g, ' ').trim();
}

async function fetchJson(url) {
  const r = await req(url, { headers });
  return safeJson((r && (r.content || r.body)) || '{}', {});
}

async function fetchJsonFollow(url) {
  // V1.3: 手动跟随 301/302 重定向(壳 req 不跟随时 .com API 会 301 跳 .cc)
  let u = url;
  for (let i = 0; i < 4; i++) {
    let r = null;
    try { r = await req(u, { headers }); } catch (e) { return {}; }
    const st = (r && (r.status || r.statusCode)) || 0;
    if (st === 301 || st === 302) {
      let loc = '';
      try { loc = (r.headers || r.responseHeaders || {}); const kv = (typeof loc === 'string') ? {} : loc; for (const k in kv) { if (String(k).toLowerCase() === 'location') { loc = kv[k]; break; } } if (typeof loc !== 'string') loc = (loc && loc.location) || ''; } catch (e) { loc = ''; }
      if (typeof loc === 'string' && loc) { u = /^https?:\/\//i.test(loc) ? loc : absUrl(loc); continue; }
      return {};
    }
    return safeJson((r && (r.content || r.body)) || '{}', {});
  }
  try { r = await req(u, { headers }); return safeJson((r && (r.content || r.body)) || '{}', {}); } catch (e) { return {}; }
}

function m3u8Ok(t) {
  return /#EXTM3U|#EXTINF|#EXT-X-STREAM-INF/i.test(String(t || ''));
}

// V1.5: master playlist 变体提取 - 取带宽最高的变体URL, 相对路径转绝对
function pickVariant(t, baseUrl) {
  const lines = String(t || '').split(/\r?\n/);
  let best = { bw: -1, url: '' };
  let pendingBw = -1;
  for (let i = 0; i < lines.length; i++) {
    const l = lines[i].trim();
    if (!l) continue;
    if (/^#EXT-X-STREAM-INF/i.test(l)) {
      const m = l.match(/BANDWIDTH=(\d+)/i);
      pendingBw = m ? parseInt(m[1]) : 0;
    } else if (l.charAt(0) !== '#') {
      if (pendingBw >= 0) {
        let u = l;
        if (u.indexOf('//') === 0) u = 'https:' + u;
        else if (u.charAt(0) === '/') {
          const m2 = baseUrl.match(/^(https?:\/\/[^\/]+)/);
          u = (m2 ? m2[1] : '') + u;
        } else if (u.charAt(0) !== 'h') {
          u = baseUrl.substring(0, baseUrl.lastIndexOf('/') + 1) + u;
        }
        if (u.indexOf('http') === 0 && pendingBw > best.bw) best = { bw: pendingBw, url: u };
      }
      pendingBw = -1;
    }
  }
  return best.url;
}

// 返回 {alive: true/false/null, variant: 变体真流URL(仅master时)}
async function probeStream(url) {
  function withTimeout(p, ms) {
    let to;
    const t = new Promise(function (_, rej) { to = setTimeout(function () { rej(new Error('timeout')); }, ms); });
    return Promise.race([p, t]).then(function (v) { clearTimeout(to); return v; }, function (e) { clearTimeout(to); throw e; });
  }
  function readBody(r) {
    if (typeof r === 'string') return { st: 0, t: r };
    if (!r) return { st: 0, t: '' };
    return { st: r.status || r.statusCode || 0, t: String(r.content || r.body || r.data || '') };
  }
  function judge(st, t) {
    if (m3u8Ok(t)) return { st: st, t: t };
    if (st >= 400) return null;
    if (/404|not\s?found/i.test(t)) return null;
    if (!t) return undefined;
    return { st: st, t: t }; // 有内容非m3u8
  }
  const forms = [
    { method: 'GET', headers: { 'User-Agent': UA, 'Referer': host + '/pc' } },
    { method: 'GET' },
    null
  ];
  let first = null;
  if (typeof req === 'function') {
    for (let i = 0; i < forms.length; i++) {
      try {
        const r = forms[i] ? await withTimeout(req(url, forms[i]), 3000) : await withTimeout(req(url), 3000);
        first = judge(readBody(r).st, readBody(r).t);
        if (first !== undefined) break; // 拿到结论(死/活/非m3u8)
      } catch (e) { /* 换形态 */ }
    }
  } else if (typeof fetch === 'function') {
    try {
      const r = await withTimeout(fetch(url, { method: 'GET', headers: { 'User-Agent': UA, 'Referer': host + '/pc' } }), 3000);
      const t = (r && typeof r.text === 'function') ? await r.text().catch(function () { return ''; }) : '';
      first = judge(r ? (r.status || 0) : 0, t);
    } catch (e) { /* 无结论 */ }
  }
  if (first === null) return { alive: false, variant: '' };
  if (first === undefined) return { alive: null, variant: '' };
  // 是 m3u8: 判断 master 还是 media
  if (first.t.indexOf('#EXT-X-STREAM-INF') !== -1) {
    // master: 提取变体真流, 顺带验证变体可达
    const v = pickVariant(first.t, url);
    console.log('[detail Debug] master 识别: ' + url + ' 变体=' + (v || '(未提取到)'));
    if (!v) return { alive: true, variant: '' };
    let vAlive = true; // 乐观: master 能回就默认变体可达
    try {
      const vf = forms[0];
      const rv = await withTimeout(req ? (vf ? req(v, vf) : req(v)) : fetch(v), 3000);
      const vb = (req && (typeof rv === 'string' || rv && (rv.content || rv.body || rv.data || rv.status !== undefined))) ? readBody(rv) : { st: rv ? (rv.status || 0) : 0, t: (rv && typeof rv.text === 'function') ? await rv.text().catch(function () { return ''; }) : '' };
      const vj = judge(vb.st, vb.t);
      vAlive = vj !== null;
    } catch (e) { vAlive = true; }
    // master 本身不是流(壳播放器不跟随变体选择, 播不出) => 标记失效, 变体真流另行置顶
    return { alive: false, variant: vAlive ? v : '' };
  }
  return { alive: true, variant: '' };
}

function getClasses() {
  return [
    { type_id: 'all', type_name: '全部直播' },
    { type_id: 'hot', type_name: '热门直播' },
    { type_id: 'nba', type_name: 'NBA' },
    { type_id: '1', type_name: '足球直播' },
    { type_id: '2', type_name: '篮球直播' },
    { type_id: '3', type_name: '网球直播' },
    { type_id: '19', type_name: '台球直播' },
    { type_id: 'schedule', type_name: '赛程列表' },
    { type_id: 'recordings', type_name: '录像' }
  ];
}

function titleOf(it) {
  const mi = it.match_info || {};
  const league = it.league_name || mi.league_name || it.league || '';
  const home = it.home_team || mi.home_team || (it.homeTeam && it.homeTeam.name) || '';
  const away = it.away_team || mi.away_team || (it.awayTeam && it.awayTeam.name) || '';
  const title = it.title || it.name || '';
  if (title && title !== it.name) return clean(title);
  if (league && home && away) return clean(league + ' ' + home + ' vs ' + away);
  return clean(title || it.name || ('直播间 ' + (it.room_id || it.id || '')));
}

function remarkOf(it) {
  const parts = [];
  const status = it.status || (it.match_info && it.match_info.status) || '';
  if (status === 'live' || it.is_live) parts.push('直播中');
  else if (status === 'online') parts.push('在线');
  else if (status === 'upcoming') parts.push('未开赛');
  else if (status) parts.push(status);
  const score = (it.home_score !== undefined && it.away_score !== undefined) ? (it.home_score + '-' + it.away_score) : '';
  if (score && score !== '0-0') parts.push(score);
  if (it.heat) parts.push('热度:' + it.heat);
  if (it.name && it.title && it.name !== it.title) parts.push(it.name);
  return clean(parts.join(' ')) || '直播';
}

function picOf(it) {
  return absUrl(it.screenshot || it.avatar || it.home_team_logo || it.away_team_logo || (it.homeTeam && it.homeTeam.logo) || (it.awayTeam && it.awayTeam.logo) || '/images/logo.png');
}

function itemToVod(it) {
  const roomId = it.room_id || (it.archor && it.archor.room_id) || (Array.isArray(it.archors) && it.archors[0] && it.archors[0].room_id) || '';
  if (!roomId) return null;
  return {
    vod_id: String(roomId) + '###' + encodeURIComponent(titleOf(it)),
    vod_name: titleOf(it),
    vod_pic: picOf(it),
    vod_remarks: remarkOf(it)
  };
}

function recordingToVod(it) {
  const matchId = it.match_id || it.id || '';
  if (!matchId) return null;
  const name = titleOf(it);
  return {
    vod_id: 'rec$' + String(matchId) + '###' + encodeURIComponent(name),
    vod_name: name,
    vod_pic: absUrl(it.cover_image || it.screenshot || it.home_team_logo || it.away_team_logo || '/images/logo.png'),
    vod_remarks: clean([it.start_time || '', it.recording_count ? ('录像:' + it.recording_count) : '录像'].filter(Boolean).join(' '))
  };
}

async function init(cfg) {
  if (cfg && cfg.ext && String(cfg.ext).indexOf('http') === 0) host = String(cfg.ext).trim().replace(/\/$/, '');
}

async function home(filter) {
  return JSON.stringify({ class: getClasses(), filters: {} });
}

async function homeVod() {
  return await category('all', 1, false, {});
}

async function category(tid, pg, filter, extend) {
  tid = String((extend && extend.cateId) || tid || 'all');
  pg = parseInt(pg) || 1;
  const size = 30;
  let apiUrl = '';

  if (tid === 'schedule') {
    apiUrl = host + '/api/v1/schedule?type=all&page=' + pg + '&size=' + size + '&_t=' + Date.now();
  } else if (tid === 'recordings') {
    apiUrl = host + '/api/v1/recordings?page=' + pg + '&size=' + size + '&_t=' + Date.now();
  } else if (tid === 'nba') {
    // 官网没有单独 nba 参数；用篮球赛程聚合后按 NBA 关键字过滤，有 NBA 时显示 NBA，无 NBA 时为空不混入其他篮球。
    apiUrl = host + '/api/v1/schedule?type=2&page=' + pg + '&size=100&_t=' + Date.now();
  } else {
    const type = tid === 'all' ? '' : tid;
    apiUrl = host + '/api/v1/archor?type=' + encodeURIComponent(type) + '&_t=' + Date.now();
  }

  let list = [];
  let total = 0;
  try {
    const json = await fetchJson(apiUrl);
    const data = Array.isArray(json.data) ? json.data : [];
    const seen = {};
    for (let i = 0; i < data.length; i++) {
      if (tid === 'recordings') {
        const vod = recordingToVod(data[i]);
        if (vod && !seen[vod.vod_id]) { seen[vod.vod_id] = true; list.push(vod); }
      } else if (tid === 'nba') {
        const title = titleOf(data[i]);
        if (!/NBA|美职篮|美国职业篮球/i.test(title)) continue;
        if (Array.isArray(data[i].archors) && data[i].archors.length) {
          for (let j = 0; j < data[i].archors.length; j++) {
            const merged = Object.assign({}, data[i], data[i].archors[j], {
              title,
              screenshot: data[i].screenshot || data[i].archors[j].screenshot
            });
            const vod = itemToVod(merged);
            if (vod && !seen[vod.vod_id]) { seen[vod.vod_id] = true; list.push(vod); }
          }
        } else {
          const vod = itemToVod(data[i]);
          if (vod && !seen[vod.vod_id]) { seen[vod.vod_id] = true; list.push(vod); }
        }
      } else if (tid === 'schedule' && Array.isArray(data[i].archors) && data[i].archors.length) {
        for (let j = 0; j < data[i].archors.length; j++) {
          const merged = Object.assign({}, data[i], data[i].archors[j], {
            title: titleOf(data[i]),
            screenshot: data[i].screenshot || data[i].archors[j].screenshot
          });
          const vod = itemToVod(merged);
          if (vod && !seen[vod.vod_id]) { seen[vod.vod_id] = true; list.push(vod); }
        }
      } else {
        const vod = itemToVod(data[i]);
        if (vod && !seen[vod.vod_id]) { seen[vod.vod_id] = true; list.push(vod); }
      }
    }
    total = tid === 'nba' ? list.length : (json.total || list.length);
  } catch (e) {
    list = [];
  }
  return JSON.stringify({ code: 1, msg: '数据列表', page: pg, pagecount: 1, limit: size, total, list });
}

async function detail(id) {
  id = Array.isArray(id) ? id[0] : id;
  let roomId = String(id || '');
  let displayName = '咖啡直播';
  if (roomId.indexOf('###') >= 0) {
    const parts = roomId.split('###');
    roomId = parts[0];
    try { displayName = decodeURIComponent(parts[1] || displayName); } catch (e) { displayName = parts[1] || displayName; }
  }
  if (roomId.indexOf('rec$') === 0) {
    const matchId = roomId.slice(4);
    let vod = {
      vod_id: roomId,
      vod_name: displayName,
      vod_pic: host + '/images/logo.png',
      vod_remarks: '录像',
      vod_play_from: '咖啡录像',
      vod_play_url: '',
      vod_content: '咖啡直播赛事录像'
    };
    try {
      const json = await fetchJson(host + '/api/v1/match/' + encodeURIComponent(matchId) + '/recordings?_t=' + Date.now());
      const data = json.data || {};
      const match = data.match || {};
      const urls = [];
      const replays = Array.isArray(data.replays) ? data.replays : [];
      const highlights = Array.isArray(data.highlights) ? data.highlights : [];
      for (let i = 0; i < replays.length; i++) {
        if (replays[i].video_url) urls.push(clean(replays[i].title || ('录像' + (i + 1))) + '$' + replays[i].video_url);
      }
      for (let i = 0; i < highlights.length; i++) {
        if (highlights[i].video_url) urls.push(clean(highlights[i].title || ('集锦' + (i + 1))) + '$' + highlights[i].video_url);
      }
      vod = {
        vod_id: roomId,
        vod_name: titleOf(match) || displayName,
        vod_pic: absUrl((replays[0] && replays[0].cover_image) || match.cover_image || match.home_team_logo || match.away_team_logo || '/images/logo.png'),
        vod_remarks: clean([match.start_time || '', match.home_score !== undefined ? (match.home_score + '-' + match.away_score) : ''].filter(Boolean).join(' ')) || '录像',
        vod_play_from: '咖啡录像',
        vod_play_url: urls.join('#'),
        vod_content: '咖啡直播赛事录像'
      };
    } catch (e) {}
    return JSON.stringify({ code: 1, msg: '数据列表', page: 1, pagecount: 1, limit: 1, total: 1, list: [vod] });
  }
  if (!roomId) return JSON.stringify({ code: 1, page: 1, pagecount: 1, limit: 0, total: 0, list: [] });

  let vod = {
    vod_id: roomId,
    vod_name: displayName,
    vod_pic: host + '/images/logo.png',
    vod_remarks: '直播',
    vod_play_from: '咖啡直播',
    vod_play_url: '',
    vod_content: '咖啡直播实时体育直播'
  };

  try {
    const json = await fetchJsonFollow(host + '/api/v1/room/' + encodeURIComponent(roomId) + '?_t=' + Date.now());
    const data = json.data || {};
    const room = data.room_info || {};
    const archor = data.archor || {};
    const signals = Array.isArray(data.signals) ? data.signals : [];
    const urls = [];
    const seen = {};

    function addLine(name, url) {
      url = String(url || '').trim();
      if (!url || seen[url]) return;
      seen[url] = true;
      urls.push(clean(name || ('线路' + (urls.length + 1))) + '$' + url);
    }

    // V1.2: 收集线路 -> 并行探测可达性 -> 可用置顶, 失效标注❌排后
    const cands = [];
    const cSeen = {};
    function pushCand(name, url) {
      url = String(url || '').trim();
      if (!url || cSeen[url]) return;
      cSeen[url] = true;
      cands.push({ name: clean(name || '') || ('线路' + (cands.length + 1)), url });
    }
    for (let i = 0; i < signals.length; i++) pushCand(signals[i].name, signals[i].stream_url);
    pushCand(archor.name, archor.stream_url);
    // 只探测 m3u8 直播流(非 http 直链/回放不探, 按原序保留)
    const probed = await Promise.all(cands.map(function (cd) {
      if (!/\.m3u8(\?|$)/i.test(cd.url)) return Promise.resolve({ cd: cd, alive: null, variant: '' });
      return probeStream(cd.url).then(function (r) { return { cd: cd, alive: r.alive, variant: r.variant || '' }; });
    }));
    // V1.5: master变体真流 作为独立线路插入(标记·高清)
    for (let i = 0; i < probed.length; i++) {
      const p = probed[i];
      if (p.variant && !cSeen[p.variant]) {
        cSeen[p.variant] = true;
        probed.splice(i + 1, 0, { cd: { name: p.cd.name + '·高清', url: p.variant }, alive: true, variant: '' });
      }
    }
    // 排序: 可用(按原序) -> 未知(按原序) -> 失效(按原序)
    const order = { true: 0, null: 1, false: 2 };
    probed.sort(function (a, b) { return order[a.alive] - order[b.alive]; });
    // V1.4 启发式兜底: 探测无结论时(全null), 按 原声>archor当前信号>其他 重排(解说信号常失效, 原声最稳)
    const conclusive = probed.some(function (p) { return p.alive !== null; });
    if (!conclusive) {
      const archorUrl = String((archor && archor.stream_url) || '').trim();
      function heurScore(p) {
        if (/原声/i.test(p.cd.name)) return 0;              // 原声信号最稳
        if (p.cd.url === archorUrl) return 1;              // 平台当前主播信号
        return 2;                                          // 其他
      }
      probed.sort(function (a, b) { return heurScore(a) - heurScore(b); });
    }
    for (let i = 0; i < probed.length; i++) {
      const p = probed[i];
      if (p.alive === false) addLine(p.cd.name + ' ❌', p.cd.url);
      else if (p.alive === null) addLine(p.cd.name, p.cd.url);
      else addLine(p.cd.name + ' ✅', p.cd.url);
    }

    const title = room.title || displayName;
    vod = {
      vod_id: roomId,
      vod_name: clean(title),
      vod_pic: absUrl(archor.screenshot || room.avatar || archor.avatar || '/images/logo.png'),
      vod_remarks: remarkOf(Object.assign({}, room, archor)),
      vod_play_from: '咖啡直播',
      vod_play_url: urls.join('#'),
      vod_content: clean(room.notice || room.notice_h5 || '咖啡直播实时体育直播')
    };
  } catch (e) {}

  return JSON.stringify({ code: 1, msg: '数据列表', page: 1, pagecount: 1, limit: 1, total: 1, list: [vod] });
}

async function search(wd, quick, pg) {
  return JSON.stringify({ code: 1, msg: '数据列表', page: parseInt(pg) || 1, pagecount: 1, limit: 20, total: 0, list: [] });
}

async function play(flag, id, flags) {
  return JSON.stringify({ parse: 0, url: id, header: headers });
}

async function homeContent(filter) { return safeJson(await home(filter), { class: [], filters: {} }); }
async function homeVideoContent() { return safeJson(await homeVod(), { list: [] }); }
async function categoryContent(tid, pg, filter, extend) { return safeJson(await category(tid, pg, filter, extend || {}), { list: [] }); }
async function detailContent(ids) { return safeJson(await detail(ids), { list: [] }); }
async function searchContent(wd, quick, pg) { return safeJson(await search(wd, quick, pg || 1), { list: [] }); }
async function playerContent(flag, id, flags) { return safeJson(await play(flag, id, flags), { parse: 0, url: id }); }

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
