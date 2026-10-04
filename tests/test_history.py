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


def test_pacer_backs_off_while_changing_and_recovers(monkeypatch):
    monkeypatch.setattr(server, "HISTORY_BUSY_MAX", 10.0)
    p = server.Pacer(2.0)
    assert p.ok(False) == 2.0 and p.mode() == "idle"
    assert p.ok(True) == 4.0 and p.mode() == "busy"
    assert p.ok(True) == 8.0
    assert p.ok(True) == 8.0                      # capped at x4 and at the busy max
    assert p.ok(False) == 8.0                     # one quiet read is not enough yet
    assert p.ok(False) == 2.0 and p.mode() == "idle"


def test_pacer_busy_wait_never_passes_the_cap(monkeypatch):
    monkeypatch.setattr(server, "HISTORY_BUSY_MAX", 5.0)
    p = server.Pacer(2.0)
    p.ok(True)
    assert p.ok(True) == 5.0


def test_pacer_waits_at_least_as_long_as_the_read_took():
    p = server.Pacer(2.0)
    assert p.ok(False, took=3.5) == 3.5


def test_pacer_doubles_after_errors_and_resets():
    p = server.Pacer(2.0)
    assert [p.failed() for _ in range(3)] == [8.0, 16.0, 30.0]
    assert p.mode() == "errors"
    assert p.ok(False) == 2.0 and p.mode() == "idle"


def test_poller_waits_longer_after_a_change_and_after_an_error(monkeypatch):
    h = server.History(600, 50)
    monkeypatch.setattr(server, "history", h)
    monkeypatch.setattr(server, "HISTORY_POLL", 2.0)
    monkeypatch.setattr(server, "HISTORY_BUSY_MAX", 10.0)
    monkeypatch.setattr(usb, "is_present", lambda: True)
    replies = iter([got("01"), got("02"), RuntimeError("patch dump incomplete"), got("02"), got("02")])

    def fake_read():
        r = next(replies)
        if isinstance(r, Exception):
            raise r
        return r
    monkeypatch.setattr(server, "read_current_patch", fake_read)
    waits = []
    monkeypatch.setattr(server.time, "sleep", waits.append)
    server.poll_history(rounds=5)
    # the first wait is the base, then: changed, changed, error, quiet
    assert waits == [2.0, 4.0, 8.0, 8.0, 2.0]
    assert h.errors == 1 and "incomplete" in h.last_error
    st = h.status()
    assert st["pace"] == "idle" and st["current_poll_s"] == 2.0


def test_poller_never_overlaps_reads(monkeypatch):
    h = server.History(600, 50)
    monkeypatch.setattr(server, "history", h)
    monkeypatch.setattr(server, "HISTORY_POLL", 0.0)
    monkeypatch.setattr(usb, "is_present", lambda: True)
    open_reads, worst = [0], [0]

    def fake_read():
        open_reads[0] += 1
        worst[0] = max(worst[0], open_reads[0])
        open_reads[0] -= 1
        return got("01")
    monkeypatch.setattr(server, "read_current_patch", fake_read)
    monkeypatch.setattr(server.time, "sleep", lambda s: None)
    server.poll_history(rounds=5)
    assert worst[0] == 1
