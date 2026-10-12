# ampero-bridge: server-side param validation spec

Why: a param write that is in range for the 7-bit frame but wrong for the param (a three-position control written 65, an out-of-range enum) can crash the pedal, and the bridge used to answer ok:true. This document is the design for refusing those writes before they reach USB.

Status: phase 1 (rule table, `GET /api/rules`, 7-bit validation with 422 rejects) is implemented in `paramrules.py`. Phases 2 to 4 (restore guard, 14-bit frame, packed cab fields) are not built.

## 1. What exists today

- `ampero_mini.param_set(slot, model_code, param, value)`: only checks slot name, model code fits 14 bits, param 0-127, value 0-127 (`_check7`). The frame always sends value HI = 0x00, so a 14-bit write cannot be sent at all.
- `POST /api/param` (server.py `handle_post`): calls `param_set` and sends. No model check against what the slot holds, no per-param range, no encoding.
- `POST /api/model` is gated by `PROVEN_MODELS` (good; keep).
- `records.why_not()` (used by restore, block copy, backup): a param diff is writable if slot != cab-index>=4 and 0 <= want <= 127. Any index 0-13 passes, whether or not the model has that param.
- `docs/param-map.json` already holds per-model, per-param: record_offset, status (write-verified / address-confirmed-only / inferred / unswept / editor-defined), `written` values, `valid_range` (only ~23 params), `encoding` (only Sweller attack), `editor_enum`, `editor_display_range`, and editor_definition with raw Min/Max/valueType. The server does not load it; only a test checks it. It is the natural rule source.

Net effect: every write that reaches the pedal today is "integer 0-127". That is why Magic T Treble = 65 went through with ok:true.

## 2. Design: one rule table, built from param-map.json at startup

New module `paramrules.py` (pure, no I/O, unit-testable). At import it loads docs/param-map.json (copy baked into the image, already is) plus a small hand-written overrides file `docs/param-rules.json` that wins over anything derived. Output: `RULES[(slot, model_code, param)] -> Rule`.

Rule fields:
- `kind`: one of `range7`, `enum`, `switch`, `wide14`, `packed`, `blocked`
- `raw_min`, `raw_max` (inclusive, wire value)
- `allowed` (explicit list, for enum/switch)
- `encode` (optional display -> raw function, see section 3)
- `trust`: `proven` | `unverified` | `unknown`

Derivation (when no override exists):
1. `editor_enum` present -> `enum`, allowed = the enum values.
2. editor control_type Switch -> `switch`, allowed {0,1}.
3. Knob/Slider with display range and no Min/Max/valueType attributes -> `range7`, raw 0..DisplayMax (usually 0-100).
4. Knob with editor `Min`/`Max` attributes or `valueType` (raw differs from display) -> NOT derived. Needs an override, else `blocked`.
5. `valid_range` in the map overrides 3. `written` values never widen a rule (only 0/50/100 were tried, that proves an address, not a range).
6. TextEditor, unswept, or no entry -> `blocked`.

