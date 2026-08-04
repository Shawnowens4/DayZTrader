import json
import os
import time
import urllib.error
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[4]
IMAGES_DIR = ROOT / "dxemb" / "web" / "static" / "items"
UNMATCHED_PATH = ROOT / "dxemb" / "shared" / "catalog" / "data" / "unmatched_classnames.txt"
LOG_PATH = ROOT / "dxemb" / "shared" / "catalog" / "data" / "dzpage_fetch_log.json"

API_KEY = os.environ.get("DZPAGE_API_KEY", "").strip()
if not API_KEY:
    raise SystemExit("Set DZPAGE_API_KEY environment variable before running.")

BASE_URL = "https://dzpage.com/api/v1/items/"
HEADERS = {
    "Authorization": f"Bearer {API_KEY}",
    "Accept": "application/json",
    "User-Agent": "DayZTrader/1.0",
}

REQUESTS_PER_MINUTE = 120
DELAY = 60.0 / REQUESTS_PER_MINUTE


def fetch_item(classname: str):
    url = BASE_URL + classname
    req = urllib.request.Request(url, headers=HEADERS)

    try:
        with urllib.request.urlopen(req, timeout=20) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            return data.get("item")

    except urllib.error.HTTPError as e:
        if e.code == 404:
            return None

        if e.code == 429:
            retry_after = int(e.headers.get("Retry-After", "5"))
            print(f"  rate limited on {classname}, sleeping {retry_after}s")
            time.sleep(retry_after)
            return fetch_item(classname)

        body = ""
        try:
            body = e.read().decode("utf-8", "ignore")[:300]
        except Exception:
            pass

        print(f"  HTTP {e.code} for {classname}: {body}")
        raise

    except Exception as e:
        print(f"  ERROR fetching {classname}: {e}")
        return None


def download_icon(url: str, dest: Path):
    req = urllib.request.Request(
        url,
        headers={
            "User-Agent": "DayZTrader/1.0",
            "Accept": "image/webp,image/*;q=0.8,*/*;q=0.5",
        },
    )
    with urllib.request.urlopen(req, timeout=20) as resp:
        dest.write_bytes(resp.read())


def main():
    unmatched = []
    if UNMATCHED_PATH.exists():
        unmatched = [u.strip() for u in UNMATCHED_PATH.read_text(encoding="utf-8").splitlines() if u.strip()]

    log = {}
    if LOG_PATH.exists():
        try:
            log = json.loads(LOG_PATH.read_text(encoding="utf-8-sig"))
        except Exception:
            log = {}

    downloaded = 0
    already_exists = 0
    not_found = 0
    no_icon_field = 0
    download_failed = 0

    total = len(unmatched)

    for i, classname in enumerate(unmatched, 1):
        if classname in log:
            continue

        item = fetch_item(classname)
        time.sleep(DELAY)

        if not item:
            log[classname] = {"status": "not_found"}
            not_found += 1
            print(f"[{i}/{total}] {classname}: not found")
            continue

        icon_url = item.get("icon_thumb") or item.get("icon")
        if not icon_url:
            log[classname] = {
                "status": "no_icon_field",
                "available_keys": sorted(item.keys()),
            }
            no_icon_field += 1
            print(f"[{i}/{total}] {classname}: no icon field")
            continue

        dest_name = classname.lower() + ".webp"
        dest_path = IMAGES_DIR / dest_name

        if dest_path.exists():
            log[classname] = {
                "status": "already_exists",
                "file": dest_name,
                "source_url": icon_url,
            }
            already_exists += 1
            print(f"[{i}/{total}] {classname}: already exists")
            continue

        try:
            download_icon(icon_url, dest_path)
            log[classname] = {
                "status": "downloaded",
                "file": dest_name,
                "source_url": icon_url,
            }
            downloaded += 1
            print(f"[{i}/{total}] {classname}: downloaded -> {dest_name}")
        except Exception as e:
            log[classname] = {
                "status": "download_failed",
                "error": str(e),
                "source_url": icon_url,
            }
            download_failed += 1
            print(f"[{i}/{total}] {classname}: download failed ({e})")

        if i % 20 == 0:
            LOG_PATH.write_text(json.dumps(log, indent=2), encoding="utf-8")

    LOG_PATH.write_text(json.dumps(log, indent=2), encoding="utf-8")

    print()
    print(f"Downloaded: {downloaded}")
    print(f"Already existed: {already_exists}")
    print(f"Not found: {not_found}")
    print(f"No icon field: {no_icon_field}")
    print(f"Download failed: {download_failed}")
    print(f"Log written to: {LOG_PATH}")
    print("Next: re-run build_thumbnail_map")


if __name__ == "__main__":
    main()