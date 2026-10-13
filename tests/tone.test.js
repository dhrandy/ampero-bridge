// Run with: node tests/tone.test.js   (the pytest wrapper tests/test_tone_js.py does this)
const assert = require('assert');
const fs = require('fs');
const path = require('path');
const T = require('../site/tone.js');

function recordHex(blocks, idx, name) {
  const b = new Array(460).fill(0);
  b[0] = 1; b[1] = idx;
  for (let i = 0; i < name.length; i++) b[4 + i] = name.charCodeAt(i);
  Object.keys(blocks).forEach((slot) => {
    const o = T.OFFSETS[slot], [on, code, params] = blocks[slot];
    b[o] = on ? 1 : 0; b[o + 1] = code >> 7; b[o + 2] = code & 127;
    params.forEach((v, i) => { b[o + 4 + 2 * i] = v & 255; b[o + 5 + 2 * i] = v >> 8; });
  });
  return b.map((x) => x.toString(16).padStart(2, '0')).join('');
}

const rec2 = (slot, code, set) => { const b = recordHex({ [slot]: [true, code, []] }, 3, 'T').match(/../g).map((h) => parseInt(h, 16)); set(b, T.OFFSETS[slot]); return b.map((x) => x.toString(16).padStart(2, '0')).join(''); };
const tests = [];
const test = (name, fn) => tests.push([name, fn]);

test('parseRecord reads index, name, model code and params', () => {
  const r = T.parseRecord(recordHex({ amp: [true, 2, [10, 20, 30, 40, 50, 1]], cab: [false, 34, [9, 50]] }, 75, 'DEMO'));
  assert.strictEqual(r.index, 75); assert.strictEqual(r.label, 'P26-1'); assert.strictEqual(r.name, 'DEMO');
  assert.strictEqual(r.blocks.amp.code, 2); assert.strictEqual(r.blocks.amp.on, true);
  assert.deepStrictEqual(r.blocks.amp.params.slice(0, 6), [10, 20, 30, 40, 50, 1]);
  assert.strictEqual(r.blocks.cab.code, 34); assert.strictEqual(r.blocks.cab.on, false);
});

test('parseRecord handles a model code above 127 and a two-byte param', () => {
  const r = T.parseRecord(recordHex({ amp: [true, 192, [300]] }, 0, 'X'));
  assert.strictEqual(r.blocks.amp.code, 192); assert.strictEqual(r.blocks.amp.params[0], 300);
});

test('parseRecord refuses a bad record', () => {
  assert.throws(() => T.parseRecord('abcd'));
  assert.throws(() => T.parseRecord(null));
  assert.throws(() => T.parseRecord('zz'.repeat(460)));
});

test('controlSpec: range, enum with labels, blocked', () => {
  const range = T.controlSpec({ kind: 'range', min: 0, max: 100, trust: 'proven' });
  assert.deepStrictEqual([range.type, range.min, range.max, range.trust], ['range', 0, 100, 'verified']);
  const en = T.controlSpec({ kind: 'enum', allowed: [0, 1, 2], trust: 'proven', note: 'wire values are 0/1/2' }, ['Cool', 'Hot']);
  assert.deepStrictEqual(en.options.map((o) => o.label), ['Cool', 'Hot', '2']);
  assert.strictEqual(en.note, 'wire values are 0/1/2');
  assert.strictEqual(T.controlSpec({ kind: 'blocked', note: 'packed' }).type, 'blocked');
  assert.strictEqual(T.controlSpec(undefined).type, 'blocked');
  const wide = T.controlSpec({ kind: 'range', min: 0, max: 127, trust: 'unverified', editor_raw_max: 3980 });
  assert.strictEqual(wide.type, 'blocked'); assert.ok(wide.note.includes('14-bit'));
  assert.strictEqual(T.controlSpec({ kind: 'range', min: 0, max: 5, trust: 'unverified' }).trust, 'unverified');
});

test('a leftover derive note is not shown', () => {
  assert.strictEqual(T.controlSpec({ kind: 'range', min: 0, max: 100, trust: 'proven', note: 'no range in the map' }).note, '');
});

