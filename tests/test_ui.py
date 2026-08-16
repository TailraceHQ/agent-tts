"""Tests for the stdlib radio-list selector."""

from tts_reader.ui import BACK, EXIT, _frame, _items, prompt_line, radio_select


def _drive(keys, **kwargs):
    it = iter(keys)
    return radio_select(
        "Title",
        [("a", "Alpha"), ("b", "Bravo")],
        read_key=lambda: next(it),
        write=lambda s: None,
        **kwargs,
    )


def test_enter_saves_preselected_without_space():
    assert _drive(["enter"], selected_id="a") == "a"


def test_space_selects_then_enter_saves():
    # cursor starts on a; down to b; space fills b; enter saves b
    assert _drive(["down", "space", "enter"], selected_id="a") == "b"


def test_enter_on_exit_commits_immediately():
    # a -> b -> back -> exit
    assert _drive(["down", "down", "down", "enter"]) == EXIT


def test_space_then_enter_on_back():
    # a -> b -> back; space selects back; enter saves
    assert _drive(["down", "down", "space", "enter"]) == BACK


def test_esc_exits():
    assert _drive(["esc"]) == EXIT


def test_empty_choices_exit():
    assert radio_select("T", [], read_key=lambda: "enter", write=lambda s: None) == EXIT


def test_frame_uses_crlf_so_raw_ttys_do_not_staircase():
    glyphs = {"dot": "*", "empty": " ", "cursor": ">", "rule": "-" * 8}
    items = _items([("a", "Alpha"), ("b", "Bravo")], allow_back=True, glyphs=glyphs)
    frame = _frame("Cloud voice setup\nWhich provider?", items, 0, "a", glyphs)
    assert "\r\n" in frame
    assert frame.replace("\r\n", "").find("\n") == -1
    for label in ("Alpha", "Bravo", "Go back", "Exit", "Which provider?"):
        assert label in frame


def test_prompt_line_injectable():
    assert prompt_line("Name: ", read_line=lambda msg: " OPEN_AI_ALLOY_VOICE_KEY ") == (
        "OPEN_AI_ALLOY_VOICE_KEY"
    )
