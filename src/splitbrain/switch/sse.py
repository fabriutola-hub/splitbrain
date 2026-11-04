"""Pure incremental Server-Sent Events parser for the Switch agent bridge."""

from __future__ import annotations

import codecs
from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class SSEFrame:
    id: str | None
    event: str | None
    data: str


class SSEParser:
    """Feed byte or text chunks in any split; collect completed frames.

    Switch writes keepalives as bare comment lines and sends one `data:` line
    per frame, but the parser implements multi-line data and split UTF-8 too.
    """

    def __init__(self) -> None:
        self._decoder = codecs.getincrementaldecoder("utf-8")(errors="replace")
        self._buffer = ""
        self._data_lines: list[str] = []
        self._event: str | None = None
        self._last_event_id: str | None = None

    def feed(self, chunk: bytes | str) -> list[SSEFrame]:
        text = self._decoder.decode(chunk) if isinstance(chunk, bytes) else chunk
        # CRLF split across two chunks is reassembled before lines are cut.
        self._buffer += text.replace("\r\n", "\n")
        lines = self._buffer.split("\n")
        self._buffer = lines.pop()
        frames: list[SSEFrame] = []
        for line in lines:
            frame = self._consume(line.rstrip("\r"))
            if frame is not None:
                frames.append(frame)
        return frames

    def _consume(self, line: str) -> SSEFrame | None:
        if line == "":
            return self._dispatch()
        if line.startswith(":"):
            return None
        field, _, value = line.partition(":")
        if value.startswith(" "):
            value = value[1:]
        if field == "data":
            self._data_lines.append(value)
        elif field == "event":
            self._event = value
        elif field == "id":
            self._last_event_id = value
        # `retry` and unknown fields are ignored by design.
        return None

    def _dispatch(self) -> SSEFrame | None:
        if not self._data_lines:
            self._event = None
            return None
        frame = SSEFrame(
            id=self._last_event_id,
            event=self._event,
            data="\n".join(self._data_lines),
        )
        self._data_lines = []
        self._event = None
        # The last event id buffer persists across frames per the SSE spec.
        return frame
