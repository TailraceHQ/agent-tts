"""Stdlib radio-list selector for interactive CLI setup.

Space fills the radio under the cursor. Enter saves that selection (Back and
Exit commit immediately when focused). No third-party TUI libraries: the
runtime stays stdlib-only.
"""

from __future__ import annotations

import os
import sys
from typing import Callable, List, Optional, Sequence, Tuple

BACK = "__back__"
EXIT = "__exit__"

_HINT = "space select · enter save · ↑/↓ move"

# (id, label) pairs passed in by callers.
Choice = Tuple[str, str]


class _Item:
    __slots__ = ("id", "label", "kind")

    def __init__(self, id: str, label: str, kind: str = "choice"):
        self.id = id
        self.label = label
        self.kind = kind  # choice | action | sep


def _glyphs(stream) -> dict:
    encoding = getattr(stream, "encoding", None) or "utf-8"
    try:
        "•❯─".encode(encoding)
        return {"dot": "•", "empty": " ", "cursor": "❯", "rule": "─" * 28}
    except (UnicodeEncodeError, LookupError):
        return {"dot": "*", "empty": " ", "cursor": ">", "rule": "-" * 28}


def _items(choices: Sequence[Choice], allow_back: bool, glyphs: dict) -> List[_Item]:
    out = [_Item(i, label) for i, label in choices]
    out.append(_Item("", glyphs["rule"], "sep"))
    if allow_back:
        out.append(_Item(BACK, "Go back", "action"))
    out.append(_Item(EXIT, "Exit", "action"))
    return out


def _move(cursor: int, delta: int, items: Sequence[_Item]) -> int:
    n = len(items)
    i = cursor
    for _ in range(n):
        i = (i + delta) % n
        if items[i].kind != "sep":
            return i
    return cursor


def _frame(
    title: str, items: Sequence[_Item], cursor: int, chosen: str, glyphs: dict
) -> str:
    lines: List[str] = []
    if title:
        for raw in title.splitlines():
            lines.append(f"\033[1m{raw}\033[0m" if raw else "")
        lines.append("")
    for i, it in enumerate(items):
        if it.kind == "sep":
            lines.append(f"  \033[2m{it.label}\033[0m")
            continue
        filled = it.id == chosen
        radio = glyphs["dot"] if filled else glyphs["empty"]
        pointer = glyphs["cursor"] if i == cursor else " "
        row = f"{pointer} ({radio}) {it.label}"
        if i == cursor:
            row = f"\033[36m{row}\033[0m"
        elif filled:
            row = f"\033[32m{row}\033[0m"
        lines.append(row)
    lines.append("")
    lines.append(f"\033[2m  {_HINT}\033[0m")
    # CRLF: tty.setraw() disables ONLCR, so a bare \\n would move down
    # without returning to column 0 and the list would staircase.
    return "".join(line + "\r\n" for line in lines)


def _read_escape(fd: int) -> str:
    import select

    ready, _, _ = select.select([fd], [], [], 0.05)
    if not ready:
        return "esc"
    rest = os.read(fd, 8)
    if rest.startswith(b"[A") or rest.startswith(b"OA"):
        return "up"
    if rest.startswith(b"[B") or rest.startswith(b"OB"):
        return "down"
    return "esc"


def _read_key_posix(fd: int) -> str:
    ch = os.read(fd, 1)
    if not ch or ch == b"\x1b":
        return _read_escape(fd) if ch == b"\x1b" else "esc"
    if ch == b"\x03":
        return "ctrl-c"
    if ch in (b"\r", b"\n"):
        return "enter"
    if ch == b" ":
        return "space"
    if ch in (b"q", b"Q"):
        return "esc"
    if ch in (b"k", b"K"):
        return "up"
    if ch in (b"j", b"J"):
        return "down"
    return "other"


def _read_key_windows() -> str:
    import msvcrt

    ch = msvcrt.getwch()
    if ch in ("\x00", "\xe0"):
        extra = msvcrt.getwch()
        return {"H": "up", "P": "down"}.get(extra, "other")
    if ch in ("\r", "\n"):
        return "enter"
    if ch == " ":
        return "space"
    if ch == "\x03":
        return "ctrl-c"
    if ch in ("q", "Q", "\x1b"):
        return "esc"
    if ch in ("k", "K"):
        return "up"
    if ch in ("j", "J"):
        return "down"
    return "other"