test('checkValue holds to the enforced range and enum', () => {
  const range = T.controlSpec({ kind: 'range', min: 0, max: 100, trust: 'proven' });
  assert.strictEqual(T.checkValue(range, '55'), null);
  assert.strictEqual(T.checkValue(range, 0), null);
  assert.ok(T.checkValue(range, '101')); assert.ok(T.checkValue(range, '-1'));
  assert.ok(T.checkValue(range, '5.5')); assert.ok(T.checkValue(range, '')); assert.ok(T.checkValue(range, 'abc'));
  const en = T.controlSpec({ kind: 'enum', allowed: [0, 1, 2], trust: 'proven' });
  assert.strictEqual(T.checkValue(en, '2'), null);
  assert.ok(T.checkValue(en, '65'));
  assert.ok(T.checkValue({ type: 'blocked' }, '1'));
});

test('readBack confirms a match and flags a mismatch or a changed model', () => {
  const r = T.parseRecord(recordHex({ amp: [true, 2, [10, 20, 30]] }, 1, 'A'));
  assert.strictEqual(T.readBack(r, 'amp', 2, 1, 20).ok, true);
  assert.strictEqual(T.readBack(r, 'amp', 2, 1, 21).ok, false);
  assert.strictEqual(T.readBack(r, 'amp', 3, 1, 20).ok, false);
});

test('errorText shows the server reason and the allowed values', () => {
  const e = Object.assign(new Error('65 is not allowed for Treble'), { status: 422, detail: { reason: 'not_in_enum', rule: { allowed: [0, 1, 2] } } });
  const t = T.errorText(e);
  assert.ok(t.includes('65 is not allowed') && t.includes('0, 1, 2') && t.includes('not_in_enum'));
  const r = Object.assign(new Error('out'), { detail: { reason: 'out_of_range', rule: { min: 0, max: 100 } } });
  assert.ok(T.errorText(r).includes('0 to 100'));
  assert.strictEqual(T.errorText(new Error('Cannot reach')), 'Cannot reach');
});

test('modelsFor and optionLabels read models.json', () => {
  const data = JSON.parse(fs.readFileSync(path.join(__dirname, '..', 'site', 'models.json'), 'utf8'));
  const amps = T.modelsFor(data, 'AMP'), cabs = T.modelsFor(data, 'CAB');
  assert.strictEqual(amps.length, 60); assert.strictEqual(cabs.length, 70);
  const black = T.findModel(data, 'AMP', 2);
  assert.strictEqual(black.name, 'Black Twin');
  assert.deepStrictEqual(T.optionLabels(black, 5), ['Off', 'On']);
  assert.strictEqual(T.findModel(data, 'AMP', 9999), null);
});

test('the panel offers no save, backup or restore control', () => {
  const src = fs.readFileSync(path.join(__dirname, '..', 'site', 'tone.js'), 'utf8');
  assert.ok(!/\/api\/(patch\/save|backup|restore|block\/copy|midi)/.test(src));
  assert.ok(!/[\u2014\u2013]/.test(src));
});

test('every block is offered, amp and cab first', () => {
  assert.deepStrictEqual(T.BLOCKS.map((b) => b.slot), ['amp', 'cab', 'fx1', 'fx2', 'fx3', 'dly', 'rvb', 'nr', 'eq']);
  const data = JSON.parse(fs.readFileSync(path.join(__dirname, '..', 'site', 'models.json'), 'utf8'));
  const counts = {}; T.BLOCKS.forEach((b) => { counts[b.slot] = T.modelsFor(data, b.key).length; });
  assert.deepStrictEqual(counts, { amp: 60, cab: 70, fx1: 60, fx2: 60, fx3: 30, dly: 17, rvb: 11, nr: 2, eq: 7 });
  T.BLOCKS.forEach((b) => assert.ok(T.OFFSETS[b.slot] > 0));
});

