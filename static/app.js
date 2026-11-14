// 科研小助手 Agent —— 前端逻辑（原生 JS，无框架依赖）
const $ = (s, r = document) => r.querySelector(s);
const $$ = (s, r = document) => Array.from(r.querySelectorAll(s));

const state = {
  papers: [],
  selected: new Set(),
  reader: { pid: null, page: 1, total: 1, struct: null, trans: new Map() },
};

async function api(path, opts = {}) {
  const res = await fetch(path, opts);
  if (!res.ok) {
    let msg = res.statusText;
    try { msg = (await res.json()).detail || msg; } catch (e) {}
    throw new Error(msg);
  }
  return res.json();
}

// ---------- 全局状态 ----------
async function refreshStatus() {
  try {
    const s = await api('/api/status');
    $('#sysStatus').textContent = s.llm_ready
      ? `模型已就绪 · ${s.model} · 论文 ${s.papers} 篇`
      : `未配置大模型（问答将只回原文证据） · 论文 ${s.papers} 篇`;
  } catch (e) {
    $('#sysStatus').textContent = '服务未响应';
  }
}

// ---------- 页签 ----------
$$('.tabs button').forEach(btn => {
  btn.onclick = () => {
    $$('.tabs button').forEach(b => b.classList.remove('active'));
    btn.classList.add('active');
    $$('.tab-panel').forEach(p => p.classList.remove('active'));
    $(`#tab-${btn.dataset.tab}`).classList.add('active');
    if (btn.dataset.tab === 'library') loadLibrary();
    if (btn.dataset.tab === 'reader') loadReaderSelect();
  };
});

// ---------- 文库 ----------
async function loadLibrary() {
  const data = await api('/api/papers');
  state.papers = data.papers;
  const tb = $('#paperTable tbody');
  tb.innerHTML = '';
  $('#libEmpty').style.display = state.papers.length ? 'none' : 'block';
  state.papers.forEach(p => {
    const tr = document.createElement('tr');
    tr.innerHTML = `
      <td></td>
      <td class="title">${escapeHtml(p.title || p.filename)}</td>
      <td>${p.year || '-'}</td>
      <td>${p.n_pages}</td>
      <td>${p.n_chars}</td>
      <td>${p.n_refs}</td>
      <td>${p.columns === 2 ? '双栏' : '单栏'}</td>
      <td><button class="ghost" data-act="read">阅读</button>
          <button class="ghost" data-act="del">删除</button></td>`;
    tr.querySelector('[data-act=read]').onclick = () => openReader(p.id);
    tr.querySelector('[data-act=del]').onclick = async () => {
      if (!confirm(`确定删除《${p.title || p.filename}》？文件会一并删除。`)) return;
      await api(`/api/papers/${p.id}`, { method: 'DELETE' });
      loadLibrary();
    };
    tb.appendChild(tr);
  });
  refreshStatus();
  renderQaChips();
}
$('#btnRefreshLib').onclick = loadLibrary;

const dz = $('#dropzone');
dz.onclick = () => $('#fileInput').click();
dz.ondragover = e => { e.preventDefault(); dz.classList.add('over'); };
dz.ondragleave = () => dz.classList.remove('over');
dz.ondrop = e => {
  e.preventDefault(); dz.classList.remove('over');
  if (e.dataTransfer.files.length) uploadFiles(e.dataTransfer.files);
};
$('#fileInput').onchange = e => { if (e.target.files.length) uploadFiles(e.target.files); };

async function uploadFiles(fileList) {
  const fd = new FormData();
  Array.from(fileList).forEach(f => fd.append('files', f));
  fd.append('on_duplicate', 'ask');
  $('#uploadLog').textContent = `上传 ${fileList.length} 个文件…`;
  try {
    const data = await api('/api/upload', { method: 'POST', body: fd });
    const lines = [];
    for (const r of data.results) {
      if (r.status === 'ingested') lines.push(`✅ ${r.name}：${r.meta.title}（${r.meta.n_pages} 页，${r.meta.n_refs} 篇参考文献）`);
      else if (r.status === 'duplicate') {
        lines.push(await askDuplicate(r));
      } else lines.push(`❌ ${r.name}：${r.message}`);
    }
    $('#uploadLog').textContent = lines.join('\n');
    loadLibrary();
  } catch (e) {
    $('#uploadLog').textContent = '上传失败：' + e.message;
  }
}

