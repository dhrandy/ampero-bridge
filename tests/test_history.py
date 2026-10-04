import os
import tempfile
import threading

os.environ["API_KEY"] = "k"
os.environ["AMPERO_DATA_DIR"] = tempfile.mkdtemp()

import ampero_mini as am  # noqa: E402
import server  # noqa: E402
import usbmidi as usb  # noqa: E402


def got(rec="aa" * 4, index=76, name="TEST"):
    return {"index": index, "label": am.patch_label(index), "name": name, "record_hex": rec}


def test_same_record_is_one_entry_and_a_change_is_a_new_one():
    h = server.History(600, 50)
    h.add(got("00112233"), now=100)
    h.add(got("00112233"), now=102)
    h.add(got("00112299"), now=104)
    assert len(h.entries) == 2
    assert h.entries[0]["t"] == 100 and h.entries[0]["last_seen"] == 102
    assert h.entries[0]["changed_bytes"] is None
    assert h.entries[1]["changed_bytes"] == [3]


def test_old_states_drop_out_but_the_latest_always_stays():
    h = server.History(10, 50)
    h.add(got("0001"), now=0)
    h.add(got("0002"), now=5)
    h.add(got("0003"), now=30)
    assert [e["record_hex"] for e in h.entries] == ["0003"]
    h.add(got("0003"), now=1000)
    assert len(h.entries) == 1


def test_entry_limit():
    h = server.History(10_000, 3)
    for i in range(6):
        h.add(got(f"{i:04x}"), now=i)
    assert [e["record_hex"] for e in h.entries] == ["0003", "0004", "0005"]


def test_different_length_records_are_not_diffed():
    h = server.History(600, 50)
    h.add(got("0011"), now=1)
    h.add(got("001122"), now=2)
    assert h.entries[1]["changed_bytes"] is None


def test_listing_filters_since_and_can_drop_hex():
    h = server.History(600, 50)
    h.add(got("0001"), now=10)
    h.add(got("0002"), now=20)
    out = h.listing(since=15)
    assert [s["record_hex"] for s in out["states"]] == ["0002"]
    assert "record_hex" not in h.listing(with_hex=False)["states"][0]
    assert out["polls"] == 2 and out["window_s"] == 600


def test_poller_records_and_survives_errors(monkeypatch):
    h = server.History(600, 50)
    monkeypatch.setattr(server, "history", h)
    monkeypatch.setattr(server, "HISTORY_POLL", 0.0)
    monkeypatch.setattr(usb, "is_present", lambda: True)
    replies = iter([got("01"), RuntimeError("usb hiccup"), got("02")])

    def fake_read():
        r = next(replies)
        if isinstance(r, Exception):
            raise r
        return r
    monkeypatch.setattr(server, "read_current_patch", fake_read)
    monkeypatch.setattr(server.time, "sleep", lambda s: None)
    server.poll_history(rounds=3)
    assert [e["record_hex"] for e in h.entries] == ["01", "02"]
    assert h.errors == 1 and "usb hiccup" in h.last_error


def test_poller_skips_while_the_pedal_is_unplugged(monkeypatch):
    h = server.History(600, 50)
    monkeypatch.setattr(server, "history", h)
    monkeypatch.setattr(server, "HISTORY_POLL", 0.0)
    monkeypatch.setattr(usb, "is_present", lambda: False)
    monkeypatch.setattr(server, "read_current_patch", lambda: 1 / 0)
    monkeypatch.setattr(server.time, "sleep", lambda s: None)
    server.poll_history(rounds=2)
    assert h.entries == [] and h.errors == 0


def test_poller_stops_on_the_event(monkeypatch):
    stop = threading.Event()
    stop.set()
    monkeypatch.setattr(server, "HISTORY_POLL", 0.01)
    server.poll_history(stop)   # returns at once, does not read
