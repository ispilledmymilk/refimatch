"""Emit JSON Schema for CompareRequest (run from repo root or package dir)."""

import json
import sys
from pathlib import Path

# Allow running without install
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from scoring.models import CompareRequest  # noqa: E402


def main() -> None:
    out = ROOT / "schemas" / "compare_request.schema.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    schema = json.dumps(CompareRequest.model_json_schema(), indent=2) + "\n"
    out.write_text(schema, encoding="utf-8")
    print(f"wrote {out}")


if __name__ == "__main__":
    main()
