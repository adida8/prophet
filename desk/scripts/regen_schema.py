"""Regenerate desk/contract.schema.json from the Pydantic models.

Run from desk/:  python3 scripts/regen_schema.py

The output is committed; CI verifies it stays in sync (see
tests/test_contract.py::test_schema_file_in_sync).
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from desk.publish.contract import MatchOutput, OutputIndex  # noqa: E402

SCHEMA_PATH = ROOT / "desk" / "contract.schema.json"


def build_schema() -> dict:
    return {
        "MatchOutput": MatchOutput.model_json_schema(),
        "OutputIndex": OutputIndex.model_json_schema(),
    }


if __name__ == "__main__":
    SCHEMA_PATH.write_text(
        json.dumps(build_schema(), indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(f"wrote {SCHEMA_PATH}")
