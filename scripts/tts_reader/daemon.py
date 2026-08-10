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
import secrets
import socket
import sys
import threading
import time
from collections import deque
from dataclasses import dataclass, field
from pathlib import Path
from typing import List, Optional, Tuple

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from tts_reader import config, engine, transcript  # noqa: E402
from tts_reader.sanitize import HEADER, PROSE, sanitize  # noqa: E402

AUTO = "auto"
REPLAY = "replay"
IDLE_TIMEOUT = 30 * 60  # seconds with no work before the daemon exits
VOICE_SWITCH_PAUSE = 0.08  # seconds; see _group_by_voice


def _group_by_voice(utterances, prose_voice, header_voice):
    """Merge consecutive utterances using the same resolved voice into one
    ``say`` call each, joined by newlines.

    Spawning a separate ``say`` subprocess per utterance and waiting for each
    to exit before starting the next leaves a small gap where the trailing
    syllable of one utterance can get clipped as the next process's audio
    device handoff happens - audible as every line/utterance boundary
    swallowing its last syllable. Since ``say`` already paces sentences
    naturally within one invocation, batching same-voice runs removes that
    boundary for the common case (consecutive prose or list items).
    """
    groups: List[Tuple[object, List[str]]] = []
    for utt in utterances:
        voice = header_voice if utt.voice == HEADER else prose_voice
        if groups and groups[-1][0] == voice:
            groups[-1][1].append(utt.text)
        else:
            groups.append((voice, [utt.text]))
    return [(voice, "\n".join(texts)) for voice, texts in groups]


@dataclass
class Job:
    session_id: str
    channel: str  # AUTO or REPLAY
    transcript_path: str
    cwd: str
    mode: str
    text: Optional[str] = None  # inline text; when set, skips transcript read
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
        self.token: Optional[str] = None

    # -- submission / arbitration -----------------------------------------

    def submit(self, job: Job) -> None:
        with self.cv:
            self._seq += 1
            job.seq = self._seq
            self.last_activity = time.time()

            if job.channel == AUTO:
                # "you moved on": discard this session's queued auto work
                dropped = [
                    j for j in self.pending
                    if j.channel == AUTO and j.session_id == job.session_id
                ]
                self.pending = deque(
                    j for j in self.pending
                    if not (j.channel == AUTO and j.session_id == job.session_id)
                )
                # interrupt only our *own* auto playback, never a replay or
                # another session's audio
                interrupted = bool(
                    self.active
                    and self.active.channel == AUTO
                    and self.active.session_id == job.session_id
                )
                if interrupted:
                    self._kill_active_locked()
                if dropped or interrupted:
                    config.debug_log(
                        "submit_superseded",
                        session_id=job.session_id,
                        dropped_pending=len(dropped),
                        interrupted_active=interrupted,
                    )

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

    def _speak_blocking(self, backend, text: str, voice, wpm: int) -> None:
        with self.lock:
            if self.abort_active:
                return
        # Synthesize/spawn *outside* the lock: the cloud backend does a blocking
        # network round-trip in speak(), and holding self.lock across it would
        # stall stop/status/arbitration for the whole request (up to the HTTP
        # timeout). The OS backends return a Popen immediately, so this is free
        # for them.
        proc = backend.speak(text, voice, wpm)
        if proc is None:
            return  # backend spoke nothing (e.g. missing engine / cloud key)
        with self.lock:
            if self.abort_active:
                # a stop/supersede landed while we were synthesizing; drop the
                # playback we just started rather than letting it speak.
                if proc.poll() is None:
                    try:
                        proc.terminate()
                    except OSError:
                        pass
                return
            self.active_proc = proc
        proc.wait()
        with self.lock:
            self.active_proc = None

    def _play(self, job: Job) -> None:
        # Prefer host-supplied inline text (future Cursor/Antigravity paths);
        # Claude and replay still use the transcript file when text is absent.
        text = job.text.strip() if job.text else None
        if not text:
            text = transcript.read_final_text(job.transcript_path)
        if not text:
            config.debug_log(
                "play_no_text",
                session_id=job.session_id,
                channel=job.channel,
                transcript_path=job.transcript_path,
                had_inline_text=bool(job.text),
            )
            return
        cfg = config.load_config()
        backend = engine.get_backend(cfg)
        prose_voice = cfg.get("prose_voice")
        header_voice = cfg.get("header_voice") or prose_voice
        wpm = int(cfg.get("wpm", 175))

        utterances = sanitize(text, job.mode)
        if not utterances:
            config.debug_log(
                "play_no_utterances", session_id=job.session_id, channel=job.channel
            )
            return
        config.debug_log(
            "play_start",
            session_id=job.session_id,
            channel=job.channel,
            utterance_count=len(utterances),
        )

        # announce a change of speaker so you always know which window is talking
        announce = None
        with self.lock:
            if job.session_id != self.last_speaking_session:
                self.last_speaking_session = job.session_id
                label = Path(job.cwd).name or "session"
                announce = f"{label} speaking."
        if announce:
            self._speak_blocking(backend, announce, prose_voice, wpm)
            time.sleep(VOICE_SWITCH_PAUSE)  # let the announcement's audio drain

        for i, (voice, group_text) in enumerate(
            _group_by_voice(utterances, prose_voice, header_voice)
        ):
            with self.lock:
                if self.abort_active:
                    break
            if i > 0:
                time.sleep(VOICE_SWITCH_PAUSE)  # let the prior group's audio drain
            self._speak_blocking(backend, group_text, voice, wpm)

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
        # The control channel is loopback TCP, reachable by any local process;
        # a shared token (written to the 0600 port file) gates every request so
        # another process can't inject speak/shutdown jobs.
        if self.token is not None and req.get("token") != self.token:
            return {"ok": False, "error": "unauthorized"}
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
                text=req.get("text"),
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
        # Loopback TCP (not AF_UNIX) so this works on Windows too. Bind to an
        # ephemeral port and publish it - plus an auth token - via the port file.
        self.token = secrets.token_hex(16)
        srv = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        srv.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        srv.bind(("127.0.0.1", 0))
        port = srv.getsockname()[1]
        srv.listen(16)
        srv.settimeout(5.0)

        port_file = config.port_path()
        port_file.write_text(f"{port}\n{self.token}\n")
        try:
            os.chmod(port_file, 0o600)  # best-effort; no-op on some platforms
        except OSError:
            pass
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
        for p in (config.port_path(), config.pid_path()):
            try:
                p.unlink()
            except OSError:
                pass


def main() -> None:
    Daemon().serve()


if __name__ == "__main__":
    main()
