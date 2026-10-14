/* Tone panel: dial in one block of the patch the pedal has selected, from the browser.

   Every control change is one write to the bridge's edit buffer, followed by a read back.
   Nothing here saves, backs up or restores. The ranges come from the bridge itself
   (GET /api/rules), so a control cannot offer a value the bridge would refuse.
   The pure parts (record parsing, control specs, checks) are exported for the tests. */
(function (root, factory) {
  var api = factory();
  if (typeof module === 'object' && module.exports) module.exports = api;
  else root.AmperoTone = api;
})(this, function () {
  'use strict';

  var OFFSETS = { fx1: 95, fx2: 128, amp: 161, nr: 194, cab: 227, eq: 260, fx3: 293, dly: 326, rvb: 359 };
  var BLOCKS = [{ slot: 'amp', key: 'AMP', label: 'Amp' }, { slot: 'cab', key: 'CAB', label: 'Cab' },
    { slot: 'fx1', key: 'FX1', label: 'FX1' }, { slot: 'fx2', key: 'FX2', label: 'FX2' }, { slot: 'fx3', key: 'FX3', label: 'FX3' },
    { slot: 'dly', key: 'DLY', label: 'Delay' }, { slot: 'rvb', key: 'RVB', label: 'Reverb' },
    { slot: 'nr', key: 'NR', label: 'Noise gate' }, { slot: 'eq', key: 'EQ', label: 'EQ' }];
  var SWELLER = 75, PARA_EQ = 4, UNPAIRED = -1;
  var PARAM_SLOTS = 14, RECORD_LEN = 460, GAP_MS = 700, SETTLE_MS = 900;

  function patchLabel(i) { return 'P' + (Math.floor(i / 3) + 1) + '-' + (i % 3 + 1); }

  function parseRecord(hex) {
    if (typeof hex !== 'string' || hex.length !== RECORD_LEN * 2 || /[^0-9a-f]/i.test(hex)) throw new Error('The pedal sent a patch record this page cannot read.');
    var b = [], i;
    for (i = 0; i < hex.length; i += 2) b.push(parseInt(hex.substr(i, 2), 16));
    var name = '';
    for (i = 4; i < 22 && b[i]; i++) name += String.fromCharCode(b[i]);
    var out = { index: b[1], label: patchLabel(b[1]), name: name, blocks: {} };
    Object.keys(OFFSETS).forEach(function (slot) {
      var o = OFFSETS[slot], code = b[o + 1] * 128 + b[o + 2];
      out.blocks[slot] = { on: b[o] === 1, code: code, params: decodeParams(b, slot, o, code) };
    });
    return out;
  }

  /* The same field ownership as records.decode_params in the bridge (2.9.3). Most params are two bytes,
     low first. Delay Feedback is one byte and Time is 14 bits right after it. Sweller Attack is 14 bits,
     high half before slot 0. Cab Z is one byte and the two cuts are 14 bits. Para EQ has a 15th control,
     Volume, as the last byte of its block. */
  function decodeParams(b, slot, o, code) {
    var params = [], wide = function (hi, lo) { return b[o + hi] * 128 + b[o + lo]; };
    for (var p = 0; p < PARAM_SLOTS; p++) params.push(b[o + 4 + 2 * p] | (b[o + 5 + 2 * p] << 8));
    if (slot === 'dly') { params[1] = b[o + 6]; params[2] = wide(7, 8); }
    else if (slot === 'fx3' && code === SWELLER) params[0] = wide(3, 4);
    else if (slot === 'cab') { params[4] = b[o + 12]; params[5] = wide(13, 14); params[6] = wide(15, 16); }
    else if (slot === 'eq' && code === PARA_EQ) params.push(b[o + 32]);
    return params;
  }

  function modelsFor(data, key) {
    var hit = ((data && data.blocks) || []).filter(function (b) { return b.block === key; })[0];
    return hit ? hit.models.filter(function (m) { return m.code !== null && m.code !== undefined; }) : [];
  }

  function findModel(data, key, code) {
    return modelsFor(data, key).filter(function (m) { return m.code === code; })[0] || null;
  }

  function optionLabels(model, position) {
    var p = model && (model.parameters || []).filter(function (x) { return x.position === position; })[0];
    return p && p.selector_items ? p.selector_items.map(function (s) { return typeof s === 'string' ? s : (s.Name || s.label || ''); }) : [];
  }

  // Notes the bridge leaves over from deriving a rule that a hand-written rule then replaced.
  function cleanNote(n) { return n && n !== 'no range in the map' ? n : ''; }

  /* One control description per param, from the bridge's rule for it.
     verifyMode is the bridge's own verify_mode flag from /api/rules. A param the strict rules block but
     the vendor editor documents (rule.verify_range) is only offered when it is true, and is written with
     verify:true. So is a Rate that follows a Sync switch, because only verify mode checks that pairing. */
  function controlSpec(rule, labels, verifyMode) {
    if (!rule) return { type: 'blocked', note: 'The bridge cannot write this one yet.' };
    var viaVerify = false, kind = rule.kind, trust = rule.trust === 'proven' ? 'verified' : 'unverified', lo = rule.min, hi = rule.max, allowed = rule.allowed;
    if (kind === 'blocked') {
      if (!(verifyMode && rule.verify_range)) return { type: 'blocked', note: rule.note || 'The bridge cannot write this one yet.' };
      viaVerify = true; trust = 'verify mode'; rule = Object.assign({}, rule, { note: '' });
      if (rule.verify_range.allowed) { kind = 'enum'; allowed = rule.verify_range.allowed; }
      else { kind = 'range'; lo = rule.verify_range.min; hi = rule.verify_range.max; }
    }
    if (rule.editor_raw_max) return { type: 'blocked', note: 'A 14-bit value (0 to ' + rule.editor_raw_max + '). This field uses a wider encoding that is not enabled.' };
    var syncNote = '';
    if (verifyMode && rule.sync_param !== undefined && rule.sync_param !== null) {
      if (rule.sync_param === UNPAIRED) return { type: 'blocked', note: 'The map cannot tie this Rate to one Sync switch, so verify mode will not write it.' };
      viaVerify = true;
      syncNote = rule.synced_values && rule.synced_values.length ? 'With Sync on, this control takes only the steps ' + rule.synced_values.join(', ') + '. The bridge reads Sync first.' : 'Synced values are not captured for this model. Turn Sync off before writing this control.';
    }
    var note = [cleanNote(rule.note), syncNote].filter(Boolean).join(' ');
    if (kind === 'enum') {
      return {
        type: 'enum', trust: trust, verify: viaVerify, note: note,
        options: (allowed || []).map(function (v) { return { value: v, label: labels && labels.length > v && labels[v] ? labels[v] : String(v) }; })
      };
    }
    return { type: 'range', trust: trust, verify: viaVerify, min: lo, max: hi, note: note, wide: null };
  }

  /* A preflight only. The bridge decides; this just avoids sending a value it will refuse. */
  function checkValue(spec, raw) {
    if (spec.type === 'blocked') return 'This param cannot be written.';
    var text = String(raw === null || raw === undefined ? '' : raw).trim();
    if (!/^-?\d+$/.test(text)) return 'Enter a whole number.';
    var v = Number(text);
    if (spec.type === 'enum') {
      return spec.options.some(function (o) { return o.value === v; }) ? null : 'Pick one of the listed values.';
    }
    return v >= spec.min && v <= spec.max ? null : 'Use a value from ' + spec.min + ' to ' + spec.max + '.';
  }

  /* What the pedal reports for one param after a write. */
  function readBack(parsed, slot, code, param, want) {
    var blk = parsed.blocks[slot];
    if (!blk) return { ok: false, text: 'That block is not in the record.' };
    if (blk.code !== code) return { ok: false, text: 'The pedal now holds model ' + blk.code + ', not ' + code + '.' };
    var got = blk.params[param];
    return got === want ? { ok: true, text: 'Read back ' + got + '. Matches.' } : { ok: false, text: 'The pedal reports ' + got + ', not ' + want + '.' };
  }

  function errorText(e) {
    var d = e && e.detail;
    if (d && d.reason) {
      var r = d.rule || {}, bits = [e.message];
      if (r.allowed) bits.push('Allowed: ' + r.allowed.join(', ') + '.');
      else if (r.min !== undefined) bits.push('Range: ' + r.min + ' to ' + r.max + '.');
      bits.push('(' + d.reason + ')');
      return bits.join(' ');
    }
    return (e && e.message) || 'Something went wrong.';
  }

  function sleep(ms) { return new Promise(function (r) { setTimeout(r, ms); }); }

  /* ---- the panel -------------------------------------------------------------------- */

  function mount(el, ctx) {
    var S = { slot: 'amp', patch: null, rules: null, spec: {}, code: null, busy: false, status: '', bad: false, last: 0, verifyMode: false };
    var esc = ctx.esc;

    function blockInfo() { return BLOCKS.filter(function (b) { return b.slot === S.slot; })[0]; }
    function say(text, bad) { S.status = text; S.bad = !!bad; var m = el.querySelector('#tone-status'); if (m) { m.textContent = text; m.className = 'msg' + (bad ? ' bad' : ''); } }

    function pace() {
      var wait = Math.max(0, S.last + GAP_MS - Date.now());
      return sleep(wait);
    }
    function call(path, body) { return pace().then(function () { return ctx.api(path, body); }).then(function (r) { S.last = Date.now(); return r; }, function (e) { S.last = Date.now(); throw e; }); }

    function lock(on) {
      S.busy = on;
      [].forEach.call(el.querySelectorAll('button, select, input'), function (n) { n.disabled = on; });
    }

    function readPatch() {
      return call('/api/patch/current').then(function (rec) { S.patch = parseRecord(rec.record_hex); return S.patch; });
    }

    function loadRules(code) {
      return ctx.api('/api/rules?slot=' + encodeURIComponent(S.slot) + '&model_code=' + code).then(function (r) { S.rules = r; return r; });
    }

    function buildSpecs() {
      S.verifyMode = S.rules.verify_mode === true;
      var model = findModel(ctx.models(), blockInfo().key, S.code);
      S.spec = {};
      Object.keys(S.rules.params).forEach(function (p) {
        S.spec[p] = controlSpec(S.rules.params[p], optionLabels(model, Number(p)), S.verifyMode);
      });
    }

    function refresh() {
      lock(true);
      say('Reading the pedal...');
      return readPatch().then(function (rec) {
        S.code = rec.blocks[S.slot].code;
        return loadRules(S.code).then(buildSpecs, function (e) { S.rules = null; S.spec = {}; if (e.status !== 404) throw e; });
      }).then(function () { render(); say('Read from the pedal.'); }, function (e) { render(); say(errorText(e), true); }).then(function () { lock(false); });
    }

    function modelOptions() {
      return modelsFor(ctx.models(), blockInfo().key).map(function (m) {
        var tag = m.status && m.status !== 'pedal-proven' ? ' (not proven)' : '';
        return '<option value="' + m.code + '"' + (m.code === S.code ? ' selected' : '') + '>' + esc(m.name + tag) + ' [' + m.code + ']</option>';
      }).join('');
    }

    function paramRow(p) {
      var spec = S.spec[p], blk = S.patch.blocks[S.slot], cur = blk.params[Number(p)];
      var name = (S.rules.params[p] && S.rules.params[p].name) || ('Param ' + p);
      var h = '<div class="trow" data-p="' + p + '"><div class="thead"><b>' + esc(name) + '</b><span class="tchips"><span class="chipx ' + (spec.trust === 'verified' ? 'ok' : spec.trust ? 'warn' : '') + '">' + esc(spec.trust || 'blocked') + '</span>' + (spec.verify ? '<span class="chipx warn">verify:true</span>' : '') + '</span></div>';
      if (spec.type === 'blocked') return h + '<div class="msg">' + esc(spec.note) + '</div></div>';
      h += '<div class="tctl">';
      if (spec.type === 'enum') {
        h += '<select id="tone-p' + p + '" aria-label="' + esc(name) + '">' + spec.options.map(function (o) {
          return '<option value="' + o.value + '"' + (o.value === cur ? ' selected' : '') + '>' + esc(o.label + ' (' + o.value + ')') + '</option>';
        }).join('') + '</select>';
      } else {
        var v = Math.min(Math.max(cur, spec.min), spec.max);
        h += '<input type="range" id="tone-r' + p + '" min="' + spec.min + '" max="' + spec.max + '" value="' + v + '" aria-label="' + esc(name) + ' slider">' +
          '<input type="number" inputmode="numeric" id="tone-p' + p + '" min="' + spec.min + '" max="' + spec.max + '" step="1" value="' + cur + '" aria-label="' + esc(name) + '">';
      }
      h += '<button type="button" class="pbtn" id="tone-set' + p + '" data-set="' + p + '">Set</button></div>';
      h += '<div class="msg">' + (spec.type === 'range' ? 'Range ' + spec.min + ' to ' + spec.max + '. ' : '') + 'Pedal has <span id="tone-cur' + p + '">' + cur + '</span>. ' + esc(spec.note || '') +
        (spec.verify ? ' Written in verify mode.' : '') + '</div><div class="msg" id="tone-m' + p + '" role="status"></div></div>';
      return h;
    }

    function render() {
      if (!ctx.connected()) { el.innerHTML = '<div class="panel"><p>Connect the bridge under Settings to use the tone editor.</p></div>'; return; }
      var info = blockInfo(), h = '<div class="tbanner" role="note"><b>Edit buffer only.</b> Changes here are not saved to the pedal. Re-select the patch on the pedal to discard them.</div>';
      h += '<div class="panel tpatch"><div><span class="lbl" id="tone-patch-label">' + (S.patch ? esc(S.patch.label) : '-') + '</span> <span id="tone-patch-name">' + (S.patch ? esc(S.patch.name) : 'not read yet') + '</span></div>' +
        '<button type="button" class="pbtn" id="tone-refresh">Read from pedal</button></div>';
      h += '<div class="sect">Block</div><div class="seg" role="group" aria-label="Block">' + BLOCKS.map(function (b) {
        return '<button type="button" class="pbtn' + (b.slot === S.slot ? ' pri' : '') + '" data-block="' + b.slot + '" aria-pressed="' + (b.slot === S.slot) + '">' + b.label + '</button>';
      }).join('') + '</div>';
      if (S.patch) {
        var blk = S.patch.blocks[S.slot];
        h += '<div class="sect">Model</div><div class="panel"><div class="tctl"><select id="tone-model" aria-label="' + info.label + ' model">' + modelOptions() + '</select>' +
          '<button type="button" class="pbtn pri" id="tone-model-set">Set model</button></div>' +
          '<div class="msg">' + info.label + ' block is ' + (blk.on ? 'on' : 'off') + ' on the pedal. Setting a model resets that block\'s knobs to the model defaults.</div></div>';
        h += '<div class="sect">Parameters</div>';
        if (S.verifyMode) h += '<div class="msg">Verify mode is on for this bridge. Params marked verify:true are checked against the vendor ranges, and a synced Rate takes only division steps.</div>';
        h += S.rules ? Object.keys(S.spec).sort(function (a, b) { return a - b; }).map(paramRow).join('') : '<div class="empty">No rules for this model.</div>';
      }
      h += '<div class="msg" id="tone-status" role="status"></div>';
      el.innerHTML = h;
      var s = el.querySelector('#tone-status'); s.textContent = S.status; s.className = 'msg' + (S.bad ? ' bad' : '');
    }

    function setModel() {
      var sel = el.querySelector('#tone-model'), code = Number(sel.value);
      lock(true);
      say('Setting model ' + code + '...');
      call('/api/model', { slot: S.slot, code: code }).then(function () { return sleep(SETTLE_MS); })
        .then(readPatch).then(function (rec) {
          var got = rec.blocks[S.slot].code;
          S.code = got;
          return loadRules(got).then(buildSpecs).then(function () { return got; });
        }).then(function (got) {
          render();
          say(got === code ? 'Model confirmed: the pedal reports ' + got + '.' : 'The pedal reports model ' + got + ', not ' + code + '.', got !== code);
        }, function (e) { render(); say(errorText(e), true); }).then(function () { lock(false); });
    }

    function setParam(p) {
      var spec = S.spec[p], input = el.querySelector('#tone-p' + p), raw = input.value, msg = el.querySelector('#tone-m' + p);
      var bad = checkValue(spec, raw);
      if (bad) { msg.textContent = bad; msg.className = 'msg bad'; return; }
      var value = Number(raw), code = S.code;
      lock(true);
      msg.textContent = 'Writing...'; msg.className = 'msg';
      call('/api/param', (function () { var b = { slot: S.slot, model_code: code, param: Number(p), value: value }; if (spec.verify) b.verify = true; else b.unverified_ok = true; return b; })())
        .then(function () { return sleep(SETTLE_MS); }).then(readPatch).then(function (rec) {
          var r = readBack(rec, S.slot, code, Number(p), value);
          msg.textContent = r.text; msg.className = 'msg ' + (r.ok ? 'good' : 'bad');
          var cur = el.querySelector('#tone-cur' + p); if (cur) cur.textContent = String(rec.blocks[S.slot].params[Number(p)]);
          S.status = '';
        }, function (e) { msg.textContent = errorText(e); msg.className = 'msg bad'; }).then(function () { lock(false); });
    }

    el.addEventListener('click', function (e) {
      if (S.busy) return;
      var t = e.target.closest('button');
      if (!t) return;
      if (t.id === 'tone-refresh') refresh();
      else if (t.id === 'tone-model-set') setModel();
      else if (t.dataset.set !== undefined) setParam(t.dataset.set);
      else if (t.dataset.block) { S.slot = t.dataset.block; S.rules = null; S.spec = {}; S.code = null; S.status = ''; refresh(); }
    });
    el.addEventListener('input', function (e) {
      var id = e.target.id || '', p;
      if (/^tone-r\d+$/.test(id)) { p = id.slice(6); var n = el.querySelector('#tone-p' + p); if (n) n.value = e.target.value; }
      else if (/^tone-p\d+$/.test(id) && e.target.type === 'number') { p = id.slice(6); var r = el.querySelector('#tone-r' + p); if (r) r.value = e.target.value; }
    });

    return { show: function () { render(); if (ctx.connected()) refresh(); }, state: S };
  }

  return { parseRecord: parseRecord, modelsFor: modelsFor, findModel: findModel, controlSpec: controlSpec, decodeParams: decodeParams, checkValue: checkValue,
    readBack: readBack, errorText: errorText, optionLabels: optionLabels, patchLabel: patchLabel, mount: mount, BLOCKS: BLOCKS, OFFSETS: OFFSETS };
});
