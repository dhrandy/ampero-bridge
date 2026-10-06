import json
import os

SITE = os.path.join(os.path.dirname(__file__), "..", "site")
FIELDS = {"era", "power", "cab", "controls", "players", "what", "behavior", "character"}


def load(name):
    with open(os.path.join(SITE, name), encoding="utf-8") as f:
        return json.load(f)


def test_every_info_entry_points_at_a_real_model_and_stays_short():
    codes = {f"{b['block']}:{m['code']}" for b in load("models.json")["blocks"] for m in b["models"] if m["code"] is not None}
    info = load("info.json")["models"]
    assert info, "info.json has no entries"
    for key, entry in info.items():
        assert key in codes, key
        assert entry and set(entry) <= FIELDS, key
        for field, text in entry.items():
            assert isinstance(text, str) and 0 < len(text) <= 120, (key, field)


def test_site_files_carry_no_personal_data():
    """No email address, private network address or local path in the files the public site serves."""
    import re
    patterns = [r"[\w.+-]+@[\w-]+\.[a-z]{2,}", r"\b(10|192\.168|172\.(1[6-9]|2\d|3[01]))\.\d+\.\d+(\.\d+)?\b",
                r"\.(local|lan|internal)\b", r"/(home|users|mnt|volume\d*)/\w+"]
    for name in ("index.html", "bridge.js", "bridge.css", "info.json"):
        text = open(os.path.join(SITE, name), encoding="utf-8").read().lower()
        for pat in patterns:
            assert not re.search(pat, text), (name, pat)
