"""Rules for what a param write may carry, so a bad value is refused before it reaches the pedal.

The table is built from docs/param-map.json plus explicit overrides. Values are raw wire
values, not display units. Only fields with a documented encoding get wider ranges; unrelated
wide controls remain capped. Read-confirmed fields stay unverified until a live write is checked.

    validate(slot, model_code, param, value, unverified_ok=False) -> value, or raises ValueRejected

Trust:
  proven      the map says write-verified: accepted inside the range.
  unverified  address-confirmed, inferred or editor-defined only: refused unless the caller says
              "unverified_ok": true.
  blocked     no safe rule (unswept, packed, unknown model or param): always refused.

AMPERO_VALIDATE=strict (default) refuses, warn logs and lets the write through, off skips the check.
"""
from __future__ import annotations

import json
import logging
import os

import ampero_mini as am

log = logging.getLogger("ampero-bridge")

MAX_RAW = 127   # default cap; only explicitly enabled encodings may exceed it
PROVEN, UNVERIFIED, BLOCKED, DOCUMENTED = "proven", "unverified", "blocked", "documented"
MODE = os.environ.get("AMPERO_VALIDATE", "strict").strip().lower()
if MODE not in ("strict", "warn", "off"):
    MODE = "strict"


# Verify mode (docs/verify-mode.md). Off unless AMPERO_VERIFY_MODE=1 and then only for a write that says
# "verify": true. It never changes the strict path above. It admits params whose range comes from the
# vendor editor database or manual (including ones the map still marks "unswept"), and it holds a
# synced Rate to the eleven division steps the map documents.
VERIFY_ENABLED = os.environ.get("AMPERO_VERIFY_MODE", "").strip() == "1"
DIVISIONS = [0, 10, 20, 30, 40, 50, 60, 70, 80, 90, 100]   # 1/1 .. 1/16 stored as index x 10
SYNC_ON = 1
UNPAIRED = -1          # a Rate in a model with a Sync switch the map cannot tie to it


class ValueRejected(am.ProtocolError):
    """A write the rule table refuses. Carries the detail the API puts in the 422 body."""

    def __init__(self, message: str, **extra):
        super().__init__(message)
        self.extra = extra


# Hand-written rules win over anything derived. Key: (slot, model_code, param).
# kind "enum" lists the allowed raw values, kind "range" gives raw lo..hi inclusive.
OVERRIDES: dict[tuple, dict] = {}
# Magic T Treble: both slots were live write/read-back verified on 2026-10-14.
OVERRIDES[("fx1", 77, 3)] = {"kind": "range", "lo": 0, "hi": 100, "trust": PROVEN,
    "note": "Treble 0-100; live writes 65, 0, 100, 50 read back exact 2026-10-14"}
# The editor documents the same Time layout for every delay. Analog Eko min/max and all
# divisions were read on the pedal. Other models retain their own editor maximum and Sync ID.
try:
    _editor_path = os.path.join(os.path.dirname(__file__), "docs", "editor-parameters.json")
    with open(_editor_path) as _f:
        _editor = json.load(_f)
    for _code, _model in _editor["blocks"]["dly"]["models"].items():
        _time = next(p for p in _model["params"] if p["name"] == "Time")
        _attrs = _time["editor_attributes"]
        _max = int(float(_attrs["Max"]))
        _sync = next((p["param"] for p in _model["params"] if p["name"] == _attrs.get("bind")), None)
        # Synced Time stores division index x (max / 10): eleven steps. Proven on Analog Eko
        # (0..3980 in steps of 398) 2026-10-14, then written and read back exact at all eleven
        # steps on every other 0-3980 model 2026-10-15. Backmask's 1980 ms maximum applies
        # only with Sync off: a hand capture on P12-2 (edit buffer, 2026-10-16) read all
        # eleven divisions live and every one sat on the shared 0-3980 grid, so its synced
        # scale is the same as every other delay and its synced range runs past 1980.
        _backmask = int(_code) == 6
        _steps = [i * 398 for i in range(11)] if (_max == 3980 or _backmask) else []
        # All 17 delay Time controls passed live writes at 100 and their maximum, Sync off.
        _rule = {"kind": "range", "lo": 0, "hi": 3980 if _backmask else _max, "trust": PROVEN,
            "encoding": "14bit", "note": "raw + 20 ms with Sync off; write-verified 2026-10-14; "
                "Sync off restores model default Time, not last value; " +
                ("synced writes 0, 398, 1592, 3980 verified; other divisions read-confirmed"
                 if int(_code) == 3 else
                 "no Sync control on this model" if _sync is None else
                 "all eleven synced divisions read live on the pedal 2026-10-16: shared 0-3980 "
                 "grid, past the 1980 ms Sync-off maximum"
                 if _backmask else
                 "synced writes at all eleven division steps verified 2026-10-15"
                 if _steps else
                 "synced Time unverified and refused: step scale for this maximum never read "
                 "on the pedal")}
        if _backmask:
            _rule["unsynced_hi"] = _max
        if _sync is not None:
            _rule.update(sync_param=_sync, synced_values=_steps, sync_required=True)
        OVERRIDES[("dly", int(_code), _time["param"])] = _rule