Trust policy (env `AMPERO_VALIDATE=strict|warn|off`, default strict):
- `proven` (status write-verified AND rule fully defined): accept inside range.
- `unverified` (address-confirmed-only, inferred, editor-defined): accept only inside the rule range AND only if request carries `"unverified_ok": true`; default reject. Rationale: the earlier crash was an unverified-semantics write. Flip a block to allowed in the override file after a screen check.
- `blocked`/unknown: reject always (message points at docs/knobs.md).
- `warn` mode logs the would-be rejection and sends anyway (for rollout/A-B vs callers's flow). `off` = old behavior. Default strict since the whole point is protection.

## 3. Encoding rules for the known gaps

All wire values are what goes into the param frame HI/LO (14-bit: HI = v>>7, LO = v&0x7F) and what shows in the record at `record_offset` (lo byte, hi byte follows).

| Param | Editor display | Wire/raw | Rule | Confidence |
|---|---|---|---|---|
| Magic T p3 (fx1 code 77, fx2 code 13) | map labels it Treble knob 0-100 | param-map `written` is [0,1,2] (not 0/50/100 like Gain/Vol/Bass) | `enum` allowed {0,1,2}; reject anything else, including 65 | High that 0-2 is safe. **Naming conflict, see section 7** |
| Magic T p4 "Mode" | I/II/III enum 0-2, status editor-defined | untested | `enum` {0,1,2}, `unverified` | Low |
| 2290 Mod p2 Time (dly code 16) | 20-4000 ms | editor raw Min 0 Max 3980 (default 480). Same shape as Sweller (raw = ms - 20) | `wide14`, raw 0..3980, API accepts `value` (raw) or `ms` (display, bridge converts ms-20). Raw 0..3980 needs the 14-bit frame (see 4.2) | Medium: shape matches Sweller, not pedal-proven for 2290 |
| 2290 Mod p3 Mod Rate | 0.1-10 Hz | editor raw 0..990, step 0.01 | `wide14`, raw 0..990, `hz` convenience = (Hz-0.1)*100. `unverified` | Low-medium |
| 2290 p5/p6/p7 | Phase reverse 0-3, Low cut 0-3, High cut 0-3 | enums | `enum` 0..3, proven | High (editor enums, write-verified) |
| 2290 p9 Sync | switch | 0/1 | `switch`. Note: Sync on rewrites neighbor rate and Time becomes a division enum, see synced rate below | High |
| Sweller Attack (fx3 code 75, p0) | 80-4000 ms | raw = ms - 80, 0..3920, hi7 at 296 lo7 at 297 (read-back at 80/1000/4000) | `wide14`, raw 0..3920, proven for fx3. fx1 code 142 / fx2 code 126 Sweller: same shape per editor, but unverified | High for fx3, medium for others |
| Shimmer Lo End / Hi End (rvb code 9, p3 p4) | -50..+50 dial | editor Min 0 Max 100, default 30/40. Hypothesis raw = dial + 50 (matches default 30 = -20, 40 = -10) | `range7` raw 0..100, API also accepts `dial` -50..50 -> raw = dial+50. Mark `unverified` until one screen read-back | Medium |
| Slapback Time (dly code 9, p2) | 20-300 ms | editor raw Min 0 Max 280, default 130 | `wide14`-style but fits 7 bits: raw 0..127 safe today; 128..280 needs 14-bit frame. Likely raw = ms - 20. **Open: protocol.md says "130 ms was its default", the editor says raw default 130 (= 150 ms if raw = ms-20), and one saved preset was written with time 110**. Needs one screen check of what ms the pedal shows for a known raw. Until then rule is raw 0..280, `unverified` | Medium-low |
| Synced rates (Trem Jet, Shiver T, Jetter N, 13 fx2 models, 2290 time when Sync on) | 11-step division | stored = index*10 (0..100 step 10); writing 1 to a Sync param rewrites the neighbor rate | Rate rule is context dependent: if the record's Sync param is 1, rate must be in {0,10,...,100}. See 5 | High (map conventions) |
| Classic PS p0 (fx1 45, fx2 93, fx3 76) | enum | 0-5 | `enum` 0..5; value 6 wedges pedal. Already in `valid_range` | High |
| Mic type (cab p0) | enum 0-10 | 0..10 | `enum` from editor list, proven | High |
| Cab Volume, Position X/Y (cab p1-p3) | 0-100 | raw 0-100 | `range7` 0..100 | High (knobs.md checked) |
| Cab Position Z, Low Cut, High Cut (p4-6) | Z 0-100, cuts Hz | **packed bytes 12-16 of the cab block**, Z one byte; Low Cut 14 bit `(b13<<7)|b14`, Hz = v+19, 0=off, raw 0..1981; High Cut 14 bit, Hz = 2000+10v, 1801 = off (0..1801) | `packed`: `blocked` in `/api/param` until a multi-byte write path exists. Spec for that path: new endpoint field names `cab_z`, `low_cut_hz`, `high_cut_hz` that the bridge converts, because the generic p4/p5/p6 frame addressing does not map onto these bytes. Needs a pedal capture to prove the write frame, so it is a later phase | Not writable yet, correct to keep blocked |

Rule of thumb applied to every table row: where editor display range and wire raw differ (Min/Max/valueType attributes present), the rule table stores RAW, and the API takes raw by default. Optional convenience fields (`ms`, `hz`, `dial`) are converted server-side and echoed back in the response (`"raw": 3980, "from": {"ms": 4000}`) so the caller can see what was sent. Never accept display units under the plain `value` key.

## 4. Where the checks live

4.1 `paramrules.validate(slot, model_code, param, value, record=None)` returns the raw value (after any conversion) or raises `ValueRejected` (a `ProtocolError` subclass, HTTP 422).

4.2 `ampero_mini.param_set`: add `value` 14-bit support (`HI = v>>7, LO = v&0x7F`, error above 16383). Keep the 7-bit limit when the rule says `range7`. Frame layout already carries a HI byte, this only stops forcing it to 0. Wide writes ship only after pedal capture proves them for 2290 Time / Slapback; until then rules for values >127 stay `unverified` and rejected by default.

4.3 `POST /api/param` (server.py): ordering
 1. slot valid, model_code is in PROVEN_MODELS for that slot (reuse the `/api/model` gate).
 2. **Model-match check**: read the edit buffer (reads are unthrottled) and confirm the slot's current model == model_code. The pedal already ignores a mismatch silently, but a silent no-op that returns ok:true hides mistakes. Reject with `model_mismatch`, include actual code. Cost: one read per write; allow `"skip_read": true`? No, keep it mandatory in strict mode, but reuse a read cached by the history poller if under 2 s old.
 3. `paramrules.validate`.
 4. Sync context check for rate params (needs the record, same read as step 2).
 5. throttle + send (existing path).

4.4 `records.why_not()`: replace the `0..127` and `CAB_WRITABLE_PARAMS` branches by `paramrules.validate` using the target model. Restore, copy and backup converge then share the same checks. Add a `reason` code so stuck rows are machine-readable.

4.5 `/api/model`: unchanged, except after a model change the response includes `"params_reset": true` and the new rule summary for the slot (helps callers).

4.6 New read endpoint `GET /api/rules?slot=&model_code=` returns the rules (range/enum/encoding/trust) for a model. This is the "reconciled map for callers": one machine-readable answer to "what may I write", generated from the same table the server enforces, so doc and server cannot drift.

## 5. Error behavior

- HTTP 422 for validation failures, 409 `model_mismatch`, nothing is sent to USB and nothing is queued in the write throttle (rejects must not consume the 6-slot queue or the write gap).
- Body: `{"error": "...", "kind": "ValueRejected", "reason": "out_of_range|not_in_enum|blocked_param|unverified|wrong_model|sync_rate|not_14bit_proven", "slot", "model_code", "model", "param", "name", "value", "allowed": {"min":0,"max":2} or [0,1,2], "trust": "proven|unverified", "hint": "set unverified_ok to test, see /api/rules"}`.
- Bool, float, string numerics rejected (today `_int` coercion should be checked: reject `True`, `65.0`, `"65"`).
- Batch: not adding batch now. Keep one write per call so one bad value cannot take down a sequence mid-way. (Optional later: `POST /api/params` that validates ALL rows first, then sends all or none.)
- Log every reject (INFO) and every accepted unverified write (WARN) with caller, so a crash can be traced to the last accepted write.

## 6. Restore / converge guard (inactive-index problem)

Problem: `diffs()` compares all 14 param slots for a block whose model is unchanged. After a model change a block's record keeps leftover bytes in positions the new model does not use (and the wire can still hold e.g. 65 from the previous model). A restore then "fixes" those unused slots, sending raw leftovers to indices that may be undefined or now a different type.

Design:
1. `paramrules.active_params(slot, model_code)` = set of param indices defined in param-map/editor definitions for that model (e.g. Magic T: 0-4, Slapback: 0-3, 2290: 0-10; nr: 0-1; cab: 0-3 writable).
2. `records.diffs()` splits differences: indices in the active set go into the plan; indices outside it are dropped from the plan and listed in `report["ignored_inactive"]` (informational, with have/want). They are never written. They also do not count as "stuck" or "differs", so restore-check stays clean and idempotent.
3. For active indices, `why_not()` calls the full rule validation, using the WANT model's rules. A backup value that is out of range for its rule (e.g. Magic T p3 = 65 stored in an old patch) becomes `stuck` with the reason, never written. Row status already falls to `not-saved` (or `saved-partial` only when `partial_ok`). Make `partial_ok` skip only `stuck` for reasons `blocked`/`unverified`, not `out_of_range`/`not_in_enum` (a bad value in the source file should stop the save of that patch unless the user explicitly forces it).
4. Models with no entry in param-map (unknown): active set unknown -> treat block as `stuck: "no param map for model"` and write power/model only. No param writes.
5. Dry run (`apply` false) runs the same validation and reports `would_write`, `ignored_inactive`, `stuck` so the user sees rejects before anything touches the pedal. Recommend: require a dry run in the same session before `apply` (bridge stores a hash of the dry-run plan; apply with a different plan hash is refused). Optional, flagged as additional scope.
6. Re-read after model change already happens in converge (good). Add: after a model write, wait PEDAL_SETTLE and verify the slot model equals want before any param write; if not, abort that block.
7. Sync context: when want has Sync on, rate values must be division steps; when Sync off, free range. Apply per diff using the want record's Sync byte, and order writes Sync first, then rate (so the rate is not rewritten by the sync flip).

## 7. Open items to resolve before coding (need a human or the pedal)

1. **Magic T p3 naming.** param-map/editor call p3 "Treble" (knob 0-100) and p4 "Mode" (I/II/III), but the only live evidence for p3 is writes of 0, 1, 2, and the earlier crash was Treble = 65. Either the editor order differs from the wire order (p3 is really the 3-way switch) or the 0/1/2 sweep exercised a real knob. Spec makes p3 `enum {0,1,2}` for fx1 77 / fx2 13 until a screen check. Needs someone at the pedal: set Magic T on the screen and see which control is the 3-position one and what Treble raw is.
2. **Slapback / 2290 Time raw offset** (raw = ms - 20?) and whether the existing value 110 means 110 or 130 ms.
3. **Shimmer Lo/Hi** raw = dial + 50: one screen read.
4. **14-bit write frame** for Time/Mod Rate: confirm HI byte placement by one capture or one careful write on a throwaway patch (this is exactly the kind of write that needs the pedal, so it is separate from validation).
5. **Cab Z / cuts** packed write: needs Hotone editor capture (they were decoded from reads only).
6. `AMPERO_VALIDATE` default: spec recommends strict. Existing preset flows will start getting 422s for any param not proven; check his sheet values against `/api/rules` first.

## 8. Tests (add to tests/)

- Table-driven: every param in param-map.json has a rule or an explicit `blocked`; no param silently falls back to 0-127.
- Rejects: Magic T p3 = 3, 65, 100; Classic PS p0 = 6; Sweller raw 3921; 2290 time raw 3981; Shimmer raw 101; cab p4+; model_mismatch; bool/float/string values; unverified without flag.
- Accepts: previously proven writes from `written` lists replay green (regression guard against over-blocking).
- Throttle: rejects do not consume queue or gap (extend fakepedal test).
- Restore: leftover bytes in inactive index are ignored and reported, not written; out-of-range value in a backup becomes stuck; dry run matches apply plan.
- param-map consistency: docs/ and site/ copies equal (exists), plus overrides file only references existing models.

## 9. Suggested build order

1. paramrules.py + overrides + /api/rules + validation in /api/param (7-bit rules only; blocks everything wide/packed). Fast, closes the crash hole.
2. records.why_not / diffs guard (inactive index, rule checks).
3. After pedal evidence: 14-bit frame + Sweller/2290/Slapback/Shimmer conversions.
4. Packed cab fields.
