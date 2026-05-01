#!/usr/bin/env python3
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "lib"))

from attune_meta_pack.actions import dispatch_from_env

if __name__ == "__main__":
    raise SystemExit(dispatch_from_env())