except (OSError, ValueError, KeyError, StopIteration) as error:
    log.error("delay wide rules unavailable: %s", error)
OVERRIDES[("fx3", 75, 0)] = {"kind": "range", "lo": 0, "hi": 3920, "trust": PROVEN,
    "encoding": "14bit", "note": "raw + 80 ms; live writes 100, 920, 3920, 0 read back exact 2026-10-14"}
# FX2 Sweller (code 126) Attack: same 0-3920 raw range, stored at bytes 131-132 of the record. The
# outgoing frame was captured from the official editor and bridge writes read back exactly.
OVERRIDES[("fx2", 126, 0)] = {"kind": "range", "lo": 0, "hi": 3920, "trust": PROVEN,
    "encoding": "14bit", "note": "raw + 80 ms; write-verified on the pedal 2026-10-14 (100, 920, 3920 read back exact)"}
# Shimmer Lo/Hi End: editor range -50..50 shown, raw 0-100 (probably dial + 50), not yet read on a screen.
for _p in (3, 4):
    OVERRIDES[("rvb", 9, _p)] = {"kind": "range", "lo": 0, "hi": 100, "trust": UNVERIFIED,
                                 "note": "raw 0-100, shown as -50..50; offset not confirmed on screen"}
# Cab fields own separate bytes; Z/cuts write-tested on seven cabs 2026-10-14, then
# swept on all 70 cab codes 2026-10-15 (490 writes, all read back exact, bytes identical).
for _p in (1, 2, 3):
    OVERRIDES[("cab", "ALL", _p)] = {"kind": "range", "lo": 0, "hi": 100, "trust": PROVEN}
for _p, _hi, _note in ((4, 100, "Position Z: raw = screen"),
        (5, 1981, "Low Cut: 0 = Off; otherwise raw + 19 Hz"),
        (6, 1801, "High Cut: 1801 = Off; otherwise 2000 + 10 * raw Hz")):
    OVERRIDES[("cab", "ALL", _p)] = {"kind": "range", "lo": 0, "hi": _hi, "trust": PROVEN,
        "encoding": "14bit" if _p > 4 else "7bit",
        "note": _note + "; write-verified 2026-10-14 on cab codes 0,13,25,49,112,144,153, then on all 70 cab codes 2026-10-15"}


def _map_path() -> str:
    here = os.path.dirname(os.path.abspath(__file__))
    return os.environ.get("AMPERO_PARAM_MAP") or os.path.join(here, "docs", "param-map.json")


def _num(text):
    try:
        return float(text)
    except (TypeError, ValueError):
        return None


