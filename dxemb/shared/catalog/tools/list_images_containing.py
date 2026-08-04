import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[4]
IMAGES_DIR = ROOT / "dxemb" / "web" / "static" / "items"

terms = [t.lower() for t in sys.argv[1:]]
if not terms:
    print("Usage: list_images_containing.py <term1> <term2> ...")
    sys.exit(1)

files = sorted(f.name for f in IMAGES_DIR.glob("*.webp"))
print(f"Total image files: {len(files)}\n")

for term in terms:
    matches = [f for f in files if term in f.lower()]
    print(f"--- '{term}' ({len(matches)} matches) ---")
    for m in matches:
        print(f"  {m}")
    print()