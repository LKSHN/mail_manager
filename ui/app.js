// ─── MAIL MANAGER — FRONTEND ──────────────────────────────────────────────────
// All calls to Python use:  await window.pywebview.api.method(args)
// Every Python method returns { ok: bool, ...payload } or { ok: false, error }

'use strict';

// ══════════════════════════════════════════════════════════════════════════════
// STATE
// ══════════════════════════════════════════════════════════════════════════════
const State = {
  query:        'in:inbox',
  messages:     [],
  labels:       [],          // [{id, name}]
  currentMid:   null,
  currentThread:null,
  ctxMid:       null,        // mid targeted by right-click
  replyData:    null,        // { to, subject, threadId } when replying
  loading:      false,
};

// ══════════════════════════════════════════════════════════════════════════════
// TINY HELPERS
// ══════════════════════════════════════════════════════════════════════════════
const $  = id => document.getElementById(id);
const $$ = sel => document.querySelectorAll(sel);

function show(id) { $(id).classList.remove('hidden'); }
function hide(id) { $(id).classList.add('hidden');    }
function toggle(id, cond) { cond ? show(id) : hide(id); }

/** Format a raw Date header string into a short human-readable form. */
function fmtDate(raw) {
  if (!raw) return '';
  const d = new Date(raw);
  if (isNaN(d)) return raw.slice(0, 16);
  const now   = new Date();
  const sameY = d.getFullYear() === now.getFullYear();
  const sameD = d.toDateString() === now.toDateString();
  if (sameD) return d.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
  if (sameY) return d.toLocaleDateString([], { month: 'short', day: 'numeric' });
  return d.toLocaleDateString([], { month: 'short', day: 'numeric', year: '2-digit' });
}

