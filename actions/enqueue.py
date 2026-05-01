#!/usr/bin/env python3
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "lib"))

import json

from attune_meta_pack.enqueue import EnqueueActionError, run_single
from attune_meta_pack.io import read_params


def main() -> int:
    try:
        params = read_params()
        result = run_single(params)
    except EnqueueActionError as exc:
        out = {
            "success": False,
            "count": 0,
            "items": [{"index": 0, "success": False, "error": str(exc)}],
        }
        print(json.dumps(out))
        return 1
    except Exception as exc:  # pragma: no cover - defensive
        out = {
            "success": False,
            "count": 0,
            "items": [
                {"index": 0, "success": False, "error": f"Unhandled error: {exc}"}
            ],
        }
        print(json.dumps(out))
        return 1

    print(json.dumps(result))
    return 0 if result.get("success") else 1


if __name__ == "__main__":
    raise SystemExit(main())
