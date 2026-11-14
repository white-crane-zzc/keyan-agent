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
  // 逐个上传：每传完一个就把结果写进日志，长文档解析时也能看到进度，不会停在「上传中」没反应
  const files = Array.from(fileList);
  const lines = [];
  const flush = extra => { $('#uploadLog').textContent = lines.concat(extra ? [extra] : []).join('\n'); };
  for (let i = 0; i < files.length; i++) {
    flush(`⏳ 正在处理 ${i + 1}/${files.length}：${files[i].name}（大文档解析需要时间，请稍候）`);
    const fd = new FormData();
    fd.append('files', files[i]);
    fd.append('on_duplicate', 'ask');
    try {
      const data = await api('/api/upload', { method: 'POST', body: fd });
      for (const r of data.results) {
        if (r.status === 'ingested') lines.push(`✅ ${r.name}：${r.meta.title}（${r.meta.n_pages} 页，${r.meta.n_refs} 篇参考文献）`);
        else if (r.status === 'duplicate') lines.push(await askDuplicate(r));
        else lines.push(`❌ ${r.name}：${r.message}`);
      }
    } catch (e) {
      lines.push(`❌ ${files[i].name}：上传失败（${e.message}）`);
    }
    flush();
  }
  loadLibrary();
}

// 重复文件处理：展示差异，让用户选保留哪版
function askDuplicate(r) {
  return new Promise(resolve => {
    const diff = r.diff || {};
    const lines = [
      r.exact
        ? `库里已有一份内容完全相同的 PDF：《${r.existing.title}》`
        : `检测到同一篇论文的另一版：《${r.existing.title}》（相似度 ${(r.similarity * 100).toFixed(0)}%）`,
      `库里已有：${r.existing.meta.n_pages} 页 / ${r.existing.meta.n_chars} 字符 / ${r.existing.meta.n_refs} 篇参考文献`,
    ];
    if (!r.exact) {
      lines.push(`新上传：${r.incoming_meta.n_pages} 页 / ${r.incoming_meta.n_chars} 字符 / ${r.incoming_meta.n_refs} 篇参考文献`);
      lines.push(`章节新增：${(diff.sections_added || []).join('、') || '无'}`);
      lines.push(`章节删除：${(diff.sections_removed || []).join('、') || '无'}`);
    } else {
      lines.push(`新上传：${r.incoming_meta.n_pages} 页（同名文件，内容一致）`);
    }
    lines.push(`结论：${r.suggestion}`, '',
      '确定 = 用新上传的这份替换库里旧版（旧版删除）',
      '取消 = 两个都保留（并存，自动改名不覆盖）');
    const msg = lines.join('\n');
    const useNew = confirm(msg);
    const action = useNew ? 'keep_new' : 'keep_both';
    api('/api/upload/confirm', {
      method: 'POST', headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ staged: r.staged, name: r.existing.filename, action, existing_id: r.existing.id }),
    }).then(res => resolve(`↻ ${r.existing.title}：${useNew ? '已替换为上传的新版' : `已并存（${res.name || '两个版本都保留'}）`}`))
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
  $('#graphNote').textContent = data.note || `当前图谱：${data.nodes.length} 篇 / ${data.edges.length} 条引用边`;
  const coreBox = $('#coreList');
  coreBox.innerHTML = data.core.length ? data.core.map(id => {
    const n = data.nodes.find(x => x.id === id);
    return n ? `<li data-pid="${n.id}">${escapeHtml(n.title.slice(0, 44))}（被引 ${n.in}）</li>` : '';
  }).join('') : '<li class="hint">没有能判定的基石论文：选中的论文之间没有互相引用</li>';
  $('#periphList').innerHTML = data.peripheral.length ? data.peripheral.map(id => {
    const n = data.nodes.find(x => x.id === id);
    return n ? `<li data-pid="${n.id}">${escapeHtml(n.title.slice(0, 44))}（引出 ${n.out}）</li>` : '';
  }).join('') : '<li class="hint">没有边缘论文</li>';
  $('#extList').innerHTML = data.external_top.map(([t, c]) => `<li>${escapeHtml(t.slice(0, 46))}（${c}）</li>`).join('');
  $$('.graph-side li').forEach(li => {
    if (li.dataset.pid) li.onclick = () => openReader(Number(li.dataset.pid));
  });
};