// 重复文件处理：展示差异，让用户选保留哪版
function askDuplicate(r) {
  return new Promise(resolve => {
    const diff = r.diff;
    const msg = [
      `检测到内容重复：《${r.existing.title}》（相似度 ${(r.similarity * 100).toFixed(0)}%）`,
      `库里已有：${r.existing.meta.n_pages} 页 / ${r.existing.meta.n_chars} 字符 / ${r.existing.meta.n_refs} 篇参考文献`,
      `新上传：${r.incoming_meta.n_pages} 页 / ${r.incoming_meta.n_chars} 字符 / ${r.incoming_meta.n_refs} 篇参考文献`,
      `章节新增：${(diff.sections_added || []).join('、') || '无'}`,
      `章节删除：${(diff.sections_removed || []).join('、') || '无'}`,
      `结论：${r.suggestion}`,
      '',
      '确定 = 保留新版本（覆盖库里旧版）',
      '取消 = 两个版本都保留（并存）',
    ].join('\n');
    const useNew = confirm(msg);
    const action = useNew ? 'keep_new' : 'keep_both';
    api('/api/upload/confirm', {
      method: 'POST', headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ staged: r.staged, name: r.existing.filename, action }),
    }).then(() => resolve(`↻ ${r.existing.title}：已按「${useNew ? '保留新版' : '两个都留'}」处理`))
      .catch(e => resolve('重复处理失败：' + e.message));
  });
}

$('#btnArxivId').onclick = async () => {
  const ids = $('#arxivIds').value.split(/[\s,]+/).filter(Boolean);
  if (!ids.length) return;
  $('#arxivLog').textContent = '下载中…';
  try {
    const data = await api('/api/ingest/arxiv', {
      method: 'POST', headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ ids }),
    });
    $('#arxivLog').textContent = data.results.map(r => `${r.status === 'ingested' ? '✅' : '⚠️'} ${r.arxiv_id} ${r.title || r.message || ''}`).join('\n');
    loadLibrary();
  } catch (e) { $('#arxivLog').textContent = '失败：' + e.message; }
};

$('#btnArxivSearch').onclick = async () => {
  const q = $('#arxivQuery').value.trim();
  if (!q) return;
  $('#arxivLog').textContent = '检索中…';
  try {
    const data = await api('/api/ingest/arxiv', {
      method: 'POST', headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ query: q, max: 3 }),
    });
    $('#arxivLog').textContent = data.results.map(r => `${r.status === 'ingested' ? '✅' : '⚠️'} ${r.arxiv_id} ${r.title || r.message || ''}`).join('\n');
    loadLibrary();
  } catch (e) { $('#arxivLog').textContent = '失败：' + e.message; }
};

