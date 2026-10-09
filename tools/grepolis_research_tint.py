#!/usr/bin/env python3
"""
Download every research icon from the Grepolis EN wiki Research Portal
and make green, yellow and red tinted versions of each.

Icons you already have are skipped, and requests the wiki rate-limits
(HTTP 429) are retried with a growing wait, so you can simply run it again.

Usage:
    python3 grepolis_research_tint.py                 # fetch whatever is missing
    python3 grepolis_research_tint.py --force         # re-download everything
    python3 grepolis_research_tint.py --strength 0.6  # stronger tint

Output (inside the grepolis_research_icons folder):
    original/<research>.png
    green/<research>_green.png
    yellow/<research>_yellow.png
    red/<research>_red.png
"""

import argparse
import io
import os
import subprocess
import sys
import tempfile
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

from PIL import Image

WIKI = "https://wiki.en.grepolis.com/wiki/Special:FilePath/"

# Research name -> wiki image file name (from the Research Portal table)
RESEARCHES = {
    # Academy level 1
    "Slinger": "Slinger.png",
    "Archer": "Archer.png",
    "City Guard": "Town guard.png",
    # Level 4
    "Hoplite": "Hoplite.png",
    "Diplomacy": "Diplomacy.png",
    "Meteorology": "Meteorology.png",
    # Level 7
    "Espionage": "Espionage.png",
    "Booty": "Booty.png",
    "Ceramics": "Pottery.png",
    # Level 10
    "Horseman": "Rider.png",
    "Architecture": "Architecture.png",
    "Trainer": "Instructor.png",
    # Level 13
    "Colony Ship": "Colonize ship.png",
    "Bireme": "Bireme.png",
    "Crane": "Building crane.png",
    "Shipwright": "Shipwright.png",
    # Level 16
    "Chariot": "Chariot.png",
    "Light Ship": "Attack ship.png",
    "Conscription": "Conscription.png",
    # Level 19
    "Fire Ship": "Demolition ship.png",
    "Catapult": "Catapult.png",
    "Cryptography": "Cryptography.png",
    "Democracy": "Democracy.png",
    # Level 22
    "Light Transport Ships": "Small transporter.png",
    "Plow": "Plow.png",
    "Bunks": "Berth.png",
    # Level 25
    "Trireme": "Trireme.png",
    "Phalanx": "Phalanx.png",
    "Breakthrough": "Breach.png",
    "Mathematics": "Mathematics.png",
    # Level 28
    "Ram": "Ram.png",
    "Cartography": "Cartography.png",
    "Conquest": "Take over.png",
    # Level 31
    "Stone Hail": "Stone Hail.png",
    "Temple Looting": "Temple Looting.png",
    "Divine Selection": "Divine Selection.png",
    # Level 34
    "Battle Experience": "Combat Experience.png",
    "Strong Wine": "Strong Wine.png",
    "Set Sail": "Set Sail.png",
}

TINTS = {
    "green": (40, 200, 70),
    "yellow": (255, 200, 0),
    "red": (225, 35, 35),
}

UA = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Safari/605.1.15"
RETRY_CODES = {429, 500, 502, 503, 504}
ATTEMPTS = 6


class Transient(Exception):
    """A failure worth retrying: rate limiting, a server hiccup or a dropped connection."""

    def __init__(self, reason: str, retry_after=None):
        super().__init__(reason)
        self.retry_after = retry_after


def slug(name: str) -> str:
    return name.lower().replace(" ", "_")


def retry_after_seconds(value):
    try:
        return max(1, min(120, int(value)))
    except (TypeError, ValueError):
        return None


