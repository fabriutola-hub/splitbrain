# Recovering a lost room claim

Two processes using the same agent identity can displace each other's room
claim. The connection lock serializes calls within one `SwitchAgent`; it cannot
serialize another process. A successful `connect_to_room` therefore does not
guarantee that the next operation still has a room.

## Retry contract

`SwitchAgent.op` recovers only inside the calling task's `act_in(room_id)` or
`connect_in(room_id)` scope, with the connection header enabled and an operation
in `ROOM_CLAIM_RETRY_OPS`. The trigger must be HTTP 400 with a JSON object whose
`detail` is exactly:

```text
Not connected to a room. Call connect_to_room first.
```

There are **three attempts total** per operation. Before each of the two retries,
the client waits a random 50–150 ms, reconnects to the scope's original room
using the same connection, and repeats only the rejected operation with the
same arguments. It keeps the local lock throughout. It never reruns the scope
or an earlier successful operation. A reconnect failure propagates immediately.
Exhaustion raises the original `SwitchOpError`, with an exception note and an
error log identifying the operation, room and three-attempt limit. Cancellation
propagates and clears the scope before releasing the lock.

Other 400s, 403s, 409s, 5xx responses and transport errors are not retried by this
policy. A missing response can mean a write committed; automatically replaying
it could duplicate a message. Unknown operations, calls without a connection,
calls outside a scope, and calls from another task do not inherit recovery.

Decision-record and correction-journal readers use this same client policy;
there is no additional document-read retry budget in `decision_record.py`.
The recovery demo's existing timeout loop can still repeat a whole read-only
observation after a transient error. That outer loop never publishes messages
or edits documents.

## Why each supported retry is safe

Source review: Switch revision `e47cab4b7b62f1a4b1857d1cc59e4bb7bfdd8d72`.
Paths below are relative to Switch's `core/` directory.

`switch_core/bridges/agent/operations/context.py:127–150` resolves the connected
room and raises the exact `ValueError` above when the room set is empty. The
HTTP adapter maps `ValueError` to 400 in
`switch_core/bridges/agent/api/operations.py:66–82`, and returns its text as
`detail` at lines 350–354. For every allowlisted operation below, that guard
precedes the call that performs the operation's effect.

| Operation | Guard before the effect in `switch_core/bridges/agent/operations/definitions.py` | Safety argument |
| --- | --- | --- |
| `load_internal_documents` | Lines 541–548: resolve room, then `request_document_load`. | Read only; the rejected attempt has not loaded documents. |
| `update_room_document` | Lines 612–624: resolve room, then `request_room_document_update`. | The rejected attempt has not updated the document or announced an update. The same document ID and full content are sent again. Content is assigned, not appended, by `switch_core/db/stores/document_store.py:65–66`. |
| `create_room_document` | Lines 580–591: resolve room, then `request_room_document_create`. | Creation is not idempotent. This specific refusal happens before a document is created or announced; the retry creates it once. |
| `post_message` | Lines 795–799: resolve room, then `send_message`. | Posting is not idempotent. This refusal happens before publishing anything; only the successful attempt publishes. |
| `send_targeted_message` | Lines 864–875: resolve room, then `send_targeted_message`. | Neither message publication nor targeted delivery has started when the guard refuses the call. Successful earlier sends are never repeated. |
| `assume_role` | Lines 1144–1149: resolve room, then `assume_room_role`. | No lease has been acquired on the rejected attempt. The retry still has to pass Switch's normal exclusivity checks. |
| `release_role` | Lines 1155–1157: resolve room, then `release_room_role`. | Release has not begun on the rejected attempt; the operation is also documented as idempotent. |

The allowlist covers the implicit-room operations currently used by Splitbrain.
Other operations remain single-attempt until their guard ordering has been
reviewed. This is not a general guarantee of exactly-once delivery across
transport failures, process crashes or unlimited contention.

## Observer contention

`connect_to_room` accepts `room_id` and `include_general_instructions`, with no
non-takeover argument (`definitions.py:252–255`). Its claim helper calls
`claim_room(..., takeover=True)` at line 123. `load_internal_documents` requires
a connected room and takes document IDs, with no explicit-room read argument
(lines 528–548). `read_context(room_id=...)` can read a conversation without
connecting (lines 699–705), but does not return internal document content.

The observer therefore still claims the room to inspect recovery documents.
Its polling pause is increased from 0.5 s to 1 s, halving the maximum steady
poll rate and giving the worker more time between claims. The 120 s observation
timeout and duplicate checks stay in place. This reduces contention; bounded
client recovery handles losses that still occur.

## Verification and live follow-up

Unit tests use fake pre-effect refusals and post-effect ambiguous failures.
They cover all seven supported operations with one or two losses, the fixed
limit, exact error matching, isolation by task and room, cancellation, failed
reconnects, and both creation and update in `Sentinel._save_corrections`.
They also check that retrying a later save does not repeat an earlier creation
or either kind of chat message.

With the shared live stack, repeat
`test_recovery_demo_preserves_the_case_across_both_process_failures` and the
recovery demo. Confirm that the restarted Sentinel saves its final journal,
each original thread has exactly one correction, there is one decision and one
conflict room, and the observer finishes without a dropped worker event or an
exhausted claim-recovery budget. Unit tests cannot establish fairness between
independent processes under continuous takeover.