test('decoders match the bridge: delay feedback and time, sweller attack, cab z and cuts, para eq volume', () => {
  let r = T.parseRecord(rec2('dly', 0, (b, o) => { b[o + 6] = 50; b[o + 7] = 3; b[o + 8] = 46; }));
  assert.strictEqual(r.blocks.dly.params[1], 50); assert.strictEqual(r.blocks.dly.params[2], 430);
  r = T.parseRecord(rec2('dly', 16, (b, o) => { b[o + 6] = 20; b[o + 7] = 3; b[o + 8] = 96; }));
  assert.deepStrictEqual([r.blocks.dly.params[1], r.blocks.dly.params[2]], [20, 480]);
  r = T.parseRecord(rec2('fx3', 75, (b, o) => { b[o + 3] = 7; b[o + 4] = 24; }));
  assert.strictEqual(r.blocks.fx3.params[0], 920);
  r = T.parseRecord(rec2('fx3', 6, (b, o) => { b[o + 3] = 7; b[o + 4] = 24; }));
  assert.strictEqual(r.blocks.fx3.params[0], 24);
  r = T.parseRecord(rec2('cab', 5, (b, o) => { b[o + 12] = 100; b[o + 13] = 15; b[o + 14] = 61; b[o + 15] = 14; b[o + 16] = 9; }));
  assert.deepStrictEqual(r.blocks.cab.params.slice(4, 7), [100, 1981, 1801]);
  r = T.parseRecord(rec2('eq', 4, (b, o) => { b[o + 32] = 50; }));
  assert.strictEqual(r.blocks.eq.params.length, 15); assert.strictEqual(r.blocks.eq.params[14], 50);
  r = T.parseRecord(rec2('eq', 1, (b, o) => { b[o + 32] = 50; }));
  assert.strictEqual(r.blocks.eq.params.length, 14);
});

const blockedRule = { kind: 'blocked', note: 'not swept', verify_range: { min: 0, max: 24 } };

test('verify-only params are offered only when the bridge reports verify mode', () => {
  assert.strictEqual(T.controlSpec(blockedRule, [], false).type, 'blocked');
  assert.strictEqual(T.controlSpec(blockedRule, undefined, undefined).type, 'blocked');
  const on = T.controlSpec(blockedRule, [], true);
  assert.deepStrictEqual([on.type, on.min, on.max, on.verify, on.trust], ['range', 0, 24, true, 'verify mode']);
  assert.strictEqual(T.checkValue(on, '24'), null); assert.ok(T.checkValue(on, '25'));
  const en = T.controlSpec({ kind: 'blocked', verify_range: { allowed: [0, 1] } }, [], true);
  assert.deepStrictEqual(en.options.map((o) => o.value), [0, 1]);
  assert.strictEqual(T.controlSpec({ kind: 'blocked', note: 'packed cab field' }, [], true).type, 'blocked');
});

test('a Rate that follows a Sync switch goes through verify mode and says so', () => {
  const rate = { kind: 'range', min: 0, max: 100, trust: 'proven', sync_param: 4, synced_values: [0, 10, 20] };
  const on = T.controlSpec(rate, [], true);
  assert.strictEqual(on.verify, true); assert.ok(on.note.includes('0, 10, 20'));
  const off = T.controlSpec({ kind: 'range', min: 0, max: 100, trust: 'proven' }, [], true);
  assert.strictEqual(off.verify, false);
  assert.strictEqual(T.controlSpec(Object.assign({}, rate, { sync_param: -1 }), [], true).type, 'blocked');
});

test('a normal param is not sent through verify mode', () => {
  assert.strictEqual(T.controlSpec({ kind: 'range', min: 0, max: 100, trust: 'unverified' }, [], true).verify, false);
});

test('the panel sends verify:true only for verify specs', () => {
  const src = fs.readFileSync(path.join(__dirname, '..', 'site', 'tone.js'), 'utf8');
  assert.ok(/if \(spec\.verify\) b\.verify = true; else b\.unverified_ok = true;/.test(src));
});

let failed = 0;
tests.forEach(([name, fn]) => { try { fn(); console.log('ok   ' + name); } catch (e) { failed++; console.log('FAIL ' + name + '\n' + e.stack); } });
process.exit(failed ? 1 : 0);