def fetch_with_curl(url: str) -> bytes:
    """macOS system curl uses the keychain's certificates, so it works even when
    python.org Python has no CA bundle installed."""
    fd, tmp = tempfile.mkstemp(suffix=".png")
    os.close(fd)
    try:
        r = subprocess.run(
            ["curl", "-sSL", "-A", UA, "--max-time", "30", "-o", tmp, "-w", "%{http_code}", url],
            capture_output=True, text=True, check=False,
        )
        code_text = (r.stdout or "").strip()[-3:]
        code = int(code_text) if code_text.isdigit() else 0
        if code == 200:
            return Path(tmp).read_bytes()
        if code in RETRY_CODES:
            raise Transient(f"HTTP {code}")
        if code == 0:
            raise Transient((r.stderr or "network error").strip())
        raise RuntimeError(f"HTTP {code}")
    finally:
        os.unlink(tmp)


def fetch(url: str) -> bytes:
    try:
        req = urllib.request.Request(url, headers={"User-Agent": UA})
        with urllib.request.urlopen(req, timeout=30) as resp:
            return resp.read()
    except urllib.error.HTTPError as e:  # must come before URLError
        if e.code in RETRY_CODES:
            raise Transient(f"HTTP {e.code}", retry_after_seconds(e.headers.get("Retry-After")))
        raise RuntimeError(f"HTTP {e.code}")
    except urllib.error.URLError as e:
        if "CERTIFICATE_VERIFY_FAILED" in str(e):
            return fetch_with_curl(url)
        raise Transient(str(e.reason))
    except (TimeoutError, ConnectionError, OSError) as e:
        raise Transient(str(e))


def download(name: str, filename: str) -> Image.Image:
    url = WIKI + urllib.parse.quote(filename.replace(" ", "_"))
    for attempt in range(ATTEMPTS):
        try:
            return Image.open(io.BytesIO(fetch(url))).convert("RGBA")
        except Transient as t:
            if attempt == ATTEMPTS - 1:
                raise RuntimeError(f"still failing after {ATTEMPTS} tries ({t})")
            wait = t.retry_after or min(60, 5 * 2 ** attempt)  # 5, 10, 20, 40, 60 s
            print(f"  … {name}: {t}, trying again in {wait}s", flush=True)
            time.sleep(wait)
    raise RuntimeError("unreachable")


def tint(img: Image.Image, rgb: tuple, strength: float) -> Image.Image:
    """Blend the icon toward a solid colour, keeping its detail and transparency."""
    base = img.convert("RGBA")
    colour = Image.new("RGBA", base.size, rgb + (255,))
    mixed = Image.blend(base, colour, strength)
    mixed.putalpha(base.getchannel("A"))  # keep the original transparency
    return mixed


def default_out() -> Path:
    here = Path(__file__).resolve().parent
    return here if here.name == "grepolis_research_icons" else Path("grepolis_research_icons")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default=None, help="output folder (default: grepolis_research_icons)")
    ap.add_argument("--strength", type=float, default=0.45, help="tint strength 0..1 (default 0.45)")
    ap.add_argument("--force", action="store_true", help="download again even if the files exist")
    ap.add_argument("--delay", type=float, default=1.0, help="seconds between downloads (default 1)")
    args = ap.parse_args()

    out = Path(args.out).expanduser() if args.out else default_out()
    for sub in ["original", *TINTS]:
        (out / sub).mkdir(parents=True, exist_ok=True)

    done = skipped = 0
    failed = []
    for name, filename in RESEARCHES.items():
        s = slug(name)
        targets = [out / "original" / f"{s}.png"] + [out / c / f"{s}_{c}.png" for c in TINTS]
        if not args.force and all(p.exists() for p in targets):
            skipped += 1
            continue
        try:
            img = download(name, filename)
        except Exception as e:  # noqa: BLE001
            print(f"  ✗ {name} ({filename}): {e}", flush=True)
            failed.append(name)
            continue

        img.save(targets[0])
        for colour, rgb in TINTS.items():
            tint(img, rgb, args.strength).save(out / colour / f"{s}_{colour}.png")
        print(f"  ✓ {name}", flush=True)
        done += 1
        time.sleep(args.delay)  # be polite to the wiki

    print(f"\nDownloaded {done}, already had {skipped}, failed {len(failed)} → {out.resolve()}")
    if failed:
        print("Failed:", ", ".join(failed))
        print("The wiki may still be rate-limiting you. Wait a few minutes and run this again.")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
