"""Turn Claude's markdown response into a clean text-to-speech utterance queue.

This is the workhorse of the plugin. It takes a raw markdown response and
returns an ordered list of ``Utterance`` objects, each tagged with a logical
voice (``"prose"`` or ``"header"``). Headings and blockquotes get the header
voice; everything else gets prose. Code blocks and tables are collapsed to a
short spoken pointer ("see codeblock below" / "see table below") rather than
being read character by character.

The point of returning a structured queue (rather than one big string) is that
``/tts preview`` can print exactly which voice says what, and the daemon can
switch the macOS ``say`` voice per utterance.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import List, Optional

PROSE = "prose"
HEADER = "header"

# Spoken stubs the sanitizer emits instead of reading a code block or table.
# A turn that is *only* these pointers is treated as junk and stays silent.
_POINTER_TEXTS = frozenset({"see codeblock below", "see table below"})
_MIN_SPEAK_WORDS = 3
_BRIEF_MAX_WORDS = 20
_SENTENCE_RE = re.compile(r".+?[.!?]")

# Word / extension pronunciation overrides. Seeded from the spec examples
# (``modes.py:12`` -> "mode dot pi, line 12"). This is intentionally a plain
# dict so it can be extended or overridden from config later.
DEFAULT_PRONUNCIATION = {
    "modes": "mode",
    "py": "pi",
    "js": "jay ess",
    "ts": "tee ess",
    "md": "markdown",
    "rs": "rust",
    "go": "go",
    "sh": "shell",
    "yml": "yaml",
    "cfg": "config",
}


@dataclass
class Utterance:
    voice: str  # PROSE or HEADER
    text: str

    def __repr__(self) -> str:  # nice output for /tts preview and test failures
        return f"[{self.voice}] {self.text}"


# --------------------------------------------------------------------------
# Inline transforms
# --------------------------------------------------------------------------

_CAMEL_RE = re.compile(r"[A-Z]+(?=[A-Z][a-z])|[A-Z]?[a-z]+|[A-Z]+|\d+")


def _split_identifier(ident: str) -> List[str]:
    """Split a snake_case / camelCase identifier into lowercase words."""
    words: List[str] = []
    for part in ident.split("_"):
        if not part:
            continue
        words.extend(m.group(0) for m in _CAMEL_RE.finditer(part))
    return [w.lower() for w in words] or [ident.lower()]


def _render_identifier(ident: str) -> str:
    """Speak a code identifier as an English "... function" phrase.

    Rules derived from the spec examples:
      build()       -> "the build function"   (single lowercase word)
      load_config   -> "the load config function"  (snake_case)
      loadConfig()  -> "load config function"  (camelCase, multi-word)
    """
    words = _split_identifier(ident)
    spoken = " ".join(words)
    has_underscore = "_" in ident
    single_lower_word = len(words) == 1
    prefix = "the " if (has_underscore or single_lower_word) else ""
    return f"{prefix}{spoken} function"


def _pronounce_word(word: str, pron: dict) -> str:
    return pron.get(word.lower(), word)


# `path/to/modes.py:12`  ->  "mode dot pi, line 12"  (optional backticks / path)
_FILE_LINE_RE = re.compile(
    r"`?(?:[\w./-]*/)?([A-Za-z0-9_-]+)\.([A-Za-z0-9]+):(\d+)`?"
)
# build()  loadConfig()  `parse()`  ->  function phrase
_FUNC_CALL_RE = re.compile(r"`?\b([A-Za-z_][A-Za-z0-9_]*)\(\)`?")
# any leftover backtick code span
_CODESPAN_RE = re.compile(r"`([^`]+)`")
# bare snake_case token (underscores don't occur in normal prose)
_BARE_SNAKE_RE = re.compile(r"\b([a-z0-9]+(?:_[a-z0-9]+)+)\b")
# bare ":300"  ->  "line 300"  (colon not attached to a preceding word/number)
_LINE_REF_RE = re.compile(r"(?<![A-Za-z0-9]):(\d+)\b")
# "~20"  ->  "about 20"
_APPROX_RE = re.compile(r"~(\d+)")
# markdown link [text](url) -> text
_LINK_RE = re.compile(r"\[([^\]]+)\]\([^)]*\)")
# emphasis markers
_BOLD_STAR_RE = re.compile(r"\*\*(.+?)\*\*")
_BOLD_USCORE_RE = re.compile(r"__(.+?)__")
_ITALIC_STAR_RE = re.compile(r"\*(.+?)\*")
_ITALIC_USCORE_RE = re.compile(r"(?<![A-Za-z0-9])_(?!_)(.+?)(?<!_)_(?![A-Za-z0-9])")


def _codespan_repl(m: "re.Match", pron: dict) -> str:
    inner = m.group(1).strip()
    if re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", inner):
        return _render_identifier(inner)
    return inner  # arbitrary inline code: speak it plainly, drop the backticks


def transform_inline(text: str, pron: dict | None = None) -> str:
    """Apply all inline substitutions and return clean spoken text."""
    pron = pron or DEFAULT_PRONUNCIATION

    def file_repl(m: "re.Match") -> str:
        name = _pronounce_word(m.group(1), pron)
        ext = _pronounce_word(m.group(2), pron)
        return f"{name} dot {ext}, line {m.group(3)}"

    text = _LINK_RE.sub(r"\1", text)
    text = _FILE_LINE_RE.sub(file_repl, text)
    text = _FUNC_CALL_RE.sub(lambda m: _render_identifier(m.group(1)), text)
    text = _CODESPAN_RE.sub(lambda m: _codespan_repl(m, pron), text)
    text = _BARE_SNAKE_RE.sub(lambda m: _render_identifier(m.group(1)), text)
    text = _LINE_REF_RE.sub(r"line \1", text)
    text = _APPROX_RE.sub(r"about \1", text)
    # emphasis: bold before italic so ** isn't eaten by the * rule
    text = _BOLD_STAR_RE.sub(r"\1", text)
    text = _BOLD_USCORE_RE.sub(r"\1", text)
    text = _ITALIC_STAR_RE.sub(r"\1", text)
    text = _ITALIC_USCORE_RE.sub(r"\1", text)

    return re.sub(r"\s+", " ", text).strip()


# --------------------------------------------------------------------------
# Block parsing
# --------------------------------------------------------------------------

_HEADING_RE = re.compile(r"^\s{0,3}#{1,6}\s+(.*?)\s*#*\s*$")
_FENCE_RE = re.compile(r"^\s*(```+|~~~+)")
_BLOCKQUOTE_RE = re.compile(r"^\s*>\s?(.*)$")
_LIST_RE = re.compile(r"^\s*(?:[-*+]|\d+[.)])\s+(.*)$")
_TABLE_SEP_RE = re.compile(r"^\s*\|?\s*:?-{1,}:?\s*(\|\s*:?-{1,}:?\s*)+\|?\s*$")


@dataclass
class _Block:
    kind: str  # heading | code | table | blockquote | list | paragraph
    utterances: List[Utterance]


def _parse_blocks(md: str, pron: dict) -> List[_Block]:
    lines = md.splitlines()
    blocks: List[_Block] = []
    i = 0
    n = len(lines)

    while i < n:
        line = lines[i]

        # blank line
        if not line.strip():
            i += 1
            continue

        # fenced code block -> single pointer utterance
        if _FENCE_RE.match(line):
            fence = _FENCE_RE.match(line).group(1)[0]
            i += 1
            while i < n and not re.match(rf"^\s*{re.escape(fence)}{{3,}}", lines[i]):
                i += 1
            i += 1  # consume closing fence
            blocks.append(_Block("code", [Utterance(PROSE, "see codeblock below")]))
            continue

        # heading
        m = _HEADING_RE.match(line)
        if m:
            text = transform_inline(m.group(1), pron)
            if text:
                blocks.append(_Block("heading", [Utterance(HEADER, text)]))
            i += 1
            continue

        # table: a pipe row immediately followed by a separator row
        if "|" in line and i + 1 < n and _TABLE_SEP_RE.match(lines[i + 1]):
            i += 2
            while i < n and "|" in lines[i] and lines[i].strip():
                i += 1
            blocks.append(_Block("table", [Utterance(PROSE, "see table below")]))
            continue

        # blockquote (contiguous) -> header/alt voice
        if _BLOCKQUOTE_RE.match(line):
            quoted: List[str] = []
            while i < n and _BLOCKQUOTE_RE.match(lines[i]):
                quoted.append(_BLOCKQUOTE_RE.match(lines[i]).group(1))
                i += 1
            text = transform_inline(" ".join(quoted), pron)
            if text:
                blocks.append(_Block("blockquote", [Utterance(HEADER, text)]))
            continue

        # list: each item its own prose utterance
        if _LIST_RE.match(line):
            items: List[Utterance] = []
            while i < n and _LIST_RE.match(lines[i]):
                text = transform_inline(_LIST_RE.match(lines[i]).group(1), pron)
                if text:
                    items.append(Utterance(PROSE, text))
                i += 1
            if items:
                blocks.append(_Block("list", items))
            continue

        # paragraph: contiguous plain lines
        para: List[str] = []
        while i < n and lines[i].strip() and not (
            _FENCE_RE.match(lines[i])
            or _HEADING_RE.match(lines[i])
            or _BLOCKQUOTE_RE.match(lines[i])
            or _LIST_RE.match(lines[i])
        ):
            para.append(lines[i])
            i += 1
        text = transform_inline(" ".join(para), pron)
        if text:
            blocks.append(_Block("paragraph", [Utterance(PROSE, text)]))

    return blocks


# --------------------------------------------------------------------------
# Public API
# --------------------------------------------------------------------------


def _first_sentence(text: str, max_words: int = _BRIEF_MAX_WORDS) -> str:
    """First sentence of ``text``, capped at ``max_words``."""
    text = (text or "").strip()
    if not text:
        return ""
    m = _SENTENCE_RE.match(text)
    chunk = m.group(0).strip() if m else text
    words = chunk.split()
    if len(words) > max_words:
        return " ".join(words[:max_words])
    return chunk


def _is_junk(utterances: List[Utterance]) -> bool:
    """True when the queue is empty, pointer-only, or shorter than a real reply."""
    texts = [u.text.strip() for u in utterances if u.text and u.text.strip()]
    if not texts:
        return True
    stripped = [re.sub(r"[.!?]+$", "", t.lower()).strip() for t in texts]
    if all(s in _POINTER_TEXTS for s in stripped):
        return True
    return sum(len(t.split()) for t in texts) < _MIN_SPEAK_WORDS


def _lead_block(blocks: List[_Block]) -> Optional[_Block]:
    for b in blocks:
        if b.kind == "paragraph":
            return b
    return blocks[0] if blocks else None


def sanitize(markdown: str, mode: str = "full", pron: dict | None = None) -> List[Utterance]:
    """Convert a markdown response into an utterance queue.

    ``mode="full"``    -> every block.
    ``mode="summary"`` -> only the lead paragraph (first prose paragraph block).
    ``mode="closing"`` -> only the last prose paragraph (the usual answer).
    ``mode="brief"``   -> first sentence of the lead paragraph, capped at 20 words.
    Pointer-only or very short queues are dropped so they are never spoken.
    """
    pron = pron or DEFAULT_PRONUNCIATION
    blocks = _parse_blocks(markdown or "", pron)

    if mode == "summary":
        lead = _lead_block(blocks)
        out = list(lead.utterances) if lead else []
    elif mode == "closing":
        paras = [b for b in blocks if b.kind == "paragraph"]
        chosen = paras[-1] if paras else (blocks[-1] if blocks else None)
        out = list(chosen.utterances) if chosen else []
    elif mode == "brief":
        lead = _lead_block(blocks)
        if not lead or not lead.utterances:
            out = []
        else:
            text = " ".join(u.text for u in lead.utterances)
            sentence = _first_sentence(text)
            voice = lead.utterances[0].voice
            out = [Utterance(voice, sentence)] if sentence else []
    else:
        out = []
        for b in blocks:
            out.extend(b.utterances)

    return [] if _is_junk(out) else out
