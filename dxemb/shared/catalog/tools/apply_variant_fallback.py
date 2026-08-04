# apply_variant_fallback.py
# Run inside container:
# docker compose exec bot sh -c "cd /app/dxemb && python -m shared.catalog.tools.apply_variant_fallback"

import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[4]
MAPPED_PATH = ROOT / "dxemb" / "shared" / "catalog" / "data" / "dayzidb_map.json"
UNMATCHED_PATH = ROOT / "dxemb" / "shared" / "catalog" / "data" / "unmatched_classnames.txt"

VARIANT_SUFFIXES = ("black","blue","white","wine","grey","gray","red","orange",
                    "green","camo","rust","brown","yellow","olive","tan","violet")

def base_of(name):
    pattern = r"_(" + "|".join(VARIANT_SUFFIXES) + r")(rust)?$"
    return re.sub(pattern, "", name, flags=re.IGNORECASE)

mapped = json.loads(MAPPED_PATH.read_text(encoding="utf-8-sig"))
unmatched = UNMATCHED_PATH.read_text(encoding="utf-8").splitlines() if UNMATCHED_PATH.exists() else []

still_unmatched = []
fallback_applied = 0

for cls in unmatched:
    base = base_of(cls)
    base_key = base.strip().lower()
    key = cls.strip().lower()
    if base_key in mapped:
        mapped[key] = mapped[base_key]
        fallback_applied += 1
    else:
        still_unmatched.append(cls)

MAPPED_PATH.write_text(json.dumps(mapped, indent=2, sort_keys=True), encoding="utf-8")
UNMATCHED_PATH.write_text("\n".join(sorted(still_unmatched)), encoding="utf-8")

print(f"Fallback matches applied: {fallback_applied}")
print(f"Total mapped now: {len(mapped)}")
print(f"Still unmatched: {len(still_unmatched)}")