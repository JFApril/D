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
    const json = await fetchJson(host + '/api/v1/room/' + encodeURIComponent(roomId) + '?_t=' + Date.now());
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

    for (let i = 0; i < signals.length; i++) addLine(signals[i].name, signals[i].stream_url);
    addLine(archor.name, archor.stream_url);

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