function escapeHtml(s) {
  return (s || '').replace(/[&<>"']/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));
}

// ---------- 阅读 ----------
async function loadReaderSelect() {
  const data = await api('/api/papers');
  state.papers = data.papers;
  const sel = $('#readerPaper');
  sel.innerHTML = state.papers.map(p => `<option value="${p.id}">${escapeHtml((p.title || p.filename).slice(0, 80))}</option>`).join('');
  if (!sel.value && state.papers.length) sel.value = state.papers[0].id;
  if (sel.value) loadReader(Number(sel.value));
  renderQaChips();
}

$('#readerPaper').onchange = e => loadReader(Number(e.target.value));

function openReader(pid) {
  $$('.tabs button').forEach(b => b.classList.toggle('active', b.dataset.tab === 'reader'));
  $$('.tab-panel').forEach(p => p.classList.toggle('active', p.id === 'tab-reader'));
  $('#readerPaper').value = String(pid);
  loadReader(pid);
}

async function loadReader(pid) {
  state.reader = { pid, page: 1, total: 1, struct: null, trans: new Map(), backTo: null, syncing: false };
  const st = await api(`/api/papers/${pid}/struct`);
  state.reader.struct = st;
  const tree = $('#outlineTree');
  tree.innerHTML = '';
  (st.outline || []).forEach(h => {
    const div = document.createElement('div');
    div.className = 'lv' + Math.min(h.level, 3);
    div.textContent = h.title;
    div.onclick = () => showPage(h.page);
    tree.appendChild(div);
  });
  const refs = $('#refList');
  refs.innerHTML = '';
  (st.refs || []).forEach((r, i) => {
    const d = document.createElement('div');
    d.className = 'ref-item';
    d.id = `ref-${i + 1}`;
    d.dataset.n = i + 1;
    d.textContent = `[${i + 1}] ${(r.title || r.raw || '').slice(0, 90)}`;
    d.title = r.raw || '';
    d.onclick = () => highlightRef(i + 1, false);
    refs.appendChild(d);
  });
  $('#transList').innerHTML = '';
  showPage(1);
}

async function showPage(n) {
  const { pid } = state.reader;
  if (!pid) return;
  const data = await api(`/api/papers/${pid}/page/${n}`);
  state.reader.page = n;
  state.reader.total = data.total_pages;
  $('#pageIndicator').textContent = `${n} / ${data.total_pages}`;

  const wrap = $('#pageWrap');
  wrap.innerHTML = '';
  const img = new Image();
  img.src = data.image;
  img.style.width = '100%';
  wrap.style.maxWidth = '880px';
  await new Promise(r => { img.onload = r; img.onerror = r; });
  wrap.appendChild(img);

  const overlay = document.createElement('div');
  overlay.className = 'overlay';
  const scale = img.clientWidth / data.w || 1;
  wrap.style.position = 'relative';
  data.blocks.forEach(b => {
    const [x0, y0, x1, y1] = b.bbox;
    const div = document.createElement('div');
    div.className = 'blk';
    // 正文里的 [11] 变成可点：跳到参考文献条目，再一键返回原位置
    div.innerHTML = escapeHtml(b.text).replace(/\[(\d{1,3})\]/g,
      '<span class="cit" data-n="$1">[$1]</span>');
    div.style.left = (x0 * scale) + 'px';
    div.style.top = (y0 * scale) + 'px';
    div.style.width = ((x1 - x0) * scale) + 'px';
    div.style.height = ((y1 - y0) * scale) + 'px';
    div.style.fontSize = Math.max(6, b.size * scale * 0.98) + 'px';
    div.dataset.text = b.text;
    div.querySelectorAll('.cit').forEach(c => {
      c.onclick = ev => {
        ev.stopPropagation();
        highlightRef(Number(c.dataset.n), true);
      };
    });
    div.onclick = () => highlightTranslation(b.text);
    // 悬停翻译：已译过的段落悬停即出译文提示，不用选中
    div.onmouseenter = ev => {
      if (!state.reader.trans.size) return;
      const hit = Array.from(state.reader.trans.values()).find(i => (i.source || '').slice(0, 40) === b.text.slice(0, 40));
      if (!hit || !hit.text) return;
      const tip = $('#floatTip');
      tip.style.display = 'block';
      tip.style.left = Math.min(window.innerWidth - 440, ev.clientX || 200) + 'px';
      tip.style.top = ((ev.clientY || 200) + 16) + 'px';
      tip.textContent = hit.text;
      tip.dataset.hover = '1';
    };
    div.onmouseleave = () => {
      const tip = $('#floatTip');
      if (tip.dataset.hover) { tip.style.display = 'none'; tip.dataset.hover = ''; }
    };
    overlay.appendChild(div);
  });
  wrap.appendChild(overlay);

  overlay.onmouseup = () => {
    const sel = window.getSelection().toString().trim();
    if (sel.length > 2 && sel.length < 900) quickTranslate(sel);
  };
  renderTransPage(n);
}

$('#btnPrevPage').onclick = () => { if (state.reader.page > 1) showPage(state.reader.page - 1); };
$('#btnNextPage').onclick = () => { if (state.reader.page < state.reader.total) showPage(state.reader.page + 1); };
$('#btnBackFromRef').onclick = backToBody;
$('#chkCompare').onchange = setupCompare;
$('#btnExportMd').onclick = () => { if (state.reader.pid) window.open(`/api/papers/${state.reader.pid}/export?fmt=md`); };
$('#btnExportHtml').onclick = () => { if (state.reader.pid) window.open(`/api/papers/${state.reader.pid}/export?fmt=html`); };
$('#btnRefAudit').onclick = async () => {
  const pid = state.reader.pid;
  if (!pid) return;
  const box = $('#refAudit');
  box.textContent = '筛查中…';
  try {
    const r = await api('/api/refs/batch', {
      method: 'POST', headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ paper_id: pid, limit: 0, download: false }),
    });
    const doubt = (r.items || []).filter(i => i.verdict !== '保留').slice(0, 8);
    box.innerHTML = `共 ${r.total} 条；仅引用 1 次 ${r.cited_only_once} 条、未被正文引用 ${r.not_cited} 条` +
      (doubt.length ? '<br>' + doubt.map(i => `[${i.n}] ${escapeHtml(i.title.slice(0, 46))} — ${i.reason}`).join('<br>') : '');
  } catch (e) { box.textContent = '筛查失败：' + e.message; }
};