def _derive(entry: dict) -> dict:
    """A rule from one param-map entry, or a blocked rule when the map cannot say."""
    status = entry.get("status")
    trust = PROVEN if status == "write-verified" else UNVERIFIED
    if status == "unswept":
        rule = {"kind": "blocked", "note": "not swept"}
        doc = _documented(entry)
        if doc:
            rule["verify_rule"] = doc
        return rule
    vr = entry.get("valid_range")
    enum = entry.get("editor_enum")
    ed = entry.get("editor_definition") or {}
    attrs = ed.get("editor_attributes") or {}
    ctype = ed.get("control_type")
    if enum:
        allowed = sorted({int(e["value"]) for e in enum})
        if allowed and max(allowed) <= MAX_RAW:
            return {"kind": "enum", "allowed": allowed, "trust": trust}
    if isinstance(vr, list) and len(vr) == 2:
        return {"kind": "range", "lo": int(vr[0]), "hi": int(vr[1]), "trust": trust}
    if ctype == "Switch":
        return {"kind": "enum", "allowed": [0, 1], "trust": trust}
    if ctype in ("Combox", "TextEditor") or ctype is None:
        return {"kind": "blocked", "note": "no range in the map"}
    lo, hi = _num(attrs.get("Min")), _num(attrs.get("Max"))
    if lo is None or hi is None:
        dlo, dhi = _num(attrs.get("DisplayMin")), _num(attrs.get("DisplayMax"))
        if dlo != 0 or dhi is None:
            return {"kind": "blocked", "note": "display range is not raw and no raw range is known"}
        lo, hi = 0.0, dhi
    lo, hi = int(lo), int(hi)
    if lo < 0 or hi < lo:
        return {"kind": "blocked", "note": "raw range is not usable"}
    if hi > MAX_RAW:
        # Wider than one 7-bit value. Cap it and never call it proven: the encoding is unconfirmed.
        return {"kind": "range", "lo": lo, "hi": MAX_RAW, "trust": UNVERIFIED, "wide": hi,
                "note": f"raw range is 0-{hi}; phase 1 sends 0-{MAX_RAW} only"}
    return {"kind": "range", "lo": lo, "hi": hi, "trust": trust}


def _documented(entry: dict) -> dict | None:
    """A range or enum taken from the vendor editor database, for an entry the map has not swept."""
    ed = entry.get("editor_definition")
    if not ed:
        return None
    probe = _derive({**entry, "status": "editor-defined", "valid_range": entry.get("valid_range")})
    if probe["kind"] not in ("range", "enum") or probe.get("wide"):
        return None
    return {**probe, "trust": DOCUMENTED, "note": "range from the vendor editor database, never written on the pedal"}


def build(map_path: str | None = None) -> dict:
    """{(slot, model_code, param): rule}. Cab entries are keyed with model_code 'ALL'."""
    path = map_path or _map_path()
    with open(path) as f:
        data = json.load(f)
    table = {}
    for slot, block in data["blocks"].items():
        for code, model in block["models"].items():
            key_code = "ALL" if code == "ALL" else int(code)
            for p, entry in model["params"].items():
                rule = _derive(entry)
                rule["name"] = entry.get("name")
                rule["model"] = model.get("name")
                table[(slot, key_code, int(p))] = rule
    for slot, block in data["blocks"].items():
        for code, model in block["models"].items():
            key_code = "ALL" if code == "ALL" else int(code)
            names = {int(p): e.get("name") for p, e in model["params"].items()}
            has_sync = any(n and "Sync" in n for n in names.values())
            for rp, rn in names.items():
                if not rn or not rn.endswith("Rate") or not has_sync:
                    continue
                # "Rate" pairs with "Sync", "Flg Rate" with "Flg Sync". Anything else is left unresolved,
                # and verify mode refuses a Rate it cannot pair (Sweep Eko, 2290 Mod).
                mine = [p for p, n in names.items() if n == rn[:-4] + "Sync"]
                table[(slot, key_code, rp)]["sync_param"] = mine[0] if len(mine) == 1 else UNPAIRED
    for key, rule in OVERRIDES.items():
        base = table.get(key, {})
        merged = {**base, **rule}
        if rule.get("encoding") or key in OVERRIDES:
            merged.pop("wide", None)
        table[key] = merged
    return table


try:
    RULES = build()
except (OSError, ValueError, KeyError) as e:      # no map: every write is refused, loudly
    log.error("param rules could not be built (%s): all param writes will be refused", e)
    RULES = {}


