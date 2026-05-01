"""Shared logic for the `attune.enqueue` and `attune.enqueue_batch` actions.

These actions POST one or more queue items to
``/api/v1/queues/{queue_ref}/items`` using the execution-scoped
``ATTUNE_API_TOKEN`` and ``ATTUNE_API_URL`` injected by the worker.

HTTP calls go through the vendored OpenAPI-generated client
(``attune_client.api.queues.enqueue_queue_item``) so the wire format stays in
lockstep with the API. Regenerate the client with
``packs.external/attune/.scripts/generate_client.sh`` after API schema changes.
"""

from __future__ import annotations

import json
from typing import Any

from .client_factory import build_client, import_symbol


class EnqueueActionError(Exception):
    """Raised for parameter / environment problems before any HTTP call."""


def _build_request_model(body: dict[str, Any]):
    """Convert a plain dict body into the generated request model.

    The server DTO (``EnqueueWorkQueueItemRequest``) accepts ``payload`` as any
    JSON value, but the generated client's ``EnqueueWorkQueueItemRequestPayload``
    wrapper assumes a dict. To preserve the original Rust contract — where
    payload could be any JSON value — we use the typed wrapper for objects and
    a tiny shim with a compatible ``to_dict()`` method for scalars/arrays.
    """
    EnqueueWorkQueueItemRequest = import_symbol(
        "attune_client.models.enqueue_work_queue_item_request",
        "EnqueueWorkQueueItemRequest",
    )
    EnqueueWorkQueueItemRequestPayload = import_symbol(
        "attune_client.models.enqueue_work_queue_item_request_payload",
        "EnqueueWorkQueueItemRequestPayload",
    )
    EnqueueWorkQueueItemRequestMetadata = import_symbol(
        "attune_client.models.enqueue_work_queue_item_request_metadata",
        "EnqueueWorkQueueItemRequestMetadata",
    )
    UNSET = import_symbol("attune_client.types", "UNSET")

    raw_payload = body["payload"]
    if isinstance(raw_payload, dict):
        payload: Any = EnqueueWorkQueueItemRequestPayload.from_dict(raw_payload)
    else:
        payload = _RawJsonValue(raw_payload)

    metadata: Any = UNSET
    if body.get("metadata") is not None:
        if not isinstance(body["metadata"], dict):
            raise EnqueueActionError("'metadata' must be an object")
        metadata = EnqueueWorkQueueItemRequestMetadata.from_dict(body["metadata"])

    return EnqueueWorkQueueItemRequest(
        payload=payload,
        item_key=body["item_key"] if body.get("item_key") else UNSET,
        priority=body["priority"] if body.get("priority") is not None else UNSET,
        metadata=metadata,
    )


class _RawJsonValue:
    """Duck-typed payload wrapper that returns any JSON value verbatim from
    ``to_dict()``. The generated request model serializes ``self.payload.to_dict()``
    into the request body, so this lets us pass non-object payloads through
    unchanged (matching the prior Rust action's contract)."""

    __slots__ = ("_value",)

    def __init__(self, value: Any) -> None:
        self._value = value

    def to_dict(self) -> Any:  # noqa: D401 - protocol method
        return self._value


def _extract_path(value: Any, path: str) -> str | None:
    """Walk a dotted JSON path and stringify the leaf if reachable.

    Mirrors the Rust implementation: scalar leaves (strings, numbers, bools)
    are stringified; ``None`` and missing keys return ``None``.
    """
    if not path:
        return None
    cur: Any = value
    for segment in path.split("."):
        if not segment:
            return None
        if not isinstance(cur, dict) or segment not in cur:
            return None
        cur = cur[segment]
    if cur is None:
        return None
    if isinstance(cur, bool):
        return "true" if cur else "false"
    if isinstance(cur, (str, int, float)):
        return str(cur)
    return None


