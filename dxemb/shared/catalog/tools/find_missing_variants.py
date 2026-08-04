# find_missing_variants.py
# Run inside container: docker compose exec bot sh -c "cd /app/dxemb && python -m shared.catalog.tools.find_missing_variants"

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[4]
MAPPED_PATH = ROOT / "dxemb" / "shared" / "catalog" / "data" / "dayzidb_map.json"
UNMATCHED_PATH = ROOT / "dxemb" / "shared" / "catalog" / "data" / "unmatched_classnames.txt"

mapped = json.loads(MAPPED_PATH.read_text(encoding="utf-8-sig"))
unmatched = UNMATCHED_PATH.read_text(encoding="utf-8").splitlines() if UNMATCHED_PATH.exists() else []

import re
VARIANT_SUFFIXES = ("black","blue","white","wine","grey","gray","red","orange",
                    "green","camo","rust","brown","yellow","olive","tan","violet")

def base_of(name):
    pattern = r"_(" + "|".join(VARIANT_SUFFIXES) + r")(rust)?$"
    return re.sub(pattern, "", name, flags=re.IGNORECASE)

groups = {}
for cls in unmatched:
    b = base_of(cls)
    groups.setdefault(b, []).append(cls)

report = []
for base, siblings in groups.items():
    base_key = base.strip().lower()
    if base_key in mapped:
        report.append((base, siblings))

print(f"Vehicle/asset families with a mapped default but missing color variants: {len(report)}")
for base, siblings in sorted(report):
    print(f"  {base}: missing {siblings}")