def rule_for(slot: str, model_code: int, param: int) -> dict | None:
    rule = RULES.get((slot, model_code, param))
    if rule is None and slot == "cab":
        rule = RULES.get((slot, "ALL", param))
    return rule


def _view(rule: dict) -> dict:
    out = {k: rule[k] for k in ("kind", "trust", "name", "note") if rule.get(k) is not None}
    if rule["kind"] == "range":
        out["min"], out["max"] = rule["lo"], rule["hi"]
        if rule.get("wide"):
            out["editor_raw_max"] = rule["wide"]
    elif rule["kind"] == "enum":
        out["allowed"] = rule["allowed"]
    if VERIFY_ENABLED:
        if rule.get("verify_rule"):
            v = rule["verify_rule"]
            out["verify_range"] = {"min": v["lo"], "max": v["hi"]} if v["kind"] == "range" else {"allowed": v["allowed"]}
        if rule.get("sync_param") is not None:
            out["sync_param"], out["synced_values"] = rule["sync_param"], rule.get("synced_values", DIVISIONS)
    return out


def rules_view(slot: str, model_code: int) -> dict:
    """Every param rule the bridge holds for one model, for GET /api/rules."""
    if slot not in am.SLOTS:
        raise am.ProtocolError(f"unknown slot {slot!r}; use one of {sorted(am.SLOTS)}")
    params = {}
    for (s, code, p), rule in sorted(RULES.items(), key=lambda kv: kv[0][2]):
        if s == slot and (code == model_code or (slot == "cab" and code == "ALL")):
            params[str(p)] = _view(rule)
    if not params:
        raise LookupError(f"no rules for {slot} model {model_code}")
    model = next((r.get("model") for (s, c, _), r in RULES.items() if s == slot and c == model_code), None)
    return {"slot": slot, "model_code": model_code, "model": model, "mode": MODE, "verify_mode": VERIFY_ENABLED, "params": params,
            "note": "values are raw wire values; unverified params need \"unverified_ok\": true"}


def _reject(reason: str, message: str, slot, model_code, param, value, rule=None, **more):
    detail = {"reason": reason, "slot": slot, "model_code": model_code, "param": param, "value": value}
    if rule:
        detail.update({"name": rule.get("name"), "rule": _view(rule)})
    detail.update(more)
    raise ValueRejected(message, **detail)


def validate(slot, model_code: int, param: int, value: int, unverified_ok: bool = False, read_sync=None) -> int:
    """Return the value to send, or raise ValueRejected. Never talks to the pedal."""
    if MODE == "off":
        return value
    try:
        _check(slot, model_code, param, value, unverified_ok)
        rule = rule_for(slot, model_code, param)
        if rule and rule.get("sync_required"):
            _check_sync(slot, model_code, param, value, rule, read_sync)
    except ValueRejected as e:
        if MODE == "warn":
            log.warning("param write would be refused (warn mode): %s", e)
            return value
        log.info("param write refused: %s %s", e, e.extra)
        raise
    return value


def _check(slot, model_code, param, value, unverified_ok):
    if not isinstance(slot, str) or slot not in am.SLOTS:
        raise ValueRejected(f"unknown slot {slot!r}", reason="unknown_slot", slot=str(slot))
    rule = rule_for(slot, model_code, param)
    if rule is None:
        _reject("unknown_param", f"no rule for {slot} model {model_code} param {param}: refused "
                "(see GET /api/rules)", slot, model_code, param, value)
    if rule["kind"] == "blocked":
        _reject("blocked_param", f"{rule.get('name') or 'param'} ({slot} {rule.get('model') or model_code} "
                f"p{param}) cannot be written: {rule.get('note', 'no safe rule')}", slot, model_code,
                param, value, rule)
    if rule["kind"] == "enum":
        if value not in rule["allowed"]:
            _reject("not_in_enum", f"{value} is not allowed for {rule.get('name')} ({slot} "
                    f"{rule.get('model')} p{param}); allowed {rule['allowed']}", slot, model_code, param,
                    value, rule)
    elif not rule["lo"] <= value <= rule["hi"]:
        _reject("out_of_range", f"{value} is outside {rule['lo']}-{rule['hi']} for {rule.get('name')} "
                f"({slot} {rule.get('model')} p{param})", slot, model_code, param, value, rule)
    if rule.get("trust") != PROVEN and not unverified_ok:
        _reject("unverified", f"{rule.get('name')} ({slot} {rule.get('model')} p{param}) is not "
                "write-verified on the pedal; send \"unverified_ok\": true to write it anyway",
                slot, model_code, param, value, rule)