def build_single_body(params: dict[str, Any]) -> dict[str, Any]:
    if "payload" not in params or params["payload"] is None:
        raise EnqueueActionError("missing required parameter: payload")
    body: dict[str, Any] = {"payload": params["payload"]}
    if params.get("item_key"):
        body["item_key"] = params["item_key"]
    if params.get("priority") is not None:
        body["priority"] = params["priority"]
    if params.get("metadata") is not None:
        body["metadata"] = params["metadata"]
    return body


def build_batch_body(
    entry: Any,
    shared_priority: int | None,
    shared_metadata: Any,
    item_key_field: str | None,
    index: int,
) -> dict[str, Any]:
    """Produce a single queue-item POST body from a batch ``items`` entry.

    Each entry can be either:
      * a bare payload (object/scalar/array), or
      * an envelope ``{payload, item_key?, priority?, metadata?}`` for
        per-item overrides.
    """
    env_item_key: str | None = None
    env_priority: int | None = None
    env_metadata: Any = None

    if isinstance(entry, dict) and "payload" in entry:
        payload = entry.get("payload")
        if payload is None:
            raise EnqueueActionError(f"entry {index} has no 'payload' field")
        env_item_key = entry.get("item_key") if isinstance(entry.get("item_key"), str) else None
        if isinstance(entry.get("priority"), int):
            env_priority = entry["priority"]
        env_metadata = entry.get("metadata")
    else:
        payload = entry

    if env_item_key is not None:
        item_key = env_item_key
    elif item_key_field:
        item_key = _extract_path(payload, item_key_field)
    else:
        item_key = None
    priority = env_priority if env_priority is not None else shared_priority
    metadata = env_metadata if env_metadata is not None else shared_metadata

    body: dict[str, Any] = {"payload": payload}
    if item_key:
        body["item_key"] = item_key
    if priority is not None:
        body["priority"] = priority
    if metadata is not None:
        body["metadata"] = metadata
    return body


def _response_to_result(index: int, data: Any) -> dict[str, Any]:
    """Translate the parsed ``WorkQueueItemResponse`` (or its dict form) into
    the per-item result row used by both action outputs."""
    if data is None:
        return {"index": index, "success": True}

    if hasattr(data, "to_dict"):
        try:
            data = data.to_dict()
        except Exception:
            data = {}

    if not isinstance(data, dict):
        return {"index": index, "success": True}

    out: dict[str, Any] = {"index": index, "success": True}
    if data.get("id") is not None:
        out["id"] = data["id"]
    if isinstance(data.get("queue_ref"), str):
        out["queue"] = data["queue_ref"]
    if isinstance(data.get("item_key"), str):
        out["item_key"] = data["item_key"]
    if data.get("priority") is not None:
        out["priority"] = data["priority"]
    status = data.get("status")
    if isinstance(status, str):
        out["status"] = status
    elif status is not None and hasattr(status, "value"):
        out["status"] = str(status.value)
    return out


def _error_to_result(index: int, message: str, http_status: int | None) -> dict[str, Any]:
    out: dict[str, Any] = {"index": index, "success": False, "error": message}
    if http_status is not None:
        out["http_status"] = http_status
    return out


def _extract_data_from_envelope(parsed: Any) -> Any:
    """The API wraps responses as ``ApiResponse<T>`` ``{ data, ... }``.

    ``parsed`` may be ``None`` (4xx without body), an ``ApiResponseWorkQueueItemResponse``
    instance, or a plain dict (depending on the endpoint variant).
    """
    if parsed is None:
        return None
    if hasattr(parsed, "data"):
        return parsed.data
    if isinstance(parsed, dict):
        return parsed.get("data")
    return None


