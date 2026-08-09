from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

DXEMB_ROOT = Path(__file__).resolve().parents[4] / "dxemb"
if str(DXEMB_ROOT) not in sys.path:
    sys.path.insert(0, str(DXEMB_ROOT))

from shared.catalog.service import import_types_xml_foundation_sync
from shared.catalog.types_xml import TypesXmlParseError


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Import DayZ types.xml into the catalog item table with dry-run/apply modes."
    )
    parser.add_argument(
        "--types-path",
        default=None,
        help="Explicit path to types.xml. If omitted, uses TYPES_XML_PATH then bundled default.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Parse and report only. Do not write to the database.",
    )
    return parser


def _sanitize_report(report: dict[str, Any]) -> dict[str, Any]:
    out = dict(report)
    if "resolved_path" in out:
        out.pop("resolved_path")
    return out


def main() -> int:
    args = _parser().parse_args()

    try:
        report = import_types_xml_foundation_sync(path=args.types_path, dry_run=args.dry_run)
    except FileNotFoundError as exc:
        print(json.dumps({"error": str(exc)}, indent=2, sort_keys=True))
        return 2
    except TypesXmlParseError as exc:
        print(json.dumps({"error": str(exc)}, indent=2, sort_keys=True))
        return 3
    except Exception as exc:  # pragma: no cover - defensive top-level trap
        print(json.dumps({"error": f"unexpected import failure: {exc}"}, indent=2, sort_keys=True))
        return 1

    print(json.dumps(_sanitize_report(report), indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
