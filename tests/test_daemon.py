"""Tests for the player daemon's queue, channels, and session arbitration.

Uses a fake speaker so playback is deterministic and needs no audio. Each job's
``transcript_path`` doubles as its response text (we stub the transcript read),
and each response expands to several utterances so there is a real window during
which a job can be interrupted.
"""

import threading
import time

import pytest

from tts_reader import config
from tts_reader import daemon as D
from tts_reader import engine, transcript
import tts_reader.daemon as dmod
from tts_reader.sanitize import PROSE, Utterance


class FakeProc:
    """A `say` stand-in that 'plays' for a short time unless terminated."""

    def __init__(self, dur=0.15):
        self._killed = False
        self._end = time.time() + dur

    def poll(self):
        return 0 if (self._killed or time.time() >= self._end) else None

    def wait(self):
        while self.poll() is None:
            time.sleep(0.005)

    def terminate(self):
        self._killed = True


@pytest.fixture
def harness(monkeypatch):
    config.save_config({"enabled": True, "mode": "full", "prose_voice": None,
                        "header_voice": None, "wpm": 175})
    spoken = []          # (session_id, text) in actual playback order
    lock = threading.Lock()
    current = {"sid": None}

    def fake_speak(text, voice=None, wpm=175):
        with lock:
            spoken.append((current["sid"], text))
        return FakeProc()

    monkeypatch.setattr(engine, "speak", fake_speak)
    # the "transcript_path" carries the response text in these tests
    monkeypatch.setattr(transcript, "read_final_text",
                        lambda path, request_ts=0.0, timeout=3.0, poll=0.15: path)
    monkeypatch.setattr(dmod, "sanitize",
                        lambda text, mode: [Utterance(PROSE, f"{text}-{i}") for i in range(3)])

    d = D.Daemon()
    orig_play = d._play

    def play(job):
        current["sid"] = job.session_id
        orig_play(job)

    d._play = play
    t = threading.Thread(target=d.player_loop, daemon=True)
    t.start()
    yield d, spoken
    with d.cv:
        d.running = False
        d.cv.notify_all()


def _job(sid, channel, text, ts=0.0):
    return D.Job(session_id=sid, channel=channel, transcript_path=text,
                 cwd="/w/" + sid, mode="full", request_ts=ts)


def _settle(spoken, quiet=0.4, limit=4.0):
    """Wait until playback has been quiet for `quiet` seconds."""
    deadline = time.time() + limit
    last_len, last_change = len(spoken), time.time()
    while time.time() < deadline:
        time.sleep(0.05)
        if len(spoken) != last_len:
            last_len, last_change = len(spoken), time.time()
        elif time.time() - last_change >= quiet:
            return
    return


def test_newer_auto_interrupts_own_older_auto(harness):
    d, spoken = harness
    d.submit(_job("S", D.AUTO, "old", 1))
    time.sleep(0.1)
    d.submit(_job("S", D.AUTO, "new", 2))
    _settle(spoken)
    texts = [t for _, t in spoken]
    assert any(t.startswith("new") for t in texts), "newer response must play"
    assert "old-2" not in texts, "older response's later chunks must be cut off"


def test_other_session_queues_never_interleaves(harness):
    d, spoken = harness
    d.submit(_job("A", D.AUTO, "aaa", 1))
    time.sleep(0.05)
    d.submit(_job("B", D.AUTO, "bbb", 1))
    _settle(spoken)
    order = [s for s, _ in spoken]
    assert "A" in order and "B" in order
    last_a = max(i for i, s in enumerate(order) if s == "A")
    first_b = min(i for i, s in enumerate(order) if s == "B")
    assert last_a < first_b, "B must not start before A finishes"


def test_replay_survives_following_same_session_auto(harness):
    d, spoken = harness
    # This is the /tts replay scenario: the replay starts, then the Stop hook
    # for that very turn fires an auto request from the same session.
    d.submit(_job("S", D.REPLAY, "REPLAY", 0))
    time.sleep(0.1)
    d.submit(_job("S", D.AUTO, "autospeech", 9))
    _settle(spoken)
    texts = [t for _, t in spoken]
    assert sum(t.startswith("REPLAY") for t in texts) == 3, "replay must play in full"
    assert any(t.startswith("autospeech") for t in texts), "auto still plays after"


def test_stop_interrupts_and_clears_session_queue(harness):
    d, spoken = harness
    d.submit(_job("S", D.AUTO, "one", 1))
    d.submit(_job("S", D.AUTO, "two", 2))  # 'one' cancels this per arbitration...
    d.submit(_job("S", D.AUTO, "three", 3))
    time.sleep(0.1)
    d.stop("S")
    _settle(spoken)
    # after stop, nothing new from S should start; queue is empty
    with d.lock:
        assert d.active is None
        assert len(d.pending) == 0


def test_speaker_change_is_announced(harness):
    d, spoken = harness
    d.submit(_job("W1", D.AUTO, "hello", 1))
    _settle(spoken)
    assert any("speaking" in t for _, t in spoken), "should announce the window"


def test_no_announcement_when_same_session_continues(harness):
    d, spoken = harness
    d.submit(_job("W1", D.AUTO, "first", 1))
    _settle(spoken)
    n_before = sum("speaking" in t for _, t in spoken)
    d.submit(_job("W1", D.AUTO, "second", 2))
    _settle(spoken)
    n_after = sum("speaking" in t for _, t in spoken)
    assert n_after == n_before, "same session should not re-announce"


def test_handle_request_dispatch(harness):
    d, _ = harness
    assert d.handle_request({"type": "ping"}) == {"ok": True}
    assert d.handle_request({"type": "speak", "session_id": "S",
                             "transcript_path": "x"})["queued"] is True
    assert d.handle_request({"type": "bogus"})["ok"] is False
    status = d.handle_request({"type": "status"})
    assert status["ok"] is True and "queued" in status
