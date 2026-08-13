"""Tests for the markdown -> utterance-queue sanitizer.

Every transform called out in the spec is encoded here as a case. This is the
primary correctness gate and needs no audio hardware.
"""

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "scripts"))

from tts_reader.sanitize import (  # noqa: E402
    HEADER,
    PROSE,
    Utterance,
    sanitize,
    transform_inline,
)


def spoken(md, mode="full"):
    return [u.text for u in sanitize(md, mode)]


# ---- inline identifier / function transforms ----------------------------


def test_build_call():
    assert transform_inline("call build() now") == "call the build function now"


def test_snake_case_identifier():
    assert transform_inline("see load_config here") == "see the load config function here"


def test_camel_case_call():
    assert transform_inline("run loadConfig() ok") == "run load config function ok"


def test_backticked_identifier():
    assert transform_inline("the `build` helper") == "the the build function helper"


# ---- file:line and line references --------------------------------------


def test_file_line():
    assert transform_inline("edit `modes.py:12` please") == "edit mode dot pi, line 12 please"


def test_file_line_with_path():
    assert transform_inline("src/modes.py:12") == "mode dot pi, line 12"


def test_bare_line_ref():
    assert transform_inline("jump to :300 now") == "jump to line 300 now"


# ---- approx and emphasis -------------------------------------------------


def test_approx():
    assert transform_inline("about ~20 items") == "about about 20 items"


def test_bold_stripped():
    assert transform_inline("this is **very** bold") == "this is very bold"


def test_italic_stripped():
    assert transform_inline("this is *really* italic") == "this is really italic"


def test_underscore_italic_stripped():
    assert transform_inline("a _slanted_ word") == "a slanted word"


def test_link_stripped():
    assert transform_inline("see [the docs](http://x.y) now") == "see the docs now"


# ---- block-level transforms ---------------------------------------------


def test_code_block_becomes_pointer():
    md = "Here is code:\n\n```python\nprint('x')\n```\n"
    assert "see codeblock below" in spoken(md)
    assert "print" not in " ".join(spoken(md))


def test_table_becomes_pointer():
    md = "Data:\n\n| a | b |\n| - | - |\n| 1 | 2 |\n"
    assert "see table below" in spoken(md)


def test_heading_uses_header_voice():
    md = "# Overview\n\nSome text.\n"
    utts = sanitize(md, "full")
    heading = [u for u in utts if u.text == "Overview"]
    assert heading and heading[0].voice == HEADER


def test_blockquote_uses_header_voice():
    md = "> a quoted line\n\nbody\n"
    utts = sanitize(md, "full")
    quote = [u for u in utts if "quoted" in u.text]
    assert quote and quote[0].voice == HEADER


def test_paragraph_uses_prose_voice():
    utts = sanitize("Just a sentence.", "full")
    assert utts == [Utterance(PROSE, "Just a sentence.")]


# ---- summary mode --------------------------------------------------------


def test_summary_is_lead_paragraph_only():
    md = "# Title\n\nLead paragraph here.\n\nSecond paragraph.\n"
    assert spoken(md, "summary") == ["Lead paragraph here."]


def test_summary_skips_leading_heading():
    md = "## Heading\n\nFirst real paragraph.\n"
    utts = sanitize(md, "summary")
    assert all(u.voice == PROSE for u in utts)
    assert utts[0].text == "First real paragraph."


def test_closing_is_last_paragraph_only():
    md = "# Title\n\nI will look at the file.\n\nThe tests are green now.\n"
    assert spoken(md, "closing") == ["The tests are green now."]


def test_closing_falls_back_to_last_block_without_paragraph():
    md = "# Only a heading\n\n```python\nprint(1)\n```\n"
    # heading + pointer; last paragraph is absent so last block is the pointer,
    # which is junk and stays silent.
    assert spoken(md, "closing") == []


def test_brief_is_first_sentence_of_lead():
    md = "I checked the hook. Then I rewrote the daemon. Finally tests.\n"
    assert spoken(md, "brief") == ["I checked the hook."]


def test_brief_caps_long_sentence():
    words = " ".join(f"w{i}" for i in range(30))
    assert spoken(words, "brief") == [" ".join(f"w{i}" for i in range(20))]


def test_pointer_only_turn_is_silent():
    md = "```python\nprint('x')\n```\n"
    assert spoken(md, "full") == []


def test_short_ack_is_silent():
    assert spoken("Done.", "full") == []
    assert spoken("OK.", "summary") == []


def test_code_plus_prose_still_speaks_prose():
    md = "Here is the approach I took.\n\n```python\nprint('x')\n```\n"
    texts = spoken(md, "full")
    assert any("approach" in t for t in texts)
    assert "see codeblock below" in texts


# ---- ordering / voice tagging end-to-end --------------------------------


def test_full_queue_order_and_voices():
    md = "# Setup\n\nRun build() first.\n\n> note this\n"
    utts = sanitize(md, "full")
    assert utts == [
        Utterance(HEADER, "Setup"),
        Utterance(PROSE, "Run the build function first."),
        Utterance(HEADER, "note this"),
    ]