// 划词翻译
async function quickTranslate(text) {
  const tip = $('#floatTip');
  tip.dataset.hover = '';
  tip.style.display = 'block';
  tip.style.left = Math.min(window.innerWidth - 440, (window.event && window.event.clientX) || 200) + 'px';
  tip.style.top = ((window.event && window.event.clientY) || 200) + 14 + 'px';
  tip.textContent = '翻译中…';
  try {
    const r = await api('/api/translate', {
      method: 'POST', headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ text, target: 'zh' }),
    });
    tip.textContent = r.text || r.notice || '';
  } catch (e) { tip.textContent = '翻译失败：' + e.message; }
  setTimeout(() => { tip.style.display = 'none'; }, 12000);
}

$('#btnTranslatePage').onclick = () => translateRange(state.reader.page, state.reader.page);
$('#btnTranslateAll').onclick = async () => {
  const total = state.reader.total;
  for (let p = 1; p <= total; p += 5) {
    $('#transList').innerHTML = `<div class="hint">翻译中… ${p}/${total} 页</div>`;
    await translateRange(p, Math.min(p + 4, total));
  }
  renderTransPage(state.reader.page);
};

async function translateRange(from, to) {
  const { pid } = state.reader;
  const data = await api('/api/translate/range', {
    method: 'POST', headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ paper_id: pid, page_from: from, page_to: to }),
  });
  (data.items || []).forEach(it => state.reader.trans.set(it.chunk_id, it));
  renderTransPage(state.reader.page);
}

function renderTransPage(page) {
  const list = $('#transList');
  const items = Array.from(state.reader.trans.values()).filter(i => i.page === page);
  if (!items.length) {
    list.innerHTML = `<div class="hint">本页还没有译文，点「翻译本页」。</div>`;
    return;
  }
  list.innerHTML = items.map(i => `
    <div class="item" data-key="${escapeHtml((i.source || '').slice(0, 40))}">
      <div class="dst">${escapeHtml(i.text || '（未配置模型，暂无译文）')}</div>
      <div class="src">${escapeHtml((i.source || '').slice(0, 180))}</div>
    </div>`).join('');
}

function highlightTranslation(text) {
  const key = text.slice(0, 40);
  const el = $$('#transList .item').find(i => i.dataset.key === key);
  if (el) {
    $$('#transList .item').forEach(i => i.style.background = '');
    el.style.background = '#eaf1ff';
    el.scrollIntoView({ block: 'center', behavior: 'smooth' });
  }
}