/** Parse "Name <email@example.com>" or "email@example.com" → { name, email } */
function parseFrom(from) {
  if (!from) return { name: '?', email: '' };
  const m = from.match(/^(.+?)\s*<(.+?)>$/);
  if (m) return { name: m[1].replace(/^["']|["']$/g, '').trim(), email: m[2].trim() };
  return { name: from.trim(), email: from.trim() };
}

const AVATAR_COLORS = [
  '#7c3aed','#2563eb','#059669','#d97706','#dc2626',
  '#0891b2','#65a30d','#9333ea','#e11d48','#6366f1',
];
function avatarColor(name) {
  return AVATAR_COLORS[(name || '?').toUpperCase().charCodeAt(0) % AVATAR_COLORS.length];
}

/** Apply avatar letter + bg color to an element with class .avatar */
function setAvatar(el, name) {
  el.textContent = (name || '?')[0].toUpperCase();
  el.style.background = avatarColor(name);
}

// ══════════════════════════════════════════════════════════════════════════════
// TOAST
// ══════════════════════════════════════════════════════════════════════════════
let _toastTimer = null;
function toast(msg, type = 'info') {
  const t = $('toast');
  t.textContent = msg;
  t.className   = type;          // 'success' | 'error' | ''
  t.classList.remove('hidden');
  clearTimeout(_toastTimer);
  _toastTimer = setTimeout(() => t.classList.add('hidden'), 3200);
}

// ══════════════════════════════════════════════════════════════════════════════
// MODALS
// ══════════════════════════════════════════════════════════════════════════════
const Modal = {
  open(id)  { show(id); },
  close(id) { hide(id); },
  closeAll() {
    $$('.modal-overlay').forEach(m => m.classList.add('hidden'));
  },
};

// Close modal when clicking the overlay background
document.addEventListener('click', e => {
  if (e.target.classList.contains('modal-overlay')) Modal.closeAll();
});

// Wire up all [data-modal] close buttons
document.addEventListener('click', e => {
  const btn = e.target.closest('[data-modal]');
  if (btn) Modal.close(btn.dataset.modal);
});

// ══════════════════════════════════════════════════════════════════════════════
// CONTEXT MENU
// ══════════════════════════════════════════════════════════════════════════════
const Ctx = {
  show(x, y, mid) {
    State.ctxMid = mid;
    const m = $('ctx-menu');
    m.classList.remove('hidden');
    // Clamp to viewport
    const vw = window.innerWidth, vh = window.innerHeight;
    const mw = 180, mh = 140;
    m.style.left = Math.min(x, vw - mw) + 'px';
    m.style.top  = Math.min(y, vh - mh) + 'px';
  },
  hide() {
    $('ctx-menu').classList.add('hidden');
    State.ctxMid = null;
  },
};
document.addEventListener('click', () => Ctx.hide());
document.addEventListener('contextmenu', e => e.preventDefault());

$('ctx-archive').onclick = () => App.archive(State.ctxMid, true);
$('ctx-star')   .onclick = () => App.toggleStar(State.ctxMid, true);
$('ctx-read')   .onclick = () => App.markRead(State.ctxMid, true);
$('ctx-trash')  .onclick = () => App.trash(State.ctxMid, true);

// ══════════════════════════════════════════════════════════════════════════════
// LABEL DROPDOWN (apply label from detail)
// ══════════════════════════════════════════════════════════════════════════════
$('btn-apply-label').addEventListener('click', e => {
  e.stopPropagation();
  const dd = $('label-dropdown');
  dd.classList.toggle('hidden');
});
document.addEventListener('click', () => hide('label-dropdown'));

function buildLabelDropdown() {
  const dd = $('label-dropdown');
  dd.innerHTML = '';
  State.labels.forEach(l => {
    const btn = document.createElement('button');
    btn.textContent = l.name;
    btn.onclick = async () => {
      if (!State.currentMid) return;
      const r = await api('apply_label', State.currentMid, l.id);
      if (r.ok) toast(`Label "${l.name}" applied`, 'success');
      else toast(r.error, 'error');
      hide('label-dropdown');
    };
    dd.appendChild(btn);
  });
}

// ══════════════════════════════════════════════════════════════════════════════
// API WRAPPER  (thin async wrapper around window.pywebview.api)
// ══════════════════════════════════════════════════════════════════════════════
async function api(method, ...args) {
  try {
    return await window.pywebview.api[method](...args);
  } catch (err) {
    return { ok: false, error: String(err) };
  }
}

// ══════════════════════════════════════════════════════════════════════════════
// MAIN APP
// ══════════════════════════════════════════════════════════════════════════════
const App = {

  // ── Init ──────────────────────────────────────────────────────────────────
  async init() {
    const r = await api('connect');
    if (!r.ok) {
      const lt = $('loader-text');
      if (lt) lt.textContent = 'Connection error: ' + r.error;
      return;
    }

    // Update account badge
    const emailStr = r.email || '';
    $('sidebar-email').textContent = emailStr;
    setAvatar($('sidebar-avatar'), emailStr.split('@')[0]);

    // Load labels
    await this.loadLabels();

    // Show app immediately (messages load from cache below)
    hide('loading-screen');
    show('app');
    this._bindStaticEvents();

    // Load messages — comes from cache instantly if DB is populated
    await this.loadMessages(State.query);

    // Seed sync status from last known sync time
    const st = await api('get_sync_status');
    if (st.ok && st.last_sync) {
      this._setSyncText('Synced ' + _ago(st.last_sync));
    }
  },

  // ── Load labels ───────────────────────────────────────────────────────────
  async loadLabels() {
    const r = await api('get_labels');
    if (!r.ok) return;
    State.labels = r.labels;
    buildLabelDropdown();
    this._populateFilterLabelSelect();
  },

  _populateFilterLabelSelect() {
    const sel = $('f-label');
    sel.innerHTML = '<option value="">(none)</option>';
    State.labels.forEach(l => {
      const o = document.createElement('option');
      o.value = l.id; o.textContent = l.name;
      sel.appendChild(o);
    });
  },

  // ── Load messages ─────────────────────────────────────────────────────────
  async loadMessages(query) {
    State.query   = query;
    State.loading = true;

    const r = await api('get_messages', query);
    State.loading = false;

    if (!r.ok) { toast('Load error: ' + r.error, 'error'); return; }

    State.messages = r.messages;
    this.renderMessages(r.messages);
  },

  // ── Sync events (called from Python via evaluate_js) ──────────────────────
  onSyncEvent(event, data) {
    const icon = $('sync-icon');
    const text = $('sync-text');

    if (event === 'syncing') {
      icon.className = 'spinning';
      const labels = { full: 'Initial sync…', deep: 'Deep sync…', incremental: 'Syncing…' };
      text.textContent = labels[data.mode] || 'Syncing…';
      // Show progress bar only for full / deep (not incremental)
      if (data.mode !== 'incremental') {
        $('progress-fill').style.width = '0%';
        $('progress-label').textContent = '';
        show('progress-wrap');
      }

    } else if (event === 'progress') {
      const pct = data.total > 0 ? Math.min(100, Math.round((data.done / data.total) * 100)) : 0;
      $('progress-fill').style.width = pct + '%';
      $('progress-label').textContent = `${data.done.toLocaleString()} / ${data.total.toLocaleString()}`;

    } else if (event === 'synced') {
      icon.className = '';
      icon.textContent = '✓';
      this._setSyncText('Just now');
      hide('progress-wrap');

      // Refresh the list when new data arrives
      const changed = (data.changes ?? 0) + (data.count ?? 0);
      if (changed > 0) this.loadMessages(State.query);

    } else if (event === 'progress_hide') {
      hide('progress-wrap');

    } else if (event === 'sync_error') {
      icon.className = '';
      icon.textContent = '!';
      text.textContent = 'Sync error';
      hide('progress-wrap');
      toast('Sync error: ' + (data.error || 'unknown'), 'error');
    }
  },

  _setSyncText(str) {
    $('sync-text').textContent = str;
    $('sync-icon').textContent = '✓';
  },

  // ── Render email list ──────────────────────────────────────────────────────
  renderMessages(msgs) {
    const list = $('email-list');
    list.innerHTML = '';

    if (!msgs || msgs.length === 0) {
      list.innerHTML = '<div class="list-empty"><span>No messages</span></div>';
      return;
    }

    msgs.forEach(m => {
      const { name, email } = parseFrom(m.from);
      const div = document.createElement('div');
      div.className = `email-item${m.unread ? ' unread' : ''}${m.id === State.currentMid ? ' active' : ''}`;
      div.dataset.mid      = m.id;
      div.dataset.threadId = m.threadId;
      div.innerHTML = `
        <div class="avatar xs" style="background:${avatarColor(name)}">${(name[0]||'?').toUpperCase()}</div>
        <div class="ei-body">
          <div class="ei-row1">
            <span class="ei-from">${esc(name)}</span>
            <span class="ei-date">${fmtDate(m.date)}</span>
          </div>
          <div class="ei-row2">
            <span class="ei-subject">${esc(m.subject)}</span>
            <span class="ei-star${m.starred ? ' on' : ''}" data-mid="${m.id}" title="Star">★</span>
          </div>
        </div>
        <div class="unread-dot"></div>
      `;

      // Click → show detail
      div.addEventListener('click', e => {
        if (e.target.classList.contains('ei-star')) return;
        this.showDetail(m.id, m.threadId);
      });

      // Right-click → context menu
      div.addEventListener('contextmenu', e => {
        e.stopPropagation();
        Ctx.show(e.clientX, e.clientY, m.id);
      });

      // Star click
      div.querySelector('.ei-star').addEventListener('click', e => {
        e.stopPropagation();
        this.toggleStar(m.id);
      });

      list.appendChild(div);
    });
  },

  // ── Show email detail ──────────────────────────────────────────────────────
  async showDetail(mid, threadId) {
    State.currentMid    = mid;
    State.currentThread = threadId;

    // Highlight row
    $$('.email-item').forEach(el => el.classList.toggle('active', el.dataset.mid === mid));
    // Remove unread style immediately
    const row = document.querySelector(`.email-item[data-mid="${mid}"]`);
    if (row) row.classList.remove('unread');

    // Show panel
    show('detail-panel');
    $('app').classList.add('detail-open');
    $('detail-subject').textContent = '⏳ Loading…';
    $('detail-iframe').srcdoc = '';

    const r = await api('get_message_detail', mid);
    if (!r.ok) {
      toast('Error: ' + r.error, 'error');
      return;
    }

    const { name, email } = parseFrom(r.from);
    $('detail-subject').textContent = r.subject;
    $('detail-from-name').textContent  = name;
    $('detail-from-email').textContent = email ? `<${email}>` : '';
    $('detail-date').textContent = r.date ? new Date(r.date).toLocaleString() : '';
    setAvatar($('detail-avatar'), name);

    // Update star button
    const starBtn = $('btn-star');
    starBtn.textContent = r.starred ? '★ Unstar' : '⭐ Star';
    starBtn.classList.toggle('starred', r.starred);

    // Render email body in iframe (inject base styles for readability)
    const styled = `<!DOCTYPE html><html><head><meta charset="UTF-8">
<style>
  body { font-family: 'Segoe UI', system-ui, sans-serif; font-size: 14px;
         line-height: 1.6; padding: 20px; margin: 0; color: #111;
         word-break: break-word; }
  img  { max-width: 100%; height: auto; }
  a    { color: #1a73e8; }
  pre, code { font-family: Consolas, monospace; font-size: 13px; }
  pre  { white-space: pre-wrap; background: #f6f8fa; padding: 12px;
         border-radius: 6px; overflow-x: auto; }
</style></head><body>${r.body}</body></html>`;
    $('detail-iframe').srcdoc = styled;
  },

  closeDetail() {
    hide('detail-panel');
    $('app').classList.remove('detail-open');
    $$('.email-item').forEach(el => el.classList.remove('active'));
    State.currentMid    = null;
    State.currentThread = null;
  },

  // ── Actions ───────────────────────────────────────────────────────────────
  async archive(mid, fromCtx = false) {
    mid = mid || State.currentMid;
    if (!mid) return;
    const r = await api('archive', mid);
    if (r.ok) { toast('Archived', 'success'); this._removeFromList(mid); }
    else toast(r.error, 'error');
  },

  async trash(mid, fromCtx = false) {
    mid = mid || State.currentMid;
    if (!mid) return;
    const r = await api('trash', mid);
    if (r.ok) { toast('Moved to trash', 'success'); this._removeFromList(mid); }
    else toast(r.error, 'error');
  },

  async toggleStar(mid, fromCtx = false) {
    mid = mid || State.currentMid;
    if (!mid) return;
    const r = await api('toggle_star', mid);
    if (!r.ok) { toast(r.error, 'error'); return; }

    // Update list row
    const star = document.querySelector(`.email-item[data-mid="${mid}"] .ei-star`);
    if (star) star.classList.toggle('on', r.starred);

    // Update detail bar if open
    if (mid === State.currentMid) {
      $('btn-star').textContent = r.starred ? '★ Unstar' : '⭐ Star';
      $('btn-star').classList.toggle('starred', r.starred);
    }
  },

  async markRead(mid, fromCtx = false) {
    mid = mid || State.currentMid;
    if (!mid) return;
    const r = await api('mark_read', mid);
    if (r.ok) {
      const row = document.querySelector(`.email-item[data-mid="${mid}"]`);
      if (row) row.classList.remove('unread');
    } else toast(r.error, 'error');
  },

  async openInBrowser() {
    if (!State.currentThread) return;
    const r = await api('open_in_browser', State.currentThread);
    if (!r.ok) toast(r.error, 'error');
  },

  _removeFromList(mid) {
    const row = document.querySelector(`.email-item[data-mid="${mid}"]`);
    if (row) row.remove();
    if (State.currentMid === mid) this.closeDetail();
  },

  // ── Search ────────────────────────────────────────────────────────────────
  async search() {
    const q = $('search-input').value.trim();
    if (!q) return;
    // Deactivate folder buttons
    $$('.folder-btn').forEach(b => b.classList.remove('active'));
    await this.loadMessages(q);
  },

  // ── Compose ───────────────────────────────────────────────────────────────
  openCompose(replyData = null) {
    State.replyData = replyData;
    $('compose-title').textContent = replyData ? 'Reply' : 'New Message';
    $('compose-to').value      = replyData ? replyData.to      : '';
    $('compose-subject').value = replyData ? replyData.subject : '';
    $('compose-body').value    = '';
    Modal.open('modal-compose');
    $('compose-to').focus();
  },

  async sendMessage() {
    const to      = $('compose-to').value.trim();
    const subject = $('compose-subject').value.trim();
    const body    = $('compose-body').value;
    if (!to || !subject) { toast('Fill in To and Subject', 'error'); return; }

    const threadId = State.replyData ? State.replyData.threadId : null;
    $('btn-send').disabled = true;
    const r = await api('send_message', to, subject, body, threadId);
    $('btn-send').disabled = false;

    if (r.ok) {
      toast('Message sent ✓', 'success');
      Modal.close('modal-compose');
    } else toast('Send error: ' + r.error, 'error');
  },

  // ── Labels ────────────────────────────────────────────────────────────────
  async openLabels() {
    const r = await api('get_labels');
    if (!r.ok) { toast(r.error, 'error'); return; }
    State.labels = r.labels;
    this._renderLabelsList(r.labels);
    Modal.open('modal-labels');
  },

  _renderLabelsList(labels) {
    const ul = $('labels-modal-list');
    ul.innerHTML = '';
    if (!labels.length) { ul.innerHTML = '<p style="color:var(--muted)">No labels</p>'; return; }
    labels.forEach(l => {
      const row = document.createElement('div');
      row.className = 'label-row';
      row.innerHTML = `
        <span class="label-name">${esc(l.name)}</span>
        <button class="label-del" data-lid="${l.id}" title="Delete">🗑</button>
      `;
      row.querySelector('.label-del').onclick = () => this.deleteLabel(l.id, l.name);
      ul.appendChild(row);
    });
  },

  async createLabel() {
    const name = prompt('Label name:');
    if (!name) return;
    const r = await api('create_label', name.trim());
    if (r.ok) {
      toast(`Label "${name}" created`, 'success');
      await this.openLabels();
      await this.loadLabels();
    } else toast(r.error, 'error');
  },

  async deleteLabel(lid, name) {
    if (!confirm(`Delete label "${name}"?`)) return;
    const r = await api('delete_label', lid);
    if (r.ok) {
      toast(`Label "${name}" deleted`, 'success');
      await this.openLabels();
      await this.loadLabels();
    } else toast(r.error, 'error');
  },

  // ── Filters ───────────────────────────────────────────────────────────────
  async openFilters() {
    Modal.open('modal-filters');
    await this._reloadFilters();
    await this._reloadBlocked();
  },

  async _reloadFilters() {
    const r = await api('get_filters');
    const tbody = $('filters-tbody');
    tbody.innerHTML = '';
    if (!r.ok) { toast(r.error, 'error'); return; }
    if (!r.filters.length) {
      tbody.innerHTML = '<tr><td colspan="3" style="color:var(--muted)">No filters</td></tr>';
      return;
    }
    r.filters.forEach(f => {
      const c  = f.criteria || {};
      const ac = f.action   || {};
      const criteria = [
        c.from    && `From: <code>${esc(c.from)}</code>`,
        c.to      && `To: <code>${esc(c.to)}</code>`,
        c.subject && `Subject: <code>${esc(c.subject)}</code>`,
        c.query   && `Contains: <code>${esc(c.query)}</code>`,
      ].filter(Boolean).join(', ') || '(all)';

      const addL = (ac.addLabelIds    || []).join(', ');
      const remL = (ac.removeLabelIds || []).join(', ');
      let actions = [];
      if (remL.includes('INBOX'))  actions.push('Skip inbox');
      if (remL.includes('UNREAD')) actions.push('Mark read');
      if (addL.includes('SPAM'))   actions.push('Mark spam');
      if (addL.includes('STARRED'))actions.push('Star');
      if (addL.includes('TRASH'))  actions.push('Delete');
      // Custom labels
      (ac.addLabelIds || []).filter(id => !['SPAM','STARRED','TRASH'].includes(id))
        .forEach(id => {
          const label = State.labels.find(l => l.id === id);
          if (label) actions.push(`Label: ${label.name}`);
        });

      const tr = document.createElement('tr');
      tr.innerHTML = `
        <td>${criteria}</td>
        <td>${actions.join(' · ') || '(none)'}</td>
        <td><button class="label-del" title="Delete filter">🗑</button></td>
      `;
      tr.querySelector('.label-del').onclick = () => this.deleteFilter(f.id);
      tbody.appendChild(tr);
    });
  },

  async _reloadBlocked() {
    const r = await api('get_blocked');
    const div = $('blocked-list');
    div.innerHTML = '';
    if (!r.ok) return;
    if (!r.blocked.length) {
      div.innerHTML = '<p style="color:var(--muted);font-size:13px">No blocked addresses</p>';
      return;
    }
    r.blocked.forEach(b => {
      const row = document.createElement('div');
      row.className = 'blocked-row';
      row.innerHTML = `
        <span class="blocked-addr">${esc(b.address)}</span>
        <button class="label-del blocked-del" title="Unblock">✕ Unblock</button>
      `;
      row.querySelector('.blocked-del').onclick = () => this.unblockAddress(b.filter_id, b.address);
      div.appendChild(row);
    });
  },

  openCreateFilter() {
    // Clear form
    ['f-from','f-to','f-subject','f-query'].forEach(id => $(id).value = '');
    ['f-skipInbox','f-markRead','f-markSpam','f-star','f-trash'].forEach(id => $(id).checked = false);
    $('f-label').value = '';
    Modal.open('modal-create-filter');
  },

  async saveFilter() {
    const data = {
      from:      $('f-from').value.trim(),
      to:        $('f-to').value.trim(),
      subject:   $('f-subject').value.trim(),
      query:     $('f-query').value.trim(),
      skipInbox: $('f-skipInbox').checked,
      markRead:  $('f-markRead').checked,
      markSpam:  $('f-markSpam').checked,
      star:      $('f-star').checked,
      trash:     $('f-trash').checked,
      labelId:   $('f-label').value,
    };
    if (!data.from && !data.to && !data.subject && !data.query) {
      toast('Fill in at least one criterion', 'error'); return;
    }
    const r = await api('create_filter', data);
    if (r.ok) {
      toast('Filter created', 'success');
      Modal.close('modal-create-filter');
      await this._reloadFilters();
    } else toast(r.error, 'error');
  },

  async deleteFilter(fid) {
    if (!confirm('Delete this filter?')) return;
    const r = await api('delete_filter', fid);
    if (r.ok) { toast('Filter deleted', 'success'); await this._reloadFilters(); }
    else toast(r.error, 'error');
  },

  async exportFilters() {
    const r = await api('export_filters');
    if (r.ok) toast(`${r.count} filter(s) exported to exports/filters.json`, 'success');
    else toast(r.error, 'error');
  },

  // ── Blocked addresses ─────────────────────────────────────────────────────
  async blockAddress() {
    const addr = $('block-input').value.trim();
    if (!addr) { toast('Enter an email address', 'error'); return; }
    const r = await api('block_address', addr);
    if (r.ok) {
      $('block-input').value = '';
      toast(`${addr} blocked`, 'success');
      await this._reloadBlocked();
    } else toast(r.error, 'error');
  },

  async unblockAddress(filterId, addr) {
    if (!confirm(`Unblock "${addr}"?`)) return;
    const r = await api('unblock_address', filterId);
    if (r.ok) { toast(`${addr} unblocked`, 'success'); await this._reloadBlocked(); }
    else toast(r.error, 'error');
  },

  // ── Tabs (Filters modal) ──────────────────────────────────────────────────
  switchTab(tabId) {
    $$('.tab-btn').forEach(b => b.classList.toggle('active', b.dataset.tab === tabId));
    $$('.tab-pane').forEach(p => p.classList.toggle('hidden', p.id !== tabId));
  },

  // ── Bulk Cleanup ──────────────────────────────────────────────────────────
  openCleanup() {
    $('cleanup-status').classList.add('hidden');
    Modal.open('modal-cleanup');
  },

  async _bulkRun(query, action) {
    const status = $('cleanup-status');
    status.textContent = '⏳ Previewing…';
    status.classList.remove('hidden');

    const prev = await api('bulk_preview', query);
    if (!prev.ok) { status.textContent = '❌ ' + prev.error; return; }
    if (prev.count === 0) { status.textContent = 'No messages found.'; return; }

    if (!confirm(`${prev.count} message(s) found. ${action === 'archive' ? 'Archive' : 'Delete'} all?`)) {
      status.classList.add('hidden'); return;
    }

    status.textContent = `⏳ Processing ${prev.count} message(s)…`;
    const r = await api('bulk_action', query, action);
    if (r.ok) {
      status.textContent = `✅ ${r.count} message(s) processed.`;
      toast(`${r.count} messages ${action === 'archive' ? 'archived' : 'deleted'}`, 'success');
    } else {
      status.textContent = '❌ ' + r.error;
    }
  },

  async bulkBySender(action) {
    const addr = $('cleanup-sender').value.trim();
    if (!addr) { toast('Enter a sender email', 'error'); return; }
    await this._bulkRun(`from:${addr}`, action);
  },

  async bulkByKeyword(action) {
    const kw = $('cleanup-keyword').value.trim();
    if (!kw) { toast('Enter a keyword', 'error'); return; }
    await this._bulkRun(`subject:${kw}`, action);
  },

  async quickAction(query, action) {
    await this._bulkRun(query, action);
  },

  // ── Event wiring ─────────────────────────────────────────────────────────
  _bindStaticEvents() {
    // Folder nav
    $$('.folder-btn').forEach(btn => {
      btn.addEventListener('click', () => {
        $$('.folder-btn').forEach(b => b.classList.remove('active'));
        btn.classList.add('active');
        $('search-input').value = '';
        this.loadMessages(btn.dataset.query);
      });
    });

    // Toolbar
    $('btn-refresh')  .onclick = () => this.loadMessages(State.query);
    $('btn-sync-now') .onclick = () => api('sync_now');
    $('btn-search')   .onclick = () => this.search();
    $('search-input').addEventListener('keydown', e => { if (e.key === 'Enter') this.search(); });
    $('btn-compose') .onclick = () => this.openCompose();

    // Detail actions
    $('btn-reply')       .onclick = () => {
      const msg = State.messages.find(m => m.id === State.currentMid);
      const { name, email } = parseFrom(msg ? msg.from : '');
      this.openCompose({ to: email, subject: `Re: ${msg ? msg.subject : ''}`, threadId: State.currentThread });
    };
    $('btn-archive')     .onclick = () => this.archive();
    $('btn-star')        .onclick = () => this.toggleStar();
    $('btn-trash')       .onclick = () => this.trash();
    $('btn-browser')     .onclick = () => this.openInBrowser();
    $('btn-close-detail').onclick = () => this.closeDetail();

    // Compose send
    $('btn-send').onclick = () => this.sendMessage();

    // Sidebar tools
    $('btn-labels') .onclick = () => this.openLabels();
    $('btn-filters').onclick = () => this.openFilters();
    $('btn-cleanup').onclick = () => this.openCleanup();

    // Labels modal
    $('btn-create-label').onclick = () => this.createLabel();

    // Filters modal
    $('btn-new-filter')    .onclick = () => this.openCreateFilter();
    $('btn-save-filter')   .onclick = () => this.saveFilter();
    $('btn-export-filters').onclick = () => this.exportFilters();
    $('btn-block-addr')    .onclick = () => this.blockAddress();

    // Tab switching
    $$('.tab-btn').forEach(b => {
      b.addEventListener('click', () => this.switchTab(b.dataset.tab));
    });

    // Cleanup buttons
    $('cu-sender-archive').onclick = () => this.bulkBySender('archive');
    $('cu-sender-trash')  .onclick = () => this.bulkBySender('trash');
    $('cu-kw-archive')    .onclick = () => this.bulkByKeyword('archive');
    $('cu-kw-trash')      .onclick = () => this.bulkByKeyword('trash');
    $('cu-promos').onclick = () => this.quickAction('category:promotions', 'trash');
    $('cu-spam')  .onclick = () => this.quickAction('in:spam', 'trash');
    $('cu-read')  .onclick = () => this.quickAction('is:read in:inbox', 'archive');
  },
};

// ══════════════════════════════════════════════════════════════════════════════
// UTILS
// ══════════════════════════════════════════════════════════════════════════════

/** Escape HTML entities to prevent injection in innerHTML. */
function esc(str) {
  return String(str)
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;');
}

/** Turn a UTC ISO timestamp into a human-readable "X ago" string. */
function _ago(isoStr) {
  if (!isoStr) return '';
  const diff = Math.floor((Date.now() - new Date(isoStr)) / 1000);
  if (diff < 60)   return 'just now';
  if (diff < 3600) return `${Math.floor(diff / 60)}m ago`;
  if (diff < 86400)return `${Math.floor(diff / 3600)}h ago`;
  return `${Math.floor(diff / 86400)}d ago`;
}

// ══════════════════════════════════════════════════════════════════════════════
// BOOT
// ══════════════════════════════════════════════════════════════════════════════
if (window.pywebview) {
  App.init();
} else {
  window.addEventListener('pywebviewready', () => App.init());
}
