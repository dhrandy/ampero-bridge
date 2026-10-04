import threading
import time

import pytest

import usbmidi as u


class FakePedal:
    delay = 0.0
    fail = None

    def __enter__(self):
        if FakePedal.fail:
            raise FakePedal.fail
        return self

    def __exit__(self, *a):
        return False


@pytest.fixture(autouse=True)
def fake(monkeypatch):
    FakePedal.delay = 0.0
    FakePedal.fail = None
    monkeypatch.setattr(u, "Pedal", FakePedal)


def test_ok_and_error_counters():
    link = u.Link(exit_fn=lambda c: None)
    assert link.session("t", lambda p: 5) == 5
    FakePedal.fail = u.PedalNotConnected("nope")
    with pytest.raises(u.PedalNotConnected):
        link.session("t", lambda p: 5)
    st = link.status()
    assert st["requests"] == 2 and st["errors"] == 1 and "PedalNotConnected" in st["last_error"]


def test_second_caller_gets_busy_not_a_pile_up():
    link = u.Link(wait=0.2, exit_fn=lambda c: None)
    go = threading.Event()
    t = threading.Thread(target=lambda: link.session("slow", lambda p: go.wait(2)))
    t.start()
    time.sleep(0.1)
    with pytest.raises(u.PedalBusy):
        link.session("second", lambda p: 1)
    go.set()
    t.join()
    assert link.session("after", lambda p: 1) == 1


def test_watchdog_exits_on_stuck_request():
    codes = []
    link = u.Link(hard_deadline=0.5, exit_fn=codes.append)
    release = threading.Event()
    t = threading.Thread(target=lambda: link.session("stuck", lambda p: release.wait(5)))
    t.start()
    deadline = time.time() + 4
    while not codes and time.time() < deadline:
        time.sleep(0.1)
    release.set()
    t.join()
    assert codes == [70]