def validate_verify(slot, model_code: int, param: int, value: int, read_sync=None) -> int:
    """Verify-mode check for one write. Returns the value to send or raises ValueRejected.

    Always runs in full, whatever AMPERO_VALIDATE says. `read_sync(param)` returns the Sync switch of the
    block as the pedal holds it now, or None when it cannot be read; a Rate that follows a Sync switch is
    refused when the state is unknown.
    """
    if not VERIFY_ENABLED:
        raise ValueRejected("verify mode is off on this bridge (set AMPERO_VERIFY_MODE=1 to turn it on)",
                            reason="verify_mode_off")
    if not isinstance(slot, str) or slot not in am.SLOTS:
        raise ValueRejected(f"unknown slot {slot!r}", reason="unknown_slot", slot=str(slot))
    rule = rule_for(slot, model_code, param)
    if rule is None:
        _reject("unknown_param", f"no rule for {slot} model {model_code} param {param}: refused",
                slot, model_code, param, value)
    eff = rule.get("verify_rule") if rule["kind"] == "blocked" else rule
    if not eff or eff["kind"] == "blocked":
        _reject("blocked_param", f"{rule.get('name') or 'param'} ({slot} {rule.get('model') or model_code} "
                f"p{param}) has no documented range, so verify mode will not write it: "
                f"{rule.get('note', 'no safe rule')}", slot, model_code, param, value, rule)
    if rule.get("wide"):
        _reject("wide_param", f"{rule.get('name')} ({slot} {rule.get('model')} p{param}) is a "
                f"0-{rule['wide']} value and the bridge has no 14-bit writer, so verify mode will not write it",
                slot, model_code, param, value, rule)
    if eff["kind"] == "enum":
        if value not in eff["allowed"]:
            _reject("not_in_enum", f"{value} is not allowed for {rule.get('name')} ({slot} {rule.get('model')} "
                    f"p{param}); allowed {eff['allowed']}", slot, model_code, param, value, rule)
    elif not eff["lo"] <= value <= eff["hi"]:
        _reject("out_of_range", f"{value} is outside {eff['lo']}-{eff['hi']} for {rule.get('name')} "
                f"({slot} {rule.get('model')} p{param})", slot, model_code, param, value, rule)
    _check_sync(slot, model_code, param, value, rule, read_sync)
    return value


def _check_sync(slot, model_code, param, value, rule, read_sync):
    sync_param = rule.get("sync_param")
    if sync_param == UNPAIRED:
        _reject("sync_unknown", f"{rule.get('name')} ({slot} {rule.get('model')} p{param}) sits in a model "
                "whose Sync switch the map cannot tie to this Rate, so it is not written", slot, model_code,
                param, value, rule)
    if sync_param is not None:
        state = read_sync(sync_param) if read_sync else None
        if state is None:
            _reject("sync_unknown", f"cannot tell whether Sync is on for {rule.get('model')}, so "
                    f"{rule.get('name')} is not written", slot, model_code, param, value, rule)
        if state == SYNC_ON and value not in rule.get("synced_values", DIVISIONS):
            _reject("not_a_division", f"Sync is on, so {rule.get('name')} takes a division step "
                    f"{rule.get('synced_values', DIVISIONS)}, not {value}", slot, model_code, param, value, rule, sync=True)
        if state != SYNC_ON and "unsynced_hi" in rule and value > rule["unsynced_hi"]:
            _reject("over_unsynced_max", f"Sync is off, so {rule.get('name')} stops at "
                    f"{rule['unsynced_hi']}, not {value}", slot, model_code, param, value, rule)
    return value