def _post_one(client: Any, queue_ref: str, body: dict[str, Any]) -> tuple[bool, Any, int]:
    """POST a single body via the generated client.

    Returns ``(ok, result_data_or_error_message, http_status)``.
    """
    enqueue_sync_detailed = import_symbol(
        "attune_client.api.queues.enqueue_queue_item", "sync_detailed"
    )
    UnexpectedStatus = import_symbol("attune_client.errors", "UnexpectedStatus")

    try:
        request_model = _build_request_model(body)
    except EnqueueActionError as exc:
        return False, str(exc), 0
    except Exception as exc:
        return False, f"failed to build request: {exc}", 0

    try:
        response = enqueue_sync_detailed(ref=queue_ref, client=client, body=request_model)
    except UnexpectedStatus as exc:
        return False, f"HTTP {exc.status_code}: {exc.content!r}", int(exc.status_code)
    except Exception as exc:
        return False, str(exc), 0

    status_code = int(response.status_code)
    if status_code >= 400:
        body_text = ""
        try:
            body_text = response.content.decode("utf-8", errors="replace")
        except Exception:
            pass
        return False, f"HTTP {status_code}: {body_text}", status_code

    data = _extract_data_from_envelope(response.parsed)
    if data is None and response.content:
        # Fall back to raw JSON if the parsed model didn't materialize for any
        # reason — keeps the per-item output shape stable.
        try:
            envelope = json.loads(response.content)
            if isinstance(envelope, dict):
                data = envelope.get("data")
        except (ValueError, TypeError):
            data = None
    return True, data, status_code


def run_single(params: dict[str, Any]) -> dict[str, Any]:
    queue_ref = (params.get("queue_ref") or "").strip()
    if not queue_ref:
        raise EnqueueActionError("missing required parameter: queue_ref")

    body = build_single_body(params)

    try:
        client = build_client(params)
    except ValueError as exc:
        raise EnqueueActionError(str(exc)) from exc

    with client as bound:
        ok, data_or_err, status = _post_one(bound, queue_ref, body)

    if not ok:
        return {
            "success": False,
            "count": 0,
            "items": [_error_to_result(0, str(data_or_err), status or None)],
        }

    item = _response_to_result(0, data_or_err)
    return {
        "success": True,
        "count": 1,
        "id": item.get("id"),
        "queue": item.get("queue"),
        "item_key": item.get("item_key"),
        "priority": item.get("priority"),
        "status": item.get("status"),
        "items": [item],
    }


def run_batch(params: dict[str, Any]) -> dict[str, Any]:
    queue_ref = (params.get("queue_ref") or "").strip()
    if not queue_ref:
        raise EnqueueActionError("missing required parameter: queue_ref")

    items = params.get("items")
    if items is None:
        raise EnqueueActionError("missing required parameter: items")
    if not isinstance(items, list):
        raise EnqueueActionError("'items' must be an array")

    if not items:
        return {
            "success": True,
            "count": 0,
            "succeeded": 0,
            "failed": 0,
            "items": [],
        }

    shared_priority = params.get("priority")
    shared_metadata = params.get("metadata")
    item_key_field = params.get("item_key_field")

    try:
        client = build_client(params)
    except ValueError as exc:
        raise EnqueueActionError(str(exc)) from exc

    results: list[dict[str, Any]] = []
    succeeded = 0
    failed = 0

    with client as bound:
        for i, entry in enumerate(items):
            try:
                body = build_batch_body(
                    entry,
                    shared_priority if isinstance(shared_priority, int) else None,
                    shared_metadata,
                    item_key_field,
                    i,
                )
            except EnqueueActionError as exc:
                results.append(_error_to_result(i, str(exc), None))
                failed += 1
                continue

            ok, data_or_err, status = _post_one(bound, queue_ref, body)
            if ok:
                results.append(_response_to_result(i, data_or_err))
                succeeded += 1
            else:
                results.append(_error_to_result(i, str(data_or_err), status or None))
                failed += 1

    return {
        "success": failed == 0,
        "count": len(items),
        "succeeded": succeeded,
        "failed": failed,
        "items": results,
    }
