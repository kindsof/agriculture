// 农业水利 · 前端公共层：API 客户端、导航外壳、URL 状态、少量 DOM 工具
export const API = '';                       // 同源；将来搬 GitHub Pages 只改这一行

export const NAV = [
  { href: '/home.html', label: '首页', key: 'home' },
  { href: '/books.html', label: '书目总览', key: 'books' },
  { href: '/search.html', label: '古籍检索', key: 'search' },
  { href: '/calendar.html', label: '节气农事', key: 'calendar' },
  { href: '/map.html', label: '农耕文化地图', key: 'map' },
];

export function esc(s) {
  return String(s == null ? '' : s).replace(/[&<>"']/g, c =>
    ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));
}

export function fmtNum(n) {
  n = Number(n) || 0;
  if (n >= 10000) return (n / 10000).toFixed(n >= 1000000 ? 0 : 1) + ' 万';
  return n.toLocaleString('zh-CN');
}

export async function api(path, params) {
  const u = new URL(API + path, location.origin);
  for (const [k, v] of Object.entries(params || {})) {
    if (v !== '' && v != null) u.searchParams.set(k, v);
  }
  const r = await fetch(u, { headers: { Accept: 'application/json' } });
  const ct = r.headers.get('content-type') || '';
  if (!r.ok) {
    let detail = '';
    try { detail = (await r.json()).detail || ''; } catch (e) { /* 非 JSON */ }
    throw new Error(`${r.status} ${r.statusText}${detail ? ' · ' + detail : ''}`);
  }
  return ct.includes('json') ? r.json() : r.text();
}

// 站内导航由脚本统一注入，避免四个页面各写一份而走样
// 地图页 body 是 overflow:hidden 的满屏应用，只能关成页脚（备案写到它的边栏里）
export function shell(active, opts) {
  const withFooter = !(opts && opts.footer === false);
  const nav = document.createElement('nav');
  nav.className = 'nav';
  nav.innerHTML = `<div class="nav-inner">
    <div class="brand"><b>农业水利</b><span>古籍 · 图谱 · 农耕文化</span></div>
    ${NAV.map(t => `<a class="tab" href="${t.href}"${
      t.key === active ? ' aria-current="page"' : ''}>${t.label}</a>`).join('')}
    <div class="nav-spacer"></div>
    ${active === 'search' ? '' : `<button class="nav-quick" id="quick" type="button">
      <span>检索古籍</span><kbd>/</kbd></button>`}
  </div>`;
  document.body.prepend(nav);
  const quick = nav.querySelector('#quick');
  if (quick) quick.onclick = () => location.href = '/search.html';
  // 页脚统一注入：备案号必须站内每页可见（参照 nongxin.info 页脚）
  if (withFooter && !document.querySelector('footer.foot')) {
    const f = document.createElement('footer');
    f.className = 'foot';
    f.innerHTML = `<div class="foot-inner">
      <div class="foot-main">
        <span class="quote">文臣不爱钱，武臣不惜死，天下太平矣。</span>
        <span class="sep">·</span>
        <span>数据纠错 <a href="https://github.com/kindsof/agriculture" target="_blank" rel="noopener">kindsof/agriculture</a>・内容 CC-BY-SA-4.0</span>
      </div>
      <div class="foot-legal">
        <a href="https://beian.miit.gov.cn/" target="_blank" rel="nofollow noopener">京ICP备2021026212号-3</a>
        <span class="sep">·</span><span>wm.nongxin.info</span>
      </div></div>`;
    document.body.append(f);
  }
  return nav;
}

export function debounce(fn, ms = 250) {
  let t;
  return (...a) => { clearTimeout(t); t = setTimeout(() => fn(...a), ms); };
}

// —— URL 状态：任何筛选结果都可分享、可前进后退 ——
export function readState() {
  const o = {};
  new URLSearchParams(location.search).forEach((v, k) => { o[k] = v; });
  return o;
}
export function writeState(o, push) {
  const p = new URLSearchParams();
  for (const [k, v] of Object.entries(o)) if (v !== '' && v != null) p.set(k, v);
  const q = p.toString();
  const url = location.pathname + (q ? '?' + q : '');
  history[push ? 'pushState' : 'replaceState']({}, '', url);
}

export function fail(node, err) {
  // 必须把真实错因带出来：只有「服务未启动」这一句时，前端 bug 会被当成宕机
  const detail = err ? `${err.name || 'Error'}: ${err.message || err}` : '未知错误';
  const where = err && err.stack ? String(err.stack).split('\n')[1] : '';
  node.innerHTML = `<div class="empty">加载失败：${esc(detail)}
    <div class="meta" style="margin-top:8px">若提示 Failed to fetch，才是检索服务未启动，
    在服务器上执行 <code>./corpus/run_api.sh status</code></div>
    ${where ? `<div class="meta" style="margin-top:6px;font-family:var(--mono);font-size:11px;opacity:.75">${esc(where.trim())}</div>` : ''}</div>`;
}

// 古籍正文：剥掉 YAML frontmatter，按空行与卷首标记分段
export function renderText(raw) {
  let t = String(raw || '');
  t = t.replace(/^---\n[\s\S]*?\n---\n?/, '');
  const out = [];
  for (const block of t.split(/\n{2,}/)) {
    const b = block.trim();
    if (!b) continue;
    if (b.length < 40 && /^(卷|第|序|目録|目錄|凡例|提要|[一二三四五六七八九十]|\s*[卷篇])/.test(b)) {
      out.push(`<h5>${esc(b)}</h5>`);
    } else {
      out.push(b.split('\n').map(l => l.trim()).filter(Boolean)
        .map(l => `<p>${esc(l)}</p>`).join(''));
    }
  }
  return out.join('');
}
