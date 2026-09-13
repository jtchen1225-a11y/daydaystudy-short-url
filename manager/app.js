const state = {
  links: [],
  baseUrl: 'https://go.daydaystudy.top',
  dirty: false,
  qrAvailable: true,
};

const $ = (id) => document.getElementById(id);
const body = $('linksBody');

function setStatus(text, type='') {
  const el = $('saveStatus');
  el.textContent = text;
  el.className = `status ${type}`.trim();
}

function markDirty() {
  state.dirty = true;
  setStatus('有未儲存修改', 'dirty');
}

function escapeHtml(s='') {
  return String(s).replace(/[&<>'"]/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;',"'":'&#39;','"':'&quot;'}[c]));
}

function slugify(text='') {
  return String(text)
    .trim()
    .toLowerCase()
    .replace(/^https?:\/\//, '')
    .replace(/[^a-z0-9/_-]+/g, '-')
    .replace(/-+/g, '-')
    .replace(/^[-_/]+|[-_/]+$/g, '');
}

function autoCodeFromUrl(url) {
  try {
    const u = new URL(url);
    const parts = u.pathname.split('/').filter(Boolean);
    let candidate = parts.length ? parts[parts.length - 1] : u.hostname.split('.')[0];
    candidate = slugify(candidate) || 'link';
    return uniqueCode(candidate);
  } catch {
    return uniqueCode('link');
  }
}

function uniqueCode(base, excludeIndex=-1) {
  base = slugify(base) || 'link';
  const used = new Set(state.links.map((r,i) => i === excludeIndex ? '' : String(r.short_code || '').toLowerCase()));
  if (!used.has(base)) return base;
  let n = 2;
  while (used.has(`${base}-${n}`)) n++;
  return `${base}-${n}`;
}

function normalizedUrl(url) {
  try {
    const u = new URL(String(url).trim());
    u.hash = '';
    return u.toString().replace(/\/$/, '');
  } catch { return String(url || '').trim(); }
}

function validate() {
  const codeCounts = new Map();
  const urlCounts = new Map();
  const errors = new Map();
  const warnings = new Map();
  const codePattern = /^[a-z0-9](?:[a-z0-9/_-]*[a-z0-9])?$/;
  const reserved = new Set(['index','404','assets','admin','manager']);

  state.links.forEach((r, i) => {
    const code = String(r.short_code || '').trim().toLowerCase();
    const url = normalizedUrl(r.target_url);
    codeCounts.set(code, (codeCounts.get(code) || 0) + 1);
    if (url) urlCounts.set(url, (urlCounts.get(url) || 0) + 1);
    const e = [];
    if (!code) e.push('short code 不可留空');
    else if (!codePattern.test(code) || code.includes('..')) e.push('short code 格式不正確');
    else if (reserved.has(code)) e.push('short code 是保留名稱');
    try {
      const u = new URL(r.target_url);
      if (!['http:','https:'].includes(u.protocol)) throw new Error();
    } catch { e.push('Target URL 必須是完整 http/https 網址'); }
    if (e.length) errors.set(i, e);
  });

  state.links.forEach((r, i) => {
    const code = String(r.short_code || '').trim().toLowerCase();
    const url = normalizedUrl(r.target_url);
    if (code && codeCounts.get(code) > 1) {
      const e = errors.get(i) || [];
      e.push('short code 重複');
      errors.set(i, e);
    }
    if (url && urlCounts.get(url) > 1) warnings.set(i, ['目標網址重複']);
  });
  return { errors, warnings };
}

function render() {
  const query = $('searchInput').value.trim().toLowerCase();
  const { errors, warnings } = validate();
  body.innerHTML = '';
  state.links.forEach((row, index) => {
    const hay = `${row.short_code} ${row.target_url} ${row.title}`.toLowerCase();
    if (query && !hay.includes(query)) return;
    const tr = document.createElement('tr');
    if (errors.has(index)) tr.classList.add('row-error');
    else if (warnings.has(index)) tr.classList.add('row-warning');
    const shortUrl = `${state.baseUrl.replace(/\/$/,'')}/${row.short_code || ''}`;
    tr.innerHTML = `
      <td class="col-enabled"><input type="checkbox" data-field="enabled" data-index="${index}" ${row.enabled ? 'checked' : ''}></td>
      <td><input type="text" data-field="short_code" data-index="${index}" value="${escapeHtml(row.short_code)}" spellcheck="false"></td>
      <td><input type="url" data-field="target_url" data-index="${index}" value="${escapeHtml(row.target_url)}" spellcheck="false"></td>
      <td><input type="text" data-field="title" data-index="${index}" value="${escapeHtml(row.title)}"></td>
      <td><a class="preview-link" href="${escapeHtml(shortUrl)}" target="_blank" rel="noopener">${escapeHtml(shortUrl)}</a></td>
      <td><div class="actions">
        <button class="secondary" data-action="auto" data-index="${index}">Auto</button>
        <button class="secondary" data-action="qr" data-index="${index}">QR</button>
        <button class="danger" data-action="delete" data-index="${index}">刪除</button>
      </div></td>`;
    body.appendChild(tr);
  });
  $('rowCount').textContent = state.links.length;
  const summary = $('validationSummary');
  if (errors.size) {
    summary.className = 'message error';
    summary.textContent = `有 ${errors.size} 列需要修正，儲存前請先處理紅色列。`;
  } else if (warnings.size) {
    summary.className = 'message warn';
    summary.textContent = `有 ${warnings.size} 列使用重複的目標網址；可保留，但請確認是否刻意設定。`;
  } else {
    summary.className = 'message ok';
    summary.textContent = `檢查完成：${state.links.length} 筆資料沒有 short code 衝突。`;
  }
}

async function loadAll() {
  try {
    const [linksResp, configResp] = await Promise.all([fetch('/api/links'), fetch('/api/config')]);
    const linksData = await linksResp.json();
    const configData = await configResp.json();
    state.links = linksData.links || [];
    state.baseUrl = configData.base_url || state.baseUrl;
    state.qrAvailable = configData.qr_available !== false;
    $('baseUrl').value = state.baseUrl;
    state.dirty = false;
    setStatus('已載入 links.csv', 'saved');
    render();
  } catch (e) {
    setStatus('載入失敗', 'error');
    alert(`載入失敗：${e.message}`);
  }
}

function parseBatchLine(line) {
  const parts = line.split('\t').map(s => s.trim()).filter((s,i,a) => !(s === '' && i === a.length - 1));
  if (!parts.length) return null;
  if (parts.length === 1) return { url: parts[0], title: '' };
  if (parts.length === 2) {
    if (/^https?:\/\//i.test(parts[0])) return { url: parts[0], title: parts[1] };
    if (/^https?:\/\//i.test(parts[1])) return { url: parts[1], title: parts[0] };
    return { url: parts[0], title: parts[1] };
  }
  const urlIndex = parts.findIndex(p => /^https?:\/\//i.test(p));
  if (urlIndex === 1) return { code: parts[0], url: parts[1], title: parts.slice(2).join(' ') };
  if (urlIndex === 0) return { url: parts[0], title: parts.slice(1).join(' ') };
  return { code: parts[0], url: parts[1], title: parts.slice(2).join(' ') };
}

function batchAdd() {
  const lines = $('batchInput').value.split(/\r?\n/).map(s => s.trim()).filter(Boolean);
  const skipDup = $('skipDuplicateTarget').checked;
  let added = 0, skipped = 0, invalid = 0;
  for (const line of lines) {
    const parsed = parseBatchLine(line);
    if (!parsed) continue;
    try {
      const u = new URL(parsed.url);
      if (!['http:','https:'].includes(u.protocol)) throw new Error();
    } catch { invalid++; continue; }
    const nurl = normalizedUrl(parsed.url);
    if (skipDup && state.links.some(r => normalizedUrl(r.target_url) === nurl)) { skipped++; continue; }
    let code = parsed.code ? uniqueCode(parsed.code) : autoCodeFromUrl(parsed.url);
    state.links.push({ short_code: code, target_url: parsed.url, title: parsed.title || code, enabled: true });
    added++;
  }
  if (added) markDirty();
  render();
  const msg = $('batchResult');
  msg.className = `message ${invalid ? 'warn' : 'ok'}`;
  msg.textContent = `已加入 ${added} 筆；略過重複 ${skipped} 筆；無效 ${invalid} 筆。`;
}

function csvEscape(value) {
  const s = String(value ?? '');
  return /[",\r\n]/.test(s) ? `"${s.replace(/"/g,'""')}"` : s;
}

function exportCsv() {
  const rows = [['short_code','target_url','title','enabled'], ...state.links.map(r => [r.short_code,r.target_url,r.title,r.enabled ? '1':'0'])];
  const text = '\uFEFF' + rows.map(r => r.map(csvEscape).join(',')).join('\r\n');
  const blob = new Blob([text], {type:'text/csv;charset=utf-8'});
  const a = document.createElement('a');
  a.href = URL.createObjectURL(blob);
  a.download = 'links.csv';
  a.click();
  URL.revokeObjectURL(a.href);
}

function parseCsv(text) {
  text = text.replace(/^\uFEFF/, '');
  const rows = [];
  let row = [], field = '', quoted = false;
  for (let i=0; i<text.length; i++) {
    const c = text[i];
    if (quoted) {
      if (c === '"' && text[i+1] === '"') { field += '"'; i++; }
      else if (c === '"') quoted = false;
      else field += c;
    } else {
      if (c === '"') quoted = true;
      else if (c === ',') { row.push(field); field=''; }
      else if (c === '\n') { row.push(field.replace(/\r$/,'')); rows.push(row); row=[]; field=''; }
      else field += c;
    }
  }
  if (field.length || row.length) { row.push(field.replace(/\r$/,'')); rows.push(row); }
  return rows;
}

async function importCsv(file) {
  const text = await file.text();
  const rows = parseCsv(text).filter(r => r.some(v => String(v).trim() !== ''));
  if (!rows.length) throw new Error('CSV 是空的');
  const headers = rows[0].map(h => h.trim());
  const required = ['short_code','target_url','title','enabled'];
  if (!required.every(h => headers.includes(h))) throw new Error('CSV 必須包含 short_code,target_url,title,enabled 四欄');
  const imported = rows.slice(1).map(cols => {
    const obj = {};
    headers.forEach((h,i) => obj[h] = cols[i] ?? '');
    return {
      short_code: obj.short_code.trim(),
      target_url: obj.target_url.trim(),
      title: obj.title.trim(),
      enabled: !['0','false','no','off',''].includes(obj.enabled.trim().toLowerCase()),
    };
  });
  if (!confirm(`將以匯入的 ${imported.length} 筆資料取代目前清單，是否繼續？`)) return;
  state.links = imported;
  markDirty();
  render();
}

async function saveLinks() {
  const { errors } = validate();
  if (errors.size) {
    render();
    alert('仍有資料錯誤，請先修正紅色列。');
    return;
  }
  setStatus('正在儲存…', 'dirty');
  const resp = await fetch('/api/save', {
    method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify({links:state.links})
  });
  const data = await resp.json();
  if (!resp.ok) { setStatus('儲存失敗', 'error'); throw new Error(data.error || '儲存失敗'); }
  state.dirty = false;
  setStatus(`已儲存 ${data.count} 筆`, 'saved');
  render();
}

async function saveConfig() {
  const base = $('baseUrl').value.trim().replace(/\/$/,'');
  const resp = await fetch('/api/config', {method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify({base_url:base})});
  const data = await resp.json();
  if (!resp.ok) throw new Error(data.error || '儲存網域失敗');
  state.baseUrl = data.base_url;
  $('baseUrl').value = state.baseUrl;
  render();
  setStatus('短網域已更新', 'saved');
}

function showQr(index) {
  const row = state.links[index];
  if (!row?.short_code) return;
  const url = `${state.baseUrl.replace(/\/$/,'')}/${row.short_code}`;
  $('qrTitle').textContent = row.title || row.short_code;
  $('qrUrl').textContent = url;
  const src = `/api/qr?code=${encodeURIComponent(row.short_code)}&t=${Date.now()}`;
  $('qrImage').src = src;
  $('qrDownload').href = src;
  $('qrDownload').download = `${row.short_code.replaceAll('/','__')}.png`;
  $('qrDialog').showModal();
}

async function downloadAllQr() {
  const validCodes = state.links.filter(r => r.enabled && r.short_code).map(r => r.short_code);
  if (!validCodes.length) return alert('沒有可下載的啟用短網址。');
  const resp = await fetch('/api/qr-zip', {method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify({codes:validCodes})});
  if (!resp.ok) {
    const data = await resp.json().catch(()=>({}));
    throw new Error(data.error || 'QR ZIP 產生失敗');
  }
  const blob = await resp.blob();
  const a = document.createElement('a');
  a.href = URL.createObjectURL(blob);
  a.download = 'daydaystudy-qr-codes.zip';
  a.click();
  URL.revokeObjectURL(a.href);
}

body.addEventListener('input', e => {
  const idx = Number(e.target.dataset.index);
  const field = e.target.dataset.field;
  if (!Number.isInteger(idx) || !field) return;
  state.links[idx][field] = field === 'enabled' ? e.target.checked : e.target.value;
  markDirty();
});
body.addEventListener('change', e => {
  const idx = Number(e.target.dataset.index);
  const field = e.target.dataset.field;
  if (!Number.isInteger(idx) || !field) return;
  state.links[idx][field] = field === 'enabled' ? e.target.checked : e.target.value;
  if (field === 'short_code') state.links[idx][field] = String(state.links[idx][field]).toLowerCase();
  markDirty();
  render();
});
body.addEventListener('click', e => {
  const btn = e.target.closest('button[data-action]');
  if (!btn) return;
  const idx = Number(btn.dataset.index);
  if (btn.dataset.action === 'delete') {
    if (confirm(`刪除 ${state.links[idx]?.short_code || '這一列'}？`)) {
      state.links.splice(idx,1); markDirty(); render();
    }
  } else if (btn.dataset.action === 'auto') {
    const row = state.links[idx];
    row.short_code = autoCodeFromUrl(row.target_url);
    if (!row.title) row.title = row.short_code;
    markDirty(); render();
  } else if (btn.dataset.action === 'qr') showQr(idx);
});

$('batchAddBtn').addEventListener('click', batchAdd);
$('clearBatchBtn').addEventListener('click', () => { $('batchInput').value=''; $('batchResult').className='message hidden'; });
$('addRowBtn').addEventListener('click', () => { state.links.push({short_code:uniqueCode('link'),target_url:'https://',title:'',enabled:true}); markDirty(); render(); });
$('exportBtn').addEventListener('click', exportCsv);
$('importBtn').addEventListener('click', () => $('csvFile').click());
$('csvFile').addEventListener('change', async e => { try { if (e.target.files[0]) await importCsv(e.target.files[0]); } catch(err) { alert(err.message); } e.target.value=''; });
$('saveBtn').addEventListener('click', () => saveLinks().catch(e => alert(e.message)));
$('saveConfigBtn').addEventListener('click', () => saveConfig().catch(e => alert(e.message)));
$('qrZipBtn').addEventListener('click', () => downloadAllQr().catch(e => alert(e.message)));
$('searchInput').addEventListener('input', render);
$('clearSearchBtn').addEventListener('click', () => { $('searchInput').value=''; render(); });
window.addEventListener('beforeunload', e => { if (state.dirty) { e.preventDefault(); e.returnValue=''; } });

loadAll();
