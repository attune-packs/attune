import json
import sys
from typing import Any


def read_params() -> dict[str, Any]:
    raw = sys.stdin.read().strip()
    if not raw:
        return {}
    return json.loads(raw)


def emit_json(payload: Any) -> int:
    print(json.dumps(payload, indent=2, sort_keys=True, default=str))
    return 0


def fail(message: str, *, details: Any | None = None, code: int = 1) -> int:
    payload: dict[str, Any] = {"success": False, "error": message}
    if details is not None:
        payload["details"] = details
    print(json.dumps(payload, indent=2, sort_keys=True, default=str), file=sys.stderr)
    return code
