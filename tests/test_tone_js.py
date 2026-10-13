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