function drawGraph(data) {
  const svg = $('#graphSvg');
  const W = Math.max(760, Math.round(svg.clientWidth || 900) - 40);
  const H = 620;
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
        const f = 150000 / d2;
        a.vx += dx * f / Math.sqrt(d2);
        a.vy += dy * f / Math.sqrt(d2);
      });
    });
    data.edges.forEach(e => {
      const a = byId[e.source], b = byId[e.target];
      if (!a || !b) return;
      const dx = b.x - a.x, dy = b.y - a.y;
      const d = Math.sqrt(dx * dx + dy * dy) + 0.01;
      const f = (d - 230) * 0.005;
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
  const showAllLabels = data.nodes.length <= 12;
  nodes.forEach((n, i) => {
    const r = 7 + Math.min(n.in, 8) * 1.6;
    // 节点多时只标基石/边缘，其余靠悬停看全名，避免标签糊成一片
    const labelled = showAllLabels || n.role !== '中间';
    const label = n.title.length > 16 ? n.title.slice(0, 16) + '…' : n.title;
    const est = label.length * 5.4;
    let left = n.x > W / 2;
    if (!left && n.x + r + 6 + est > W - 6) left = true;
    if (left && n.x - r - 6 - est < 6) left = false;
    const tx = left ? n.x - r - 4 : n.x + r + 4;
    const anchor = left ? 'end' : 'start';
    out += `<g data-pid="${n.id}"><title>${escapeHtml(n.title)}（被引 ${n.in} / 引出 ${n.out}）</title>`;
    out += `<circle cx="${n.x}" cy="${n.y}" r="${r}" fill="${color(n)}" opacity=".9"/>`;
    if (labelled) {
      out += `<text x="${tx}" y="${n.y + 4}" text-anchor="${anchor}" font-size="10" fill="#39425290">${escapeHtml(label)}</text>`;
    }
    out += `</g>`;
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

// 把 mermaid 的 flowchart 源码就地画成 SVG（离线，不依赖 CDN）
function renderFlowchart(src, host) {
  const nodes = new Map();
  const edges = [];
  let dir = 'TD';
  const shape = /^([A-Za-z0-9_\u4e00-\u9fff]+)\s*(?:\[([^\]]*)\]|\(([^)]*)\)|\{([^}]*)\})?$/;
  const addNode = (tok) => {
    const m = tok.match(shape);
    if (!m) return null;
    const id = m[1];
    const label = (m[2] || m[3] || m[4] || id).replace(/["']/g, '').trim();
    if (!nodes.has(id)) nodes.set(id, label);
    return id;
  };
  for (const raw of src.split('\n')) {
    const line = raw.trim();
    if (!line) continue;
    const dm = line.match(/^(?:flowchart|graph)\s+(TD|TB|LR|RL|BT)/i);
    if (dm) { dir = dm[1].toUpperCase(); continue; }
    if (/^(%%|classDef|class |style |linkStyle|subgraph|end\b|click\s)/i.test(line)) continue;
    const parts = line.split(/\s*(?:-->|==>|-.->)\s*(?:\|[^|]*\|)?/).map(s => s.trim()).filter(Boolean);
    if (!parts.length) continue;
    const ids = parts.map(addNode);
    if (ids.some(x => !x)) continue;
    for (let i = 0; i + 1 < ids.length; i++) edges.push([ids[i], ids[i + 1]]);
  }
  if (!nodes.size) { host.innerHTML = ''; return false; }

  const indeg = new Map([...nodes.keys()].map(k => [k, 0]));
  edges.forEach(([, t]) => indeg.set(t, (indeg.get(t) || 0) + 1));
  const layer = new Map();
  const roots = [...nodes.keys()].filter(k => !indeg.get(k));
  (roots.length ? roots : [[...nodes.keys()][0]]).forEach(r => layer.set(r, 0));
  for (let it = 0; it < nodes.size + 2; it++) {
    let changed = false;
    edges.forEach(([s, t]) => {
      if (layer.has(s) && (!layer.has(t) || layer.get(t) < layer.get(s) + 1)) {
        layer.set(t, layer.get(s) + 1); changed = true;
      }
    });
    if (!changed) break;
  }
  const layers = [];
  nodes.forEach((label, id) => {
    const d = layer.has(id) ? layer.get(id) : 0;
    (layers[d] = layers[d] || []).push([id, label]);
  });

  const bh = 40, gapCross = 26, gapDepth = 78, pad = 18;
  const sizes = new Map([...nodes].map(([id, label]) => [id, [Math.min(190, Math.max(96, label.length * 14 + 26)), bh]]));
  const cross = dir === 'LR' || dir === 'RL';
  const pos = new Map();
  let maxCross = 0, maxDepth = 0;
  layers.forEach((items, d) => {
    const total = items.reduce((s, [id]) => s + sizes.get(id)[cross ? 1 : 0] + gapCross, -gapCross);
    let acc = -total / 2;
    maxCross = Math.max(maxCross, total);
    maxDepth = Math.max(maxDepth, d);
    items.forEach(([id]) => {
      const [w, h] = sizes.get(id);
      const c = cross ? h : w;
      pos.set(id, cross ? [d * (190 + gapDepth), acc + c / 2] : [acc + c / 2, d * (bh + gapDepth)]);
      acc += c + gapCross;
    });
  });
  // 布局坐标是以中心为原点的，先算真实包围盒再平移，否则左半边会被 viewBox 裁掉
  let minX = Infinity, minY = Infinity, maxX = -Infinity, maxY = -Infinity;
  nodes.forEach((label, id) => {
    const [x, y] = pos.get(id);
    const [w, h] = sizes.get(id);
    minX = Math.min(minX, x - w / 2); maxX = Math.max(maxX, x + w / 2);
    minY = Math.min(minY, y - h / 2); maxY = Math.max(maxY, y + h / 2);
  });
  const W = maxX - minX + pad * 2;
  const H = maxY - minY + pad * 2;

  let out = `<defs><marker id="dar" markerWidth="9" markerHeight="9" refX="8" refY="3.5" orient="auto">
    <path d="M0,0 L8,3.5 L0,7" fill="#7f92b8"/></marker></defs>`;
  edges.forEach(([s, t]) => {
    const a = pos.get(s), b = pos.get(t);
    if (!a || !b) return;
    const [aw, ah] = sizes.get(s), [bw, bh2] = sizes.get(t);
    let x1, y1, x2, y2;
    if (cross) {
      const sgn = dir === 'LR' ? 1 : -1;
      x1 = a[0] + sgn * aw / 2; y1 = a[1];
      x2 = b[0] - sgn * bw / 2; y2 = b[1];
    } else {
      const sgn = dir === 'BT' ? -1 : 1;
      x1 = a[0]; y1 = a[1] + sgn * ah / 2;
      x2 = b[0]; y2 = b[1] - sgn * bh2 / 2;
    }
    out += `<line x1="${x1}" y1="${y1}" x2="${x2}" y2="${y2}" stroke="#9aa8c4" stroke-width="1.4" marker-end="url(#dar)"/>`;
  });
  nodes.forEach((label, id) => {
    const [x, y] = pos.get(id);
    const [w, h] = sizes.get(id);
    const shown = label.length > 18 ? label.slice(0, 18) + '…' : label;
    out += `<g><title>${escapeHtml(label)}</title>
      <rect x="${x - w / 2}" y="${y - h / 2}" width="${w}" height="${h}" rx="9" fill="#f2f5fd" stroke="#5b8def"/>
      <text x="${x}" y="${y + 5}" text-anchor="middle" font-size="12.5" fill="#243043">${escapeHtml(shown)}</text></g>`;
  });
  const dx = pad - minX, dy = pad - minY;
  host.innerHTML = `<svg width="${W.toFixed(0)}" height="${H.toFixed(0)}" viewBox="0 0 ${W.toFixed(0)} ${H.toFixed(0)}" preserveAspectRatio="xMidYMid meet"><g transform="translate(${dx.toFixed(1)},${dy.toFixed(1)})">${out}</g></svg>`;
  return true;
}

$('#btnDiagram').onclick = async () => {
  const desc = $('#diagramDesc').value.trim();
  if (!desc) return;
  const kind = $('#diagramKind').value;
  const prev = $('#diagramPreview');
  $('#diagramOut').textContent = '生成中…';
  prev.innerHTML = '';
  try {
    const data = await api('/api/write/diagram', {
      method: 'POST', headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ desc, kind }),
    });
    $('#diagramOut').textContent = data.text;
    if (kind === 'mermaid') {
      const body = (data.text || '').replace(/```[a-z]*/gi, '').trim();
      if (!renderFlowchart(body, prev)) {
        $('#diagramOut').textContent = (data.text || '') + '\n\n（这段 Mermaid 没解析成框图，可直接复制到 mermaid.live 渲染）';
      }
    }
  } catch (e) { $('#diagramOut').textContent = '失败：' + e.message; }
};

$('#btnSampleCsv').onclick = () => {
  const csv = '模型,BLEU,参数量（M）\nTransformer,29.5,65\nBERT,31.0,110\nGPT-2,29.0,1542\n';
  const a = document.createElement('a');
  a.href = URL.createObjectURL(new Blob([csv], { type: 'text/csv' }));
  a.download = '示例数据.csv';
  a.click();
  URL.revokeObjectURL(a.href);
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
    const clean = s => (s || '').replace(/\*\*/g, '').replace(/^(?:English\s+)?Figure caption:\s*/i, '').replace(/^中文图注[:：]\s*/, '');
    $('#plotOut').innerHTML = `<img src="${data.image}" />
      <div class="hint">${escapeHtml(clean(data.caption))}</div>
      <div class="hint">${escapeHtml(clean(data.caption_zh))}</div>
      <div class="hint">${escapeHtml(clean(data.stats))}</div>
      <div class="hint">图片已存 ${escapeHtml(data.image)}</div>`;
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