def _make_read_key(stdin) -> Callable[[], str]:
    if sys.platform == "win32":
        return _read_key_windows
    fd = stdin.fileno()
    return lambda: _read_key_posix(fd)


class _RawStdin:
    """Byte-at-a-time input without turning the whole tty raw.

    ``tty.setraw`` clears ``OPOST``, so ``\\n`` no longer returns to column 0
    and the radio list paints diagonally. ``setcbreak`` keeps output mapping.
    """

    def __init__(self, stdin):
        self.stdin = stdin
        self._old = None

    def __enter__(self):
        if sys.platform == "win32":
            return self
        try:
            import termios
            import tty
        except ImportError:
            return self
        fd = self.stdin.fileno()
        self._old = termios.tcgetattr(fd)
        tty.setcbreak(fd)
        return self

    def __exit__(self, *exc):
        if self._old is None:
            return False
        import termios

        termios.tcsetattr(self.stdin.fileno(), termios.TCSADRAIN, self._old)
        self._old = None
        return False


def radio_select(
    title: str,
    choices: Sequence[Choice],
    *,
    selected_id: Optional[str] = None,
    allow_back: bool = True,
    read_key: Optional[Callable[[], str]] = None,
    write: Optional[Callable[[str], None]] = None,
    stdin=None,
    stdout=None,
) -> str:
    """Interactive radio list. Returns a choice id, ``BACK``, or ``EXIT``.

    ``read_key`` / ``write`` are injectable so tests can drive the widget
    without a real terminal.
    """
    if not choices:
        return EXIT
    stdout = stdout or sys.stdout
    stdin = stdin or sys.stdin
    emit = write or (lambda s: (stdout.write(s), stdout.flush()))
    glyphs = _glyphs(stdout)
    items = _items(choices, allow_back, glyphs)

    chosen = selected_id if any(it.id == selected_id for it in items) else items[0].id
    cursor = next(
        (i for i, it in enumerate(items) if it.id == chosen),
        next(i for i, it in enumerate(items) if it.kind != "sep"),
    )

    live = read_key is None
    get_key = read_key or _make_read_key(stdin)
    n_lines = 0

    def draw() -> None:
        nonlocal n_lines
        frame = _frame(title, items, cursor, chosen, glyphs)
        if n_lines:
            emit(f"\r\033[{n_lines}A\033[J")
        emit(frame)
        n_lines = frame.count("\n")

    def erase() -> None:
        nonlocal n_lines
        if n_lines:
            emit(f"\r\033[{n_lines}A\033[J")
            n_lines = 0
        emit("\033[?25h")

    ctx = _RawStdin(stdin) if live else None
    if ctx:
        ctx.__enter__()
    try:
        emit("\033[?25l")
        draw()
        while True:
            key = get_key()
            if key in ("esc", "ctrl-c"):
                return EXIT
            if key == "up":
                cursor = _move(cursor, -1, items)
                draw()
                continue
            if key == "down":
                cursor = _move(cursor, 1, items)
                draw()
                continue
            if key == "space":
                focused = items[cursor]
                if focused.kind != "sep":
                    chosen = focused.id
                    draw()
                continue
            if key == "enter":
                focused = items[cursor]
                if focused.id in (BACK, EXIT):
                    return focused.id
                return chosen
    except (KeyboardInterrupt, EOFError):
        return EXIT
    finally:
        erase()
        if ctx:
            ctx.__exit__(None, None, None)


def prompt_line(
    message: str,
    *,
    read_line: Optional[Callable[[str], str]] = None,
) -> str:
    """Single-line prompt (cooked terminal). Empty / EOF returns ``\"\"``."""
    if read_line is not None:
        return (read_line(message) or "").strip()
    try:
        return input(message).strip()
    except (EOFError, KeyboardInterrupt):
        return ""
