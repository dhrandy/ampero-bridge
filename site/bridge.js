/* Bridge panel for the model library page.

   Talks to your own ampero-bridge from the browser: stars that are kept on the bridge,
   copying a block between patches, backup and restore, and a .prst inspector.
   The page works without any of this. Nothing is sent anywhere until a bridge address
   and key are entered under Settings, and both stay in this browser. */
(function () {
  'use strict';

  var FEATURES = [
    ['details', 'Model details', 'Tone notes and specs under each model.'],
    ['favorites', 'Favorites', 'Stars on presets and models, kept on the bridge so every browser sees them.'],
    ['copy', 'Block copy', 'Copy one block from a preset onto another.'],
    ['backup', 'Backup and restore', 'Dump every patch to a file and put patches back.'],
    ['import', 'Import', 'Look inside a .prst file or load a bridge backup.']
  ];
  var COPY_BLOCKS = ['fx1', 'fx2', 'amp', 'cab', 'eq', 'dly', 'rvb'];
  var $ = function (id) { return document.getElementById(id); };

  var state = {
    url: '', key: '', remember: false,
    features: { details: true, favorites: true, copy: true, backup: true, import: true },
    connected: false, favPatches: {}, favModels: {}, known: [], models: null,
    onlyStarred: false, tab: 'models', hooks: {}
  };

  function esc(s) {
    return String(s).replace(/[&<>"']/g, function (c) {
      return { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c];
    });
  }

  // ---- settings kept in this browser --------------------------------------------------

  function loadSettings() {
    try {
      var f = JSON.parse(localStorage.getItem('ampero.features') || '{}');
      FEATURES.forEach(function (x) { if (f[x[0]] === false) state.features[x[0]] = false; });
      var saved = JSON.parse(localStorage.getItem('ampero.bridge') || 'null');
      state.remember = !!saved;
      saved = saved || JSON.parse(sessionStorage.getItem('ampero.bridge') || 'null');
      if (saved && saved.url && saved.key) { state.url = saved.url; state.key = saved.key; }
    } catch (e) { /* storage blocked: the page still works, nothing is remembered */ }
  }

  function saveSettings() {
    try {
      localStorage.setItem('ampero.features', JSON.stringify(state.features));
      localStorage.removeItem('ampero.bridge');
      sessionStorage.removeItem('ampero.bridge');
      if (state.url && state.key) {
        (state.remember ? localStorage : sessionStorage).setItem('ampero.bridge', JSON.stringify({ url: state.url, key: state.key }));
      }
    } catch (e) { /* see loadSettings */ }
  }

  function cleanUrl(text) {
    var u = String(text || '').trim().replace(/\/+$/, '');
    return /^https?:\/\/[^\s/]+/i.test(u) ? u : '';
  }

  // ---- bridge calls --------------------------------------------------------------------

  function api(path, body, raw) {
    var opt = { headers: { 'X-Api-Key': state.key } };
    if (body !== undefined) {
      opt.method = 'POST';
      opt.headers['Content-Type'] = 'application/json';
      opt.body = JSON.stringify(body);
    }
    return fetch(state.url + path, opt).then(function (r) {
      if (raw && r.ok) return r.blob();
      return r.json().catch(function () { return {}; }).then(function (j) {
        if (!r.ok) {
          var e = new Error(j.error || ('The bridge answered ' + r.status));
          e.status = r.status;
          throw e;
        }
        return j;
      });
    }, function () {
      throw new Error('Cannot reach the bridge. Check the address, that CORS allows this site (AMPERO_CORS_ORIGINS), and that it is https.');
    });
  }

  function pollJob(onTick) {
    return new Promise(function (resolve, reject) {
      (function tick() {
        api('/api/backup/status').then(function (j) {
          onTick(j);
          if (j.state === 'done') resolve(j);
          else if (j.state === 'failed') reject(new Error(j.error || 'The job failed'));
          else setTimeout(tick, 1200);
        }, reject);
      })();
    });
  }

  // ---- model names, for readable previews ----------------------------------------------

  function modelName(block, code) {
    if (!state.models) return 'model ' + code;
    var hit = state.models[String(block).toUpperCase() + ':' + code];
    return hit || 'model ' + code;
  }

  function setModels(data) {
    var map = {};
    (data.blocks || []).forEach(function (b) {
      b.models.forEach(function (m) { if (m.code !== null && m.code !== undefined) map[b.block + ':' + m.code] = m.name; });
    });
    state.models = map;
  }

  // ---- favorites -------------------------------------------------------------------------

  function loadFavorites() {
    if (!state.connected || !state.features.favorites) return Promise.resolve();
    return api('/api/favorites').then(function (f) {
      state.favPatches = {}; state.favModels = {};
      f.patches.forEach(function (p) { state.favPatches[p.index] = true; });
      f.models.forEach(function (m) { state.favModels[m.id] = true; });
      changed();
    });
  }

  function toggleStar(kind, id, button) {
    var map = kind === 'patch' ? state.favPatches : state.favModels;
    var want = !map[id];
    button.setAttribute('aria-pressed', want);
    api('/api/favorites', { kind: kind, id: id, starred: want }).then(function (f) {
      state.favPatches = {}; state.favModels = {};
      f.patches.forEach(function (p) { state.favPatches[p.index] = true; });
      f.models.forEach(function (m) { state.favModels[m.id] = true; });
      changed();
    }, function (e) {
      button.setAttribute('aria-pressed', !want);
      note('Could not save the star: ' + e.message, true);
    });
  }

  function note(text, bad) {
    var el = $('bridge-note');
    if (!el) return;
    el.textContent = text;
    el.className = 'msg' + (bad ? ' bad' : '');
  }

  // ---- what the library page asks for ----------------------------------------------------

  function modelStarHtml(m) {
    if (!(state.connected && state.features.favorites) || m.code === null || m.code === undefined) return '';
    var id = m.block + ':' + m.code, on = !!state.favModels[id];
    return '<button type="button" class="star" data-star-model="' + esc(id) + '" aria-pressed="' + on + '" aria-label="Star ' + esc(m.name) + '">' + (on ? '\u2605' : '\u2606') + '</button>';
  }

  function modelPasses(m) {
    if (!state.onlyStarred || !(state.connected && state.features.favorites)) return true;
    return !!state.favModels[m.block + ':' + m.code];
  }

  function changed() {
    renderChrome();
    if (state.hooks.rerender) state.hooks.rerender();
    if (state.tab === 'presets') renderPresets();
  }

  // ---- header, tabs, settings dialog -------------------------------------------------------

  function anyFeature() { return FEATURES.some(function (f) { return f[0] !== 'details' && state.features[f[0]]; }); }

  function renderChrome() {
    var gear = $('gear');
    gear.querySelector('.dot').className = 'dot' + (state.connected ? ' on' : '');
    var showTabs = state.connected && anyFeature();
    $('tabs').hidden = !showTabs;
    if (!showTabs && state.tab !== 'models') selectTab('models');
    var starFilter = $('starfilter');
    if (starFilter) starFilter.hidden = !(state.connected && state.features.favorites);
    if (!(state.connected && state.features.favorites)) state.onlyStarred = false;
  }

  function selectTab(name) {
    state.tab = name;
    [].forEach.call($('tabs').children, function (b) { b.setAttribute('aria-selected', b.dataset.tab === name); });
    $('view-models').hidden = name !== 'models';
    $('view-presets').hidden = name !== 'presets';
    if (name === 'presets') refreshPresets();
  }

  function openSettings() {
    var dlg = $('settings');
    $('set-url').value = state.url;
    $('set-key').value = state.key;
    $('set-remember').checked = state.remember;
    FEATURES.forEach(function (f) { $('feat-' + f[0]).checked = state.features[f[0]]; });
    $('set-msg').textContent = state.connected ? 'Connected.' : '';
    $('set-msg').className = 'msg' + (state.connected ? ' good' : '');
    dlg.showModal();
  }

  function connect() {
    var url = cleanUrl($('set-url').value), key = $('set-key').value.trim();
    var msg = $('set-msg');
    if (!url || !key) { msg.textContent = 'Enter the bridge address (https://...) and the API key.'; msg.className = 'msg bad'; return; }
    state.url = url; state.key = key; state.remember = $('set-remember').checked;
    msg.textContent = 'Checking...'; msg.className = 'msg';
    api('/api/health').then(function () {
      state.connected = true;
      saveSettings();
      msg.textContent = 'Connected.'; msg.className = 'msg good';
      return loadFavorites();
    }).then(changed, function (e) {
      state.connected = false;
      msg.textContent = e.status === 401 ? 'The bridge says that key is not right.' : e.message;
      msg.className = 'msg bad';
      changed();
    });
  }

  function forget() {
    state.url = ''; state.key = ''; state.connected = false; state.favPatches = {}; state.favModels = {};
    saveSettings();
    $('set-url').value = ''; $('set-key').value = '';
    $('set-msg').textContent = 'Forgotten. Nothing is kept in this browser.'; $('set-msg').className = 'msg';
    changed();
  }

  function buildChrome() {
    var brand = document.querySelector('.brand');
    var gear = document.createElement('button');
    gear.type = 'button'; gear.id = 'gear'; gear.className = 'gear';
    gear.innerHTML = '<span class="dot"></span>Settings';
    gear.onclick = openSettings;
    brand.appendChild(gear);

    var tabs = document.createElement('div');
    tabs.id = 'tabs'; tabs.className = 'tabs'; tabs.hidden = true; tabs.setAttribute('role', 'tablist');
    tabs.innerHTML = '<button type="button" class="tab" role="tab" data-tab="models" aria-selected="true">Models</button>' +
      '<button type="button" class="tab" role="tab" data-tab="presets" aria-selected="false">Presets</button>';
    tabs.onclick = function (e) { var t = e.target.closest('.tab'); if (t) selectTab(t.dataset.tab); };
    var wrap = document.querySelector('.top').nextElementSibling;
    wrap.insertBefore(tabs, wrap.firstChild);

    var presets = document.createElement('div');
    presets.id = 'view-presets'; presets.className = 'pane'; presets.hidden = true;
    wrap.insertBefore(presets, wrap.querySelector('footer'));

    var dlg = document.createElement('dialog');
    dlg.id = 'settings';
    dlg.innerHTML = '<form method="dialog" class="dlg" id="set-form">' +
      '<h2>Settings</h2>' +
      '<p class="msg">These stay in this browser. The key is only sent to the bridge address below.</p>' +
      '<label>Bridge address<input type="url" id="set-url" placeholder="https://your-bridge.example" autocomplete="off" autocapitalize="off" spellcheck="false"></label>' +
      '<label>API key<input type="password" id="set-key" autocomplete="off" spellcheck="false"></label>' +
      '<label class="chk"><input type="checkbox" id="set-remember"><span>Remember on this device<small>Off: forgotten when the tab closes.</small></span></label>' +
      '<div class="row"><button type="button" class="pbtn pri" id="set-connect">Connect</button><button type="button" class="pbtn" id="set-forget">Forget</button></div>' +
      '<div class="msg" id="set-msg" role="status"></div>' +
      '<div class="sect">Show</div>' +
      FEATURES.map(function (f) {
        return '<label class="chk"><input type="checkbox" id="feat-' + f[0] + '"><span>' + f[1] + '<small>' + f[2] + '</small></span></label>';
      }).join('') +
      '<div class="row"><button class="pbtn" value="close">Done</button></div></form>';
    document.body.appendChild(dlg);
    $('set-connect').onclick = connect;
    $('set-forget').onclick = forget;
    FEATURES.forEach(function (f) {
      $('feat-' + f[0]).onchange = function () { state.features[f[0]] = this.checked; saveSettings(); changed(); };
    });
    $('set-remember').onchange = function () { state.remember = this.checked; saveSettings(); };
    $('set-form').addEventListener('keydown', function (e) { if (e.key === 'Enter' && e.target.tagName === 'INPUT' && e.target.type !== 'checkbox') { e.preventDefault(); connect(); } });

    var opts = document.querySelector('.opts');
    var lab = document.createElement('label');
    lab.id = 'starfilter'; lab.hidden = true;
    lab.innerHTML = '<input type="checkbox" id="onlystar"> starred only';
    opts.appendChild(lab);
    $('onlystar').onchange = function () { state.onlyStarred = this.checked; if (state.hooks.rerender) state.hooks.rerender(); };

    document.addEventListener('click', function (e) {
      var b = e.target.closest('[data-star-model]');
      if (b) toggleStar('model', b.dataset.starModel, b);
    });
    document.addEventListener('visibilitychange', function () { if (!document.hidden) loadFavorites().catch(function () {}); });
  }

  // ---- presets pane -------------------------------------------------------------------------

  function refreshPresets() {
    if (!state.connected) return;
    Promise.all([api('/api/patches/known'), loadFavorites()]).then(function (r) {
      state.known = r[0].patches || [];
      renderPresets();
    }, function (e) { note(e.message, true); });
  }

  function patchRows() {
    var rows = state.known.map(function (p) { return { index: p.index, label: p.label, name: p.name }; });
    var have = {};
    rows.forEach(function (r) { have[r.index] = true; });
    Object.keys(state.favPatches).forEach(function (k) {
      k = Number(k);
      if (!have[k]) rows.push({ index: k, label: label(k), name: '(not read yet)' });
    });
    rows.sort(function (a, b) { return a.index - b.index; });
    return rows;
  }

  function label(i) { return 'P' + (Math.floor(i / 3) + 1) + '-' + (i % 3 + 1); }

  function renderPresets() {
    var f = state.features, root = $('view-presets'), h = '<div id="bridge-note" class="msg" role="status"></div>';
    if (f.favorites || f.copy) {
      var rows = patchRows();
      if (f.favorites && state.onlyStarred) rows = rows.filter(function (r) { return state.favPatches[r.index]; });
      h += '<div class="sect">Presets the bridge has seen</div>';
      if (f.favorites) h += '<label class="chk" style="display:flex"><input type="checkbox" id="starred-patches"' + (state.onlyStarred ? ' checked' : '') + '><span>Starred only</span></label>';
      h += rows.length ? rows.map(function (r) {
        var on = !!state.favPatches[r.index];
        return '<div class="patch"><span class="lbl">' + esc(r.label) + '</span><span class="nm">' + esc(r.name) + '</span>' +
          (f.favorites ? '<button type="button" class="star" data-star-patch="' + r.index + '" aria-pressed="' + on + '" aria-label="Star ' + esc(r.label) + '">' + (on ? '\u2605' : '\u2606') + '</button>' : '<span></span>') +
          (f.copy ? '<button type="button" class="pbtn copy" data-copy="' + r.index + '">Copy a block</button>' : '') + '</div>';
      }).join('') : '<div class="empty">' + (state.onlyStarred ? 'Nothing starred yet.' : 'No presets seen yet. Read one with GET /api/patch/current and it shows up here.') + '</div>';
    }
    if (f.backup) {
      h += '<div class="sect">Backup and restore</div><div class="panel"><p>Backup reads every patch off the pedal one by one and saves one file on the bridge. It takes a few minutes and the pedal moves through its patches while it runs.</p>' +
        '<div class="row"><button type="button" class="pbtn pri" id="do-backup">Back up all patches</button><button type="button" class="pbtn" id="do-restore-file">Restore from a file</button></div>' +
        '<div class="bar" id="job-bar" hidden><i></i></div><div class="msg" id="job-msg" role="status"></div><ul class="list2" id="backups"></ul></div>';
    }
    if (f.import) {
      h += '<div class="sect">Import</div><div class="panel"><p>Pick a Hotone .prst file to see what is in it, or a bridge backup (.json) to restore from it.</p>' +
        '<div class="row"><button type="button" class="pbtn" id="do-import">Choose a file</button></div><div id="import-out"></div></div>';
    }
    h += '<input type="file" id="file-pick" hidden>';
    root.innerHTML = h;
    wirePresets();
    if (f.backup) listBackups();
  }

  function wirePresets() {
    var root = $('view-presets');
    root.onclick = function (e) {
      var s = e.target.closest('[data-star-patch]');
      if (s) return toggleStar('patch', Number(s.dataset.starPatch), s);
      var c = e.target.closest('[data-copy]');
      if (c) return openCopy(Number(c.dataset.copy));
    };
    var sp = $('starred-patches');
    if (sp) sp.onchange = function () { state.onlyStarred = this.checked; var o = $('onlystar'); if (o) o.checked = this.checked; renderPresets(); if (state.hooks.rerender) state.hooks.rerender(); };
    if ($('do-backup')) $('do-backup').onclick = startBackup;
    if ($('do-restore-file')) $('do-restore-file').onclick = function () { pickFile('.json,application/json', function (file) { readJson(file).then(openRestore, function (e) { $('job-msg').textContent = e.message; $('job-msg').className = 'msg bad'; }); }); };
    if ($('do-import')) $('do-import').onclick = function () { pickFile('.prst,.json,application/json', importFile); };
  }

  function pickFile(accept, then) {
    var input = $('file-pick');
    input.accept = accept; input.value = '';
    input.onchange = function () { if (input.files[0]) then(input.files[0]); };
    input.click();
  }

  function readJson(file) {
    return file.text().then(function (t) {
      try { return JSON.parse(t); } catch (e) { throw new Error('That file is not a bridge backup (it is not JSON).'); }
    });
  }

  // ---- block copy ---------------------------------------------------------------------------

  function openCopy(from) {
    var src = patchRows().filter(function (r) { return r.index === from; })[0] || { label: label(from), name: '' };
    var dlg = document.createElement('dialog');
    dlg.innerHTML = '<form method="dialog" class="dlg"><h2>Copy a block</h2>' +
      '<p class="msg">From <b>' + esc(src.label) + '</b> ' + esc(src.name) + '. Copying selects both patches on the pedal, so unsaved edits there are lost. The result goes into the edit buffer and is not saved until you say so.</p>' +
      '<label>Block<select id="cp-block">' + COPY_BLOCKS.map(function (b) { return '<option value="' + b + '">' + b.toUpperCase() + '</option>'; }).join('') + '</select></label>' +
      '<label>Onto patch<input type="text" id="cp-to" list="cp-list" placeholder="P27-2" autocomplete="off" autocapitalize="characters" spellcheck="false"></label>' +
      '<datalist id="cp-list">' + patchRows().filter(function (r) { return r.index !== from; }).map(function (r) { return '<option value="' + esc(r.label) + '">' + esc(r.name) + '</option>'; }).join('') + '</datalist>' +
      '<div id="cp-out" role="status"></div>' +
      '<div class="row"><button type="button" class="pbtn" id="cp-preview">Preview</button><button type="button" class="pbtn pri" id="cp-go" disabled>Copy</button><button class="pbtn" value="close">Close</button></div></form>';
    document.body.appendChild(dlg);
    dlg.addEventListener('close', function () { dlg.remove(); });
    dlg.showModal();
    var out = dlg.querySelector('#cp-out'), go = dlg.querySelector('#cp-go');
    var request = function (extra) {
      var to = dlg.querySelector('#cp-to').value.trim().toUpperCase();
      if (!/^P\d{1,3}-\d$/.test(to)) throw new Error('Type the target as a label like P27-2.');
      var block = dlg.querySelector('#cp-block').value;
      var body = { from: from, to: to, block: block };
      for (var k in extra) body[k] = extra[k];
      return { body: body, confirm: 'COPY ' + block.toUpperCase() + ' ' + label(from) + ' TO ' + to, to: to };
    };
    dlg.querySelector('#cp-to').oninput = function () { go.disabled = true; };
    dlg.querySelector('#cp-block').onchange = function () { go.disabled = true; };
    dlg.querySelector('#cp-preview').onclick = function () {
      var r; go.disabled = true;
      try { r = request({ dry_run: true }); } catch (e) { out.innerHTML = '<div class="msg bad">' + esc(e.message) + '</div>'; return; }
      out.innerHTML = '<div class="msg">Reading both patches...</div>';
      api('/api/block/copy', r.body).then(function (j) {
        out.innerHTML = describeCopy(j, true);
        go.disabled = !j.would_write.length;
      }, function (e) { out.innerHTML = '<div class="msg bad">' + esc(e.message) + '</div>'; });
    };
    go.onclick = function () {
      var r;
      try { r = request({ confirm: null }); } catch (e) { return; }
      r.body.confirm = r.confirm; delete r.body.dry_run;
      go.disabled = true;
      out.innerHTML = '<div class="msg">Copying. This takes several seconds...</div>';
      api('/api/block/copy', r.body).then(function (j) {
        out.innerHTML = describeCopy(j, false) + '<div class="row"><button type="button" class="pbtn danger" id="cp-save">Save to ' + esc(j.to_label) + '</button></div>';
        dlg.querySelector('#cp-save').onclick = function () { saveCopy(j, out); };
      }, function (e) { out.innerHTML = '<div class="msg bad">' + esc(e.message) + '</div>'; });
    };
  }

  function describeCopy(j, preview) {
    var items = [];
    (preview ? j.would_write : []).forEach(function (d) { items.push(describeDiff(j.block, d)); });
    var h = '';
    if (preview) {
      h += '<div class="msg"><b>' + j.would_write.length + '</b> change' + (j.would_write.length === 1 ? '' : 's') + ' to write onto ' + esc(j.to_label) + '.' +
        (j.param_writes_pending ? ' Knob values are worked out after the model is switched.' : '') + '</div>';
      if (items.length) h += '<ul class="list2">' + items.map(function (t) { return '<li>' + t + '</li>'; }).join('') + '</ul>';
      if (!j.would_write.length && !j.stuck.length) h += '<div class="msg good">Already the same. Nothing to copy.</div>';
    } else {
      h += '<div class="msg ' + (j.ok ? 'good' : 'bad') + '">' + (j.ok ? 'Done.' : 'Partly done.') + ' Wrote ' + j.written + ' change' + (j.written === 1 ? '' : 's') + ' to the edit buffer of ' + esc(j.to_label) + '. Not saved.</div>';
    }
    (j.stuck || []).concat(j.unwritten || []).forEach(function (d) {
      h += '<div class="msg bad">Could not copy ' + esc(d.field) + (d.index !== undefined ? ' ' + (d.index + 1) : '') + ': ' + esc(d.reason || 'the pedal did not take it') + '</div>';
    });
    return h;
  }

  function describeDiff(block, d) {
    if (d.field === 'power') return 'Switch ' + (d.want ? '<b>on</b>' : '<b>off</b>');
    if (d.field === 'model') return 'Model: ' + esc(modelName(block, d.have)) + ' \u2192 <b>' + esc(modelName(block, d.want)) + '</b>';
    if (d.field === 'level') return 'Patch level ' + d.have + ' \u2192 <b>' + d.want + '</b>';
    return 'Knob ' + (d.index + 1) + ': ' + d.have + ' \u2192 <b>' + d.want + '</b>';
  }

  function saveCopy(j, out) {
    var name = (j.note.match(/"name": "([^"]*)"/) || [])[1] || '';
    var want = 'SAVE ' + j.to_label;
    if (!window.confirm('Overwrite stored patch ' + j.to_label + (name ? ' (' + name + ')' : '') + ' with what is on the pedal now?')) return;
    api('/api/patch/save', { index: j.to, name: name, confirm: want }).then(function () {
      out.innerHTML += '<div class="msg good">Saved. The pedal sends nothing back for a save, so check its screen.</div>';
      refreshPresets();
    }, function (e) { out.innerHTML += '<div class="msg bad">' + esc(e.message) + '</div>'; });
  }

  // ---- backup, restore --------------------------------------------------------------------------

  function jobBar(j) {
    var bar = $('job-bar'), msg = $('job-msg');
    if (!bar) return;
    bar.hidden = false;
    bar.firstChild.style.width = (j.total ? Math.round(100 * j.done / j.total) : 0) + '%';
    msg.className = 'msg';
    msg.textContent = (j.step || 'Working') + ' (' + j.done + ' of ' + j.total + ')';
  }

  function startBackup() {
    $('do-backup').disabled = true;
    api('/api/backup', {}).then(function () { return pollJob(jobBar); }).then(function (j) {
      var r = j.result;
      $('job-msg').className = 'msg good';
      $('job-msg').textContent = 'Saved ' + r.name + ': ' + r.patches + ' patches' + (r.skipped.length ? ', ' + r.skipped.length + ' could not be read' : '') + '.';
      listBackups();
    }).catch(function (e) {
      var m = $('job-msg'); if (m) { m.className = 'msg bad'; m.textContent = e.message; }
    }).then(function () { var b = $('do-backup'); if (b) b.disabled = false; });
  }

  function listBackups() {
    api('/api/backups').then(function (r) {
      var ul = $('backups');
      if (!ul) return;
      ul.innerHTML = r.backups.map(function (b) {
        return '<li><span class="mono">' + esc(b.name) + '</span> <span class="chipx">' + Math.round(b.bytes / 1024) + ' KB</span>' +
          '<div class="row" style="margin-top:6px"><button type="button" class="pbtn" data-dl="' + esc(b.name) + '">Download</button><button type="button" class="pbtn" data-rs="' + esc(b.name) + '">Restore</button></div></li>';
      }).join('');
      ul.onclick = function (e) {
        var d = e.target.closest('[data-dl]'), r2 = e.target.closest('[data-rs]');
        if (d) download(d.dataset.dl);
        if (r2) openRestore({ name: r2.dataset.rs });
      };
    }, function () {});
  }

  function download(name) {
    api('/api/backups/' + encodeURIComponent(name), undefined, true).then(function (blob) {
      var a = document.createElement('a');
      a.href = URL.createObjectURL(blob); a.download = name;
      document.body.appendChild(a); a.click(); a.remove();
      setTimeout(function () { URL.revokeObjectURL(a.href); }, 5000);
    }, function (e) { note(e.message, true); });
  }

  // source: {name: "..."} for a file on the bridge, or the backup object itself
  function openRestore(source) {
    var body = source && source.name && Object.keys(source).length === 1 ? { name: source.name } : { backup: source };
    var dlg = document.createElement('dialog');
    dlg.innerHTML = '<form method="dialog" class="dlg"><h2>Restore patches</h2>' +
      '<p class="msg" id="rs-intro">First the bridge compares the file with the pedal. Nothing is written yet.</p>' +
      '<div id="rs-out" role="status"><div class="msg">Checking, one patch at a time. This takes a few minutes...</div></div>' +
      '<div class="bar" id="rs-bar"><i></i></div>' +
      '<label class="chk" id="rs-partial" hidden><input type="checkbox" id="rs-allow"><span>Also save patches that cannot be fully restored<small>Parts the bridge cannot write stay as they are on the pedal.</small></span></label>' +
      '<div class="row"><button type="button" class="pbtn danger" id="rs-go" disabled>Restore chosen patches</button><button class="pbtn" value="close">Close</button></div></form>';
    document.body.appendChild(dlg);
    dlg.addEventListener('close', function () { dlg.remove(); });
    dlg.showModal();
    var out = dlg.querySelector('#rs-out'), bar = dlg.querySelector('#rs-bar'), go = dlg.querySelector('#rs-go');
    var tick = function (j) { bar.firstChild.style.width = (j.total ? Math.round(100 * j.done / j.total) : 0) + '%'; };

    api('/api/restore', body).then(function () { return pollJob(tick); }).then(function (j) {
      bar.hidden = true;
      var rows = j.result.patches;
      out.innerHTML = rowsHtml(rows, true);
      dlg.querySelector('#rs-partial').hidden = !rows.some(function (r) { return r.stuck && r.stuck.length; });
      var update = function () { go.disabled = !out.querySelector('input[data-pick]:checked'); };
      out.onchange = update; update();
      go.onclick = function () {
        var picked = [].map.call(out.querySelectorAll('input[data-pick]:checked'), function (i) { return Number(i.dataset.pick); });
        if (!picked.length) return;
        if (!window.confirm('Overwrite ' + picked.length + ' stored patch' + (picked.length === 1 ? '' : 'es') + ' on the pedal with the ones from this file?')) return;
        go.disabled = true; bar.hidden = false; tick({ done: 0, total: 1 });
        out.innerHTML = '<div class="msg">Restoring. Do not touch the pedal until this finishes...</div>';
        dlg.querySelector('#rs-intro').textContent = 'Writing to the pedal.'; dlg.querySelector('#rs-partial').hidden = true; go.hidden = true;
        var req = { patches: picked, apply: true, confirm: 'RESTORE ' + picked.length + ' PATCHES', allow_partial: dlg.querySelector('#rs-allow').checked };
        if (body.name) req.name = body.name; else req.backup = body.backup;
        api('/api/restore', req).then(function () { return pollJob(tick); }).then(function (j2) {
          bar.hidden = true; out.innerHTML = rowsHtml(j2.result.patches, false);
        }, function (e) { bar.hidden = true; out.innerHTML = '<div class="msg bad">' + esc(e.message) + '</div>'; });
      };
    }, function (e) { bar.hidden = true; out.innerHTML = '<div class="msg bad">' + esc(e.message) + '</div>'; });
  }

  var STATUS_TEXT = { same: ['same', 'ok'], differs: ['differs', 'warn'], failed: ['failed', 'bad'], restored: ['restored', 'ok'], 'not-saved': ['not saved', 'bad'], 'saved-partial': ['saved, partly', 'warn'] };

  function rowsHtml(rows, pick) {
    var differs = rows.filter(function (r) { return r.status === 'differs'; }).length;
    var h = pick ? '<div class="msg">' + rows.length + ' patches checked, ' + differs + ' differ from the file. Tick the ones to restore.</div>' : '';
    h += '<ul class="list2">' + rows.map(function (r) {
      var st = STATUS_TEXT[r.status] || [r.status, ''];
      var box = pick ? '<label class="chk" style="margin:-4px 0"><input type="checkbox" data-pick="' + r.index + '"' + (r.status === 'differs' ? ' checked' : '') + (r.status === 'failed' ? ' disabled' : '') + '><span><b>' + esc(r.label) + '</b> ' + esc(r.name) + '</span></label>' : '<b>' + esc(r.label) + '</b> ' + esc(r.name);
      var why = (r.stuck || []).slice(0, 4).map(function (d) { return '<span class="why">' + esc(d.slot.toUpperCase()) + ' ' + esc(d.field) + ': ' + esc(d.reason) + '</span>'; }).join('');
      return '<li>' + box + '<span class="chipx ' + st[1] + '">' + st[0] + '</span>' + (r.error ? '<span class="why">' + esc(r.error) + '</span>' : '') + why + '</li>';
    }).join('') + '</ul>';
    return h;
  }

  // ---- import -------------------------------------------------------------------------------------

  function importFile(file) {
    var out = $('import-out');
    out.innerHTML = '<div class="msg">Reading ' + esc(file.name) + '...</div>';
    if (/\.json$/i.test(file.name)) {
      readJson(file).then(openRestore, function (e) { out.innerHTML = '<div class="msg bad">' + esc(e.message) + '</div>'; });
      out.innerHTML = '';
      return;
    }
    if (file.size > 2000000) { out.innerHTML = '<div class="msg bad">That file is too big to be a preset file.</div>'; return; }
    file.arrayBuffer().then(function (buf) {
      var bytes = new Uint8Array(buf), bin = '';
      for (var i = 0; i < bytes.length; i += 8192) bin += String.fromCharCode.apply(null, bytes.subarray(i, i + 8192));
      return api('/api/import/prst', { filename: file.name, data: btoa(bin) });
    }).then(function (r) {
      var h = '';
      if (r.error) h += '<div class="msg bad">' + esc(r.error) + '</div>';
      else h += '<div class="msg">Found a Hotone preset file with <b>' + r.count + '</b> patch' + (r.count === 1 ? '' : 'es') + '.</div>' +
        '<ul class="list2">' + r.patches.slice(0, 120).map(function (p, i) { return '<li><b>' + (i + 1) + '</b> ' + esc(p.name || '(no name)') + '</li>'; }).join('') + '</ul>';
      h += '<div class="msg bad">' + esc(r.reason) + '</div>';
      out.innerHTML = h;
    }, function (e) { out.innerHTML = '<div class="msg bad">' + esc(e.message) + '</div>'; });
  }

  // ---- start --------------------------------------------------------------------------------------

  function start(hooks) {
    state.hooks = hooks || {};
    loadSettings();
    buildChrome();
    renderChrome();
    if (state.url && state.key) {
      api('/api/health').then(function () { state.connected = true; return loadFavorites(); }).then(changed, function () { state.connected = false; changed(); });
    }
  }

  window.AmperoBridge = {
    start: start,
    setModels: setModels,
    modelStarHtml: modelStarHtml,
    modelPasses: modelPasses,
    detailsOn: function () { return state.features.details; }
  };
})();
