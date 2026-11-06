"""A persistent Switch double with document ownership and threaded history."""

from __future__ import annotations

import asyncio
from contextlib import asynccontextmanager
from copy import deepcopy
from dataclasses import dataclass, field
from typing import Any

from splitbrain.switch.client import SwitchOpError


@dataclass
class SwitchState:
    documents: dict[str, dict[str, Any]] = field(default_factory=dict)
    threads: dict[str, list[dict[str, Any]]] = field(default_factory=dict)
    rooms: dict[str, str] = field(
        default_factory=lambda: {
            "r-ops": "splitbrain-ops",
            "r-sales": "sales",
            "r-engineering": "engineering",
            "r-conflict": "conflict-sb-0001-sso",
        }
    )
    holders: list[str] = field(default_factory=list)
    serial: int = 0

    def add_message(
        self, room_id: str, body: str, sender: str, *, thread_id: str | None = None
    ) -> str:
        self.serial += 1
        ident = f"sw_fake_{self.serial}"
        entry = {"id": ident, "body": body, "sender_name": sender, "timestamp": self.serial}
        threads = self.threads.setdefault(room_id, [])
        if thread_id:
            thread = next((item for item in threads if item["root"]["id"] == thread_id), None)
            if thread is None:
                self.add_origin(room_id, thread_id)
                thread = threads[-1]
            thread["replies"].append(entry)
        else:
            threads.append({"root": entry, "replies": []})
        return ident

    def add_origin(self, room_id: str, thread_id: str) -> None:
        self.threads.setdefault(room_id, []).append(
            {"root": {"id": thread_id, "sender_name": "maria", "body": "Original"}, "replies": []}
        )


class FakeSwitch:
    def __init__(self, name: str, state: SwitchState | None = None) -> None:
        self.name = name
        self.state = state or SwitchState()
        self.posts: list[dict[str, Any]] = []
        self.targeted_calls: list[dict[str, Any]] = []
        self.calls: list[tuple[str, dict[str, Any]]] = []
        self.connected_room = ""
        self.lock = asyncio.Lock()
        self.fail_before_room: str | None = None
        self.fail_after_room: str | None = None
        self.fail_next_update = False
        self.fail_checkpoint_after_post = False
        self.fail_targeted_after_send = False

    @asynccontextmanager
    async def act_in(self, room_id: str):
        async with self.lock:
            await self.op("connect_to_room", room_id=room_id)
            yield self

    async def op(self, name: str, /, **args: Any) -> Any:
        self.calls.append((name, args))
        if name in {"list_rooms", "list_all_rooms"}:
            return [{"room_id": key, "name": value} for key, value in self.state.rooms.items()]
        if name == "get_room_detail":
            return {"roles": [{"name": "arbiter", "held_by": self.state.holders}]}
        if name == "assume_role":
            self.state.holders = [self.name]
            return {}
        if name == "release_role":
            self.state.holders.remove(self.name)
            return {}
        if name == "connect_to_room":
            self.connected_room = args["room_id"]
            return {
                "documents": [
                    {"id": item["id"], "name": item["name"]}
                    for item in self.state.documents.values()
                    if item["room_id"] == self.connected_room
                ],
                "linked_rooms": [],
            }
        if name == "load_internal_documents":
            return [deepcopy(self.state.documents[key]) for key in args["ids"]]
        if name == "create_room_document":
            ident = f"doc-{len(self.state.documents) + 1}"
            self.state.documents[ident] = {
                "id": ident,
                "room_id": self.connected_room,
                "owner": self.name,
                **args,
            }
            return {"document_id": ident}
        if name == "update_room_document":
            if self.fail_next_update:
                self.fail_next_update = False
                raise RuntimeError("checkpoint failed")
            document = self.state.documents[args["document_id"]]
            if document["owner"] != self.name:
                raise SwitchOpError(name, 403, "Only the document creator can update it")
            document["content"] = args["content"]
            return {"document_id": args["document_id"]}
        if name == "read_context":
            return {
                "threads": deepcopy(self.state.threads.get(args["room_id"], [])[-args["limit"] :])
            }
        if name == "link_rooms":
            return {}
        raise AssertionError(f"Unexpected operation {name}: {args}")

    async def post(self, room_id: str, body: str, thread_id: str | None = None) -> dict[str, str]:
        if self.fail_before_room == room_id:
            self.fail_before_room = None
            raise RuntimeError("publication failed")
        ident = self.state.add_message(room_id, body, self.name, thread_id=thread_id)
        self.posts.append({"room_id": room_id, "body": body, "thread_id": thread_id, "id": ident})
        if self.fail_checkpoint_after_post:
            self.fail_checkpoint_after_post = False
            self.fail_next_update = True
        if self.fail_after_room == room_id:
            self.fail_after_room = None
            raise RuntimeError("publication response lost")
        return {"event_id": ident}

    async def targeted(self, room_id: str, body: str, **args: Any) -> dict[str, str]:
        ident = self.state.add_message(room_id, body, self.name, thread_id=args.get("thread_id"))
        self.targeted_calls.append({"room_id": room_id, "body": body, **args})
        if self.fail_targeted_after_send:
            self.fail_targeted_after_send = False
            raise RuntimeError("targeted response lost")
        return {"event_id": ident}
