"""The player daemon: a single long-lived process that owns the speaker.

Only one ``say`` runs at a time, so every session shares this one coordinator.
It exposes a Unix-domain control socket and speaks jobs off a queue.

Session arbitration (the subtle part):

  * A session only ever interrupts *itself*. A newer auto response from session
    S drops S's queued auto job ("you moved on") and, if S is currently
    speaking on the auto channel, cuts it off and starts the new one.
  * A different session's playback is never cut off mid-sentence - new work
    queues behind it.
  * Replay lives on its own channel. It is never cancelled by a later auto
    request, which is what stops the Stop hook of the very `/tts replay` turn
    (same session, fires moments later) from killing the replay it just
    started. There is no single shared pid file; jobs are tracked structurally.
  * When the speaking session changes, the daemon announces who is talking.
"""

from __future__ import annotations

import json
import os
import socket
import sys
import threading
import time
from collections import deque
from dataclasses import dataclass, field
from typing import Optional

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from tts_reader import config, engine, transcript  # noqa: E402
from tts_reader.sanitize import HEADER, PROSE, sanitize  # noqa: E402

AUTO = "auto"
REPLAY = "replay"
IDLE_TIMEOUT = 30 * 60  # seconds with no work before the daemon exits


@dataclass
class Job:
    session_id: str
    channel: str  # AUTO or REPLAY
    transcript_path: str
    cwd: str
    mode: str
    request_ts: float
    seq: int = field(default=0)


class Daemon:
    def __init__(self) -> None:
        self.lock = threading.RLock()
        self.cv = threading.Condition(self.lock)
        self.pending: "deque[Job]" = deque()
        self.active: Optional[Job] = None
        self.active_proc = None
        self.abort_active = False
        self.last_speaking_session: Optional[str] = None
        self.running = True
        self.last_activity = time.time()
        self._seq = 0

    # -- submission / arbitration -----------------------------------------

    def submit(self, job: Job) -> None:
        with self.cv:
            self._seq += 1
            job.seq = self._seq
            self.last_activity = time.time()

            if job.channel == AUTO:
                # "you moved on": discard this session's queued auto work
                self.pending = deque(
                    j for j in self.pending
                    if not (j.channel == AUTO and j.session_id == job.session_id)
                )
                # interrupt only our *own* auto playback, never a replay or
                # another session's audio
                if (
                    self.active
                    and self.active.channel == AUTO
                    and self.active.session_id == job.session_id
                ):
                    self._kill_active_locked()

            self.pending.append(job)
            self.cv.notify()

    def stop(self, session_id: Optional[str]) -> None:
        """Interrupt current playback + drop this session's queued work."""
        with self.cv:
            self.last_activity = time.time()
            if self.active and (session_id is None or self.active.session_id == session_id):
                self._kill_active_locked()
            self.pending = deque(
                j for j in self.pending
                if session_id is not None and j.session_id != session_id
            )
            self.cv.notify()

    def _kill_active_locked(self) -> None:
        self.abort_active = True
        if self.active_proc and self.active_proc.poll() is None:
            try:
                self.active_proc.terminate()
            except OSError:
                pass

    # -- playback ---------------------------------------------------------

    def _speak_blocking(self, text: str, voice, wpm: int) -> None:
        with self.lock:
            if self.abort_active:
                return
            proc = engine.speak(text, voice, wpm)
            self.active_proc = proc
        proc.wait()
        with self.lock:
            self.active_proc = None

    def _play(self, job: Job) -> None:
        text = transcript.read_final_text(job.transcript_path, job.request_ts)
        if not text:
            return
        cfg = config.load_config()
        prose_voice = cfg.get("prose_voice")
        header_voice = cfg.get("header_voice") or prose_voice
        wpm = int(cfg.get("wpm", 175))

        utterances = sanitize(text, job.mode)
        if not utterances:
            return

        # announce a change of speaker so you always know which window is talking
        announce = None
        with self.lock:
            if job.session_id != self.last_speaking_session:
                self.last_speaking_session = job.session_id
                label = os.path.basename(job.cwd.rstrip("/")) or "session"
                announce = f"{label} speaking."
        if announce:
            self._speak_blocking(announce, prose_voice, wpm)

        for utt in utterances:
            with self.lock:
                if self.abort_active:
                    break
            voice = header_voice if utt.voice == HEADER else prose_voice
            self._speak_blocking(utt.text, voice, wpm)

    def player_loop(self) -> None:
        while True:
            with self.cv:
                while self.running and not self.pending:
                    self.cv.wait(timeout=5.0)
                    if not self.running:
                        return
                    if not self.pending and time.time() - self.last_activity > IDLE_TIMEOUT:
                        self.running = False
                        return
                if not self.running:
                    return
                job = self.pending.popleft()
                self.active = job
                self.abort_active = False
            try:
                self._play(job)
            except Exception:  # never let one bad job kill the player
                pass
            with self.lock:
                self.active = None
                self.active_proc = None
                self.last_activity = time.time()

    # -- control socket ---------------------------------------------------

    def handle_request(self, req: dict) -> dict:
        t = req.get("type")
        if t == "ping":
            return {"ok": True}
        if t == "speak":
            self.submit(Job(
                session_id=req.get("session_id", "?"),
                channel=req.get("channel", AUTO),
                transcript_path=req.get("transcript_path", ""),
                cwd=req.get("cwd", ""),
                mode=req.get("mode", "summary"),
                request_ts=float(req.get("request_ts", 0.0)),
            ))
            return {"ok": True, "queued": True}
        if t == "stop":
            self.stop(req.get("session_id"))
            return {"ok": True, "stopped": True}
        if t == "status":
            with self.lock:
                return {
                    "ok": True,
                    "active": self.active.session_id if self.active else None,
                    "channel": self.active.channel if self.active else None,
                    "queued": len(self.pending),
                }
        if t == "shutdown":
            with self.cv:
                self.running = False
                self._kill_active_locked()
                self.cv.notify_all()
            return {"ok": True}
        return {"ok": False, "error": f"unknown request {t!r}"}

    def serve(self) -> None:
        sock_path = config.socket_path()
        if sock_path.exists():
            sock_path.unlink()
        srv = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        srv.bind(str(sock_path))
        srv.listen(16)
        srv.settimeout(5.0)
        config.pid_path().write_text(str(os.getpid()))

        threading.Thread(target=self.player_loop, daemon=True).start()

        while self.running:
            try:
                conn, _ = srv.accept()
            except socket.timeout:
                with self.lock:
                    if not self.running:
                        break
                continue
            with conn:
                try:
                    data = conn.recv(65536).decode("utf-8").strip()
                    req = json.loads(data) if data else {}
                    resp = self.handle_request(req)
                except Exception as exc:  # noqa: BLE001
                    resp = {"ok": False, "error": str(exc)}
                try:
                    conn.sendall((json.dumps(resp) + "\n").encode("utf-8"))
                except OSError:
                    pass

        srv.close()
        for p in (config.socket_path(), config.pid_path()):
            try:
                p.unlink()
            except OSError:
                pass


def main() -> None:
    Daemon().serve()


if __name__ == "__main__":
    main()
