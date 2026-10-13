import os
import shutil
import subprocess

import pytest

HERE = os.path.dirname(os.path.abspath(__file__))


@pytest.mark.skipif(shutil.which("node") is None, reason="node is not installed")
def test_tone_panel_logic():
    r = subprocess.run(["node", os.path.join(HERE, "tone.test.js")], capture_output=True, text=True, timeout=60)
    assert r.returncode == 0, r.stdout + r.stderr


def test_tone_panel_has_no_write_buttons_beyond_the_edit_buffer():
    src = open(os.path.join(HERE, "..", "site", "tone.js"), encoding="utf-8").read()
    for path in ("/api/patch/save", "/api/backup", "/api/restore", "/api/block/copy", "/api/midi"):
        assert path not in src
    assert "unverified_ok" in src


@pytest.mark.skipif(shutil.which("node") is None, reason="node is not installed")
def test_site_decoder_matches_the_bridge_decoder():
    """The page and the bridge must read every block the same way (records.decode_params)."""
    import json
    import random
    import sys
    sys.path.insert(0, os.path.join(HERE, ".."))
    import records
    rnd = random.Random(7)
    recs = []
    for i in range(40):
        b = bytearray(rnd.randrange(0, 128) for _ in range(records.RECORD_LEN))
        b[1] = i % 128
        for slot, off in records.BLOCK_OFFSETS.items():
            b[off] = rnd.randrange(0, 2)
            code = rnd.choice([75, 4, 0, 16, 9, 34, 100, rnd.randrange(0, 200)])
            b[off + 1], b[off + 2] = code >> 7, code & 0x7F
        recs.append(bytes(b))
    script = ("const T=require(process.argv[1]);const L=require('fs').readFileSync(0,'utf8').trim().split('\\n');"
              "console.log(JSON.stringify(L.map(h=>{const r=T.parseRecord(h);return Object.keys(r.blocks).map(k=>[k,r.blocks[k].code,r.blocks[k].params]);})));")
    r = subprocess.run(["node", "-e", script, os.path.join(HERE, "..", "site", "tone.js")], input="\n".join(x.hex() for x in recs),
                       capture_output=True, text=True, timeout=60)
    assert r.returncode == 0, r.stderr
    got = json.loads(r.stdout)
    for rec, blocks in zip(recs, got):
        for slot, code, params in blocks:
            f = records.block_fields(rec, slot)
            assert (f["code"], f["params"]) == (code, params), slot