// ---------- 正文 [n] ↔ 参考文献 双向跳转 ----------
// 点正文里的 [11]：滚到左侧参考文献第 11 条并高亮，同时记下当前页码与滚动位置
// 点「返回正文」：回到刚才那一页的同一位置
function highlightRef(n, fromBody) {
  const item = document.getElementById(`ref-${n}`);
  if (!item) return;
  if (fromBody) {
    if (!state.reader.backTo) {
      state.reader.backTo = { page: state.reader.page, top: $('#pagePane').scrollTop };
      const back = $('#btnBackFromRef');
      if (back) back.hidden = false;
    }
  }
  $$('#refList .ref-item').forEach(i => i.classList.remove('active'));
  item.classList.add('active');
  item.scrollIntoView({ block: 'center', behavior: 'smooth' });
}

function backToBody() {
  const b = state.reader.backTo;
  const back = $('#btnBackFromRef');
  if (back) back.hidden = true;
  state.reader.backTo = null;
  $$('#refList .ref-item').forEach(i => i.classList.remove('active'));
  if (!b) return;
  const go = () => { $('#pagePane').scrollTop = b.top || 0; };
  if (b.page !== state.reader.page) showPage(b.page).then(go);
  else go();
}

// ---------- 中英对照：左右联动 + 当前页自动译 ----------
function setupCompare() {
  const on = $('#chkCompare').checked;
  const left = $('#pagePane');
  const right = $('#transPane');
  document.body.classList.toggle('compare-on', on);
  if (!on) return;
  const ratio = el => el.scrollHeight > el.clientHeight ? el.scrollTop / (el.scrollHeight - el.clientHeight) : 0;
  const sync = (src, dst) => {
    if (state.reader.syncing) return;
    state.reader.syncing = true;
    dst.scrollTop = ratio(src) * Math.max(0, dst.scrollHeight - dst.clientHeight);
    setTimeout(() => { state.reader.syncing = false; }, 60);
  };
  left.onscroll = () => sync(left, right);
  right.onscroll = () => sync(right, left);
  const page = state.reader.page;
  const has = Array.from(state.reader.trans.values()).some(i => i.page === page);
  if (!has) translateRange(page, page);
}

// ---------- 问答 ----------
function renderQaChips() {
  const box = $('#qaPapers');
  box.innerHTML = state.papers.map(p =>
    `<span class="chip ${state.selected.has(p.id) ? 'on' : ''}" data-id="${p.id}">${escapeHtml((p.title || p.filename).slice(0, 46))}</span>`
  ).join('');
  $$('.chip', box).forEach(ch => ch.onclick = () => {
    const id = Number(ch.dataset.id);
    if (state.selected.has(id)) state.selected.delete(id); else state.selected.add(id);
    ch.classList.toggle('on');
  });
}

$('#btnAsk').onclick = async () => {
  const q = $('#qaQuestion').value.trim();
  if (!q) return;
  const out = $('#qaAnswer');
  out.hidden = false;
  out.textContent = '检索并生成中…';
  try {
    const data = await api('/api/ask', {
      method: 'POST', headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ question: q, paper_ids: Array.from(state.selected) }),
    });
    out.innerHTML = `<div>${escapeHtml(data.answer)}</div>` + (data.citations && data.citations.length ? `
      <div class="cites">${data.citations.map(c =>
        `<a href="#" data-pid="${c.paper_id}" data-page="${c.page}">[${c.n}] 《${escapeHtml(c.title)}》 第 ${c.page} 页 · ${escapeHtml(c.section)}</a>`
      ).join('')}</div>` : '');
    $$('.cites a', out).forEach(a => a.onclick = e => {
      e.preventDefault();
      openReader(Number(a.dataset.pid));
      setTimeout(() => showPage(Number(a.dataset.page)), 600);
    });
  } catch (e) { out.textContent = '失败：' + e.message; }
};

