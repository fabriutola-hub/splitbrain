"""Unit tests for the pure incremental SSE parser."""

from __future__ import annotations

import pytest

from splitbrain.switch.sse import SSEParser


def test_single_frame() -> None:
    parser = SSEParser()
    frames = parser.feed(b'id: 42\nevent: message\ndata: {"a":1}\n\n')
    assert len(frames) == 1
    assert frames[0].id == "42"
    assert frames[0].event == "message"
    assert frames[0].data == '{"a":1}'


def test_keepalive_comments_are_ignored() -> None:
    parser = SSEParser()
    assert parser.feed(b": keepalive\n\n") == []
    assert parser.feed(b": another comment\n\n") == []
    frames = parser.feed(b'event: message\ndata: {"ok":true}\n\n')
    assert len(frames) == 1
    assert frames[0].data == '{"ok":true}'


def test_multiline_data_is_joined_with_newlines() -> None:
    parser = SSEParser()
    frames = parser.feed(b"data: first\ndata: second\n\n")
    assert len(frames) == 1
    assert frames[0].data == "first\nsecond"


def test_crlf_and_blank_frame_without_data() -> None:
    parser = SSEParser()
    assert parser.feed(b"\r\n\r\n") == []
    frames = parser.feed(b"event: message\r\ndata: {}\r\n\r\n")
    assert len(frames) == 1
    assert frames[0].event == "message"
    assert frames[0].data == "{}"


@pytest.mark.parametrize("split_at", [1, 5, 11, 17, 23])
def test_arbitrary_byte_chunk_splits(split_at: int) -> None:
    raw = 'id: 9007194959773697\nevent: message\ndata: {"body":"caf\u00e9"}\n\n'.encode()
    first = raw[:split_at]
    second = raw[split_at:]
    parser = SSEParser()
    assert parser.feed(first) == []
    frames = parser.feed(second)
    assert len(frames) == 1
    assert frames[0].id == "9007194959773697"
    assert frames[0].event == "message"
    assert frames[0].data == '{"body":"caf\u00e9"}'


def test_split_multibyte_character() -> None:
    raw = 'data: {"body":"caf\u00e9"}\n\n'.encode()
    split = raw.index(b"\xc3") + 1
    parser = SSEParser()
    assert parser.feed(raw[:split]) == []
    frames = parser.feed(raw[split:])
    assert frames[0].data == '{"body":"caf\u00e9"}'


def test_last_event_id_persists_and_event_resets() -> None:
    parser = SSEParser()
    stream = b"id: 7\nevent: message\ndata: one\n\nevent: subscription_changed\ndata: two\n\n"
    frames = parser.feed(stream)
    assert len(frames) == 2
    assert frames[0].id == "7"
    assert frames[1].id == "7"
    assert frames[1].event == "subscription_changed"


def test_text_chunks_are_accepted() -> None:
    parser = SSEParser()
    assert parser.feed("data: hel") == []
    frames = parser.feed("lo\n\n")
    assert frames[0].data == "hello"