// ---------- 图谱 ----------
$('#btnBuildGraph').onclick = async () => {
  const data = await api('/api/graph', {
    method: 'POST', headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ paper_ids: Array.from(state.selected) }),
  });
  drawGraph(data);
  $('#coreList').innerHTML = data.core.map(id => {
    const n = data.nodes.find(x => x.id === id);
    return n ? `<li data-pid="${n.id}">${escapeHtml(n.title.slice(0, 44))}（被引 ${n.in}）</li>` : '';
  }).join('');
  $('#periphList').innerHTML = data.peripheral.map(id => {
    const n = data.nodes.find(x => x.id === id);
    return n ? `<li data-pid="${n.id}">${escapeHtml(n.title.slice(0, 44))}（引出 ${n.out}）</li>` : '';
  }).join('');
  $('#extList').innerHTML = data.external_top.map(([t, c]) => `<li>${escapeHtml(t.slice(0, 46))}（${c}）</li>`).join('');
  $$('.graph-side li').forEach(li => {
    if (li.dataset.pid) li.onclick = () => openReader(Number(li.dataset.pid));
  });
};

function drawGraph(data) {
  const svg = $('#graphSvg');
  const W = Math.max(760, Math.round(svg.clientWidth || 900) - 40);
  const H = 560;
  const nodes = data.nodes.map((n, i) => ({
    ...n,
    x: W / 2 + Math.cos(i / data.nodes.length * 6.28) * 220,
    y: H / 2 + Math.sin(i / data.nodes.length * 6.28) * 180,
    vx: 0, vy: 0,
  }));
  const byId = Object.fromEntries(nodes.map(n => [n.id, n]));
  for (let iter = 0; iter < 220; iter++) {
    nodes.forEach(a => {
      a.vx += (W / 2 - a.x) * 0.0009;
      a.vy += (H / 2 - a.y) * 0.0009;
      nodes.forEach(b => {
        if (a === b) return;
        let dx = a.x - b.x, dy = a.y - b.y;
        let d2 = dx * dx + dy * dy + 0.01;
        const f = 90000 / d2;
        a.vx += dx * f / Math.sqrt(d2);
        a.vy += dy * f / Math.sqrt(d2);
      });
    });
    data.edges.forEach(e => {
      const a = byId[e.source], b = byId[e.target];
      if (!a || !b) return;
      const dx = b.x - a.x, dy = b.y - a.y;
      const d = Math.sqrt(dx * dx + dy * dy) + 0.01;
      const f = (d - 190) * 0.005;
      a.vx += dx / d * f; a.vy += dy / d * f;
      b.vx -= dx / d * f; b.vy -= dy / d * f;
    });
    nodes.forEach(n => { n.x += n.vx; n.y += n.vy; n.vx *= 0.55; n.vy *= 0.55;
      n.x = Math.max(60, Math.min(W - 60, n.x)); n.y = Math.max(40, Math.min(H - 40, n.y)); });
  }

  const color = n => n.role === '基石' ? '#2f6fed' : n.role === '边缘' ? '#c0c6d4' : '#8f9ab0';
  let out = `<defs><marker id="ar" markerWidth="8" markerHeight="8" refX="7" refY="3" orient="auto">
      <path d="M0,0 L7,3 L0,6" fill="#b9c2d4"/></marker></defs>`;
  data.edges.forEach(e => {
    const a = byId[e.source], b = byId[e.target];
    if (!a || !b) return;
    out += `<line x1="${a.x}" y1="${a.y}" x2="${b.x}" y2="${b.y}" stroke="#dfe4ee" stroke-width="1.2" marker-end="url(#ar)"/>`;
  });
  nodes.forEach(n => {
    const r = 7 + Math.min(n.in, 8) * 1.6;
    out += `<g data-pid="${n.id}"><circle cx="${n.x}" cy="${n.y}" r="${r}" fill="${color(n)}" opacity=".9"/>`;
    out += `<text x="${n.x + r + 3}" y="${n.y + 4}" font-size="11" fill="#39425280">${escapeHtml(n.title.slice(0, 26))}</text></g>`;
  });
  svg.innerHTML = out;
  $$('g', svg).forEach(g => g.style.cursor = 'pointer');
  $$('g', svg).forEach(g => g.onclick = () => openReader(Number(g.dataset.pid)));
}

$('#btnSurvey').onclick = () => runAnalysis('/api/survey');
$('#btnFuture').onclick = () => runAnalysis('/api/futurework');
async function runAnalysis(path) {
  const out = $('#analysisOut');
  out.hidden = false;
  out.textContent = '生成中…';
  try {
    const data = await api(path, {
      method: 'POST', headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ paper_ids: Array.from(state.selected) }),
    });
    out.textContent = data.text;
  } catch (e) { out.textContent = '失败：' + e.message; }
}

// ---------- 写作 ----------
$('#btnOutline').onclick = async () => {
  const idea = $('#ideaBox').value.trim();
  if (!idea) return;
  const out = $('#outlineOut');
  out.hidden = false; out.textContent = '生成中…';
  try {
    const data = await api('/api/write/outline', {
      method: 'POST', headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ idea, paper_ids: Array.from(state.selected) }),
    });
    out.textContent = data.text;
  } catch (e) { out.textContent = '失败：' + e.message; }
};

$('#btnDiagram').onclick = async () => {
  const desc = $('#diagramDesc').value.trim();
  if (!desc) return;
  $('#diagramOut').textContent = '生成中…';
  try {
    const data = await api('/api/write/diagram', {
      method: 'POST', headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ desc }),
    });
    $('#diagramOut').textContent = data.text;
  } catch (e) { $('#diagramOut').textContent = '失败：' + e.message; }
};

$('#btnPlot').onclick = async () => {
  const file = $('#csvInput').files[0];
  if (!file) { alert('请先选择 CSV'); return; }
  const fd = new FormData();
  fd.append('file', file);
  fd.append('desc', $('#plotDesc').value || '');
  fd.append('kind', $('#plotKind').value);
  $('#plotOut').innerHTML = '绘图…';
  try {
    const data = await api('/api/plot', { method: 'POST', body: fd });
    $('#plotOut').innerHTML = `<img src="${data.image}" />
      <div class="hint">${escapeHtml(data.caption || '')}</div>
      <div class="hint">${escapeHtml(data.caption_zh || '')}</div>
      <div class="hint">${escapeHtml(data.stats || '')}</div>`;
  } catch (e) { $('#plotOut').textContent = '失败：' + e.message; }
};

// ---------- 推荐 ----------
$('#btnRecommend').onclick = async () => {
  $('#recList').textContent = '抓取 arXiv 中…（首次较慢）';
  try {
    const data = await api('/api/recommend', {
      method: 'POST', headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ limit: 8 }),
    });
    $('#recList').innerHTML = (data.items || []).map(it => `
      <div class="rec">
        <h4>${escapeHtml(it.title)}</h4>
        <p>${escapeHtml(it.published)} · ${it.has_code ? '含开源代码' : '无代码链接'} · 相关度 ${it.score}</p>
        <p>${escapeHtml((it.summary || '').slice(0, 260))}…</p>
        <p><b>推荐理由：</b>${escapeHtml(it.reason)}</p>
        <div class="actions">
          <button data-act="dl" data-id="${it.arxiv_id}">下载入库</button>
          <button class="ghost" data-act="like" data-id="${it.arxiv_id}">有用</button>
          <button class="ghost" data-act="dislike" data-id="${it.arxiv_id}">不相关</button>
        </div>
      </div>`).join('') || '<div class="hint">没有找到新论文，先往文库里加几篇。</div>';
    $$('.rec-list button').forEach(b => b.onclick = async () => {
      const id = b.dataset.id;
      if (b.dataset.act === 'dl') {
        b.disabled = true; b.textContent = '下载中…';
        await api('/api/ingest/arxiv', {
          method: 'POST', headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ ids: [id] }),
        });
        b.textContent = '已入库';
        loadLibrary();
      } else {
        await api('/api/feedback', {
          method: 'POST', headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ arxiv_id: id, verdict: b.dataset.act }),
        });
        b.textContent = b.dataset.act === 'like' ? '已标记有用' : '已标记不相关';
      }
    });
  } catch (e) { $('#recList').textContent = '失败：' + e.message; }
};

// 启动
loadLibrary();
loadReaderSelect().catch(() => {});
