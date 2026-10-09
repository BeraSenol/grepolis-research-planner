#!/usr/bin/env python3
"""Build index.html from src/app.html and the in-game research sprite.

src/research-sprite.png holds 100 icons of 50x50 in one row. Every research has a
black-and-white version at an even index, followed by its colour version. The
planner uses the black-and-white versions, tinted 45% toward green, yellow and red,
and embeds them in the page so it works as a single file.

Usage:
    pip3 install pillow
    python3 build.py                     # writes index.html, a complete web page
    python3 build.py --fragment out.html # writes only the page content, for embedding
"""
import argparse
import base64
import io
import json
import re
from pathlib import Path

from PIL import Image

ROOT = Path(__file__).resolve().parent
TEMPLATE = ROOT / "src" / "app.html"
SPRITE_FILE = ROOT / "src" / "research-sprite.png"

# research id -> index of its black-and-white icon in the sprite
SPRITE = {
    "slinger": 78, "archer": 0, "city_guard": 94,
    "hoplite": 52, "meteorology": 58,
    "espionage": 48, "booty": 14, "ceramics": 66,
    "horseman": 70, "architecture": 2, "trainer": 54,
    "bireme": 10, "crane": 18, "shipwright": 74, "colony_ship": 30,
    "chariot": 26, "light_ship": 4, "conscription": 34,
    "fire_ship": 42, "catapult": 22, "cryptography": 36, "democracy": 40,
    "light_transport_ships": 80, "plow": 64, "bunks": 6,
    "trireme": 96, "phalanx": 60, "breakthrough": 16, "mathematics": 56,
    "ram": 68, "cartography": 20, "revolt": 88, "conquest": 90,
    "stone_hail": 76, "temple_looting": 92, "divine_selection": 46,
    "battle_experience": 32, "strong_wine": 84, "set_sail": 72,
}
TINTS = {"g": (40, 200, 70), "y": (255, 200, 0), "r": (225, 35, 35)}
STRENGTH = 0.45

PAGE = """<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1,viewport-fit=cover">
<meta name="description" content="Plan Grepolis academy researches in green, yellow and red, and download one image for your alliance.">
{title}
<style>:root{{color-scheme:light;padding-top:env(safe-area-inset-top,0px);padding-bottom:env(safe-area-inset-bottom,0px)}}body{{margin:0}}img{{max-width:100%}}[hidden]{{display:none!important}}</style>
</head>
<body>
{body}
</body>
</html>
"""


def tint(img, rgb, strength=STRENGTH):
    """Blend the icon toward a solid colour, keeping its detail and transparency."""
    base = img.convert("RGBA")
    colour = Image.new("RGBA", base.size, rgb + (255,))
    mixed = Image.blend(base, colour, strength)
    mixed.putalpha(base.getchannel("A"))
    return mixed


def data_uri(img):
    buf = io.BytesIO()
    img.save(buf, "PNG", optimize=True)
    return "data:image/png;base64," + base64.b64encode(buf.getvalue()).decode()


def tinted_icons():
    sprite = Image.open(SPRITE_FILE).convert("RGBA")
    if sprite.size != (5000, 50):
        raise SystemExit(f"{SPRITE_FILE.name} is {sprite.size[0]}x{sprite.size[1]}, expected 5000x50")
    icons = {}
    for rid, i in SPRITE.items():
        base = sprite.crop((i * 50, 0, i * 50 + 50, 50))
        icons[rid] = {k: data_uri(tint(base, rgb)) for k, rgb in TINTS.items()}
    return icons


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--fragment", metavar="FILE", help="write only the page content (no <html>/<head>) to FILE")
    args = ap.parse_args()

    template = TEMPLATE.read_text(encoding="utf-8")
    if "__ICONS__" not in template:
        raise SystemExit("src/app.html has no __ICONS__ placeholder")
    page = template.replace("__ICONS__", json.dumps(tinted_icons()))

    if args.fragment:
        out = Path(args.fragment)
        out.write_text(page, encoding="utf-8")
    else:
        m = re.search(r"<title>.*?</title>\s*", page, re.S)
        title = m.group(0).strip() if m else "<title>Grepolis Research Planner</title>"
        body = page.replace(m.group(0), "", 1) if m else page
        out = ROOT / "index.html"
        out.write_text(PAGE.format(title=title, body=body.strip()), encoding="utf-8")
    print(f"Wrote {out.name} ({round(out.stat().st_size / 1024)} KB, {len(SPRITE)} researches)")


if __name__ == "__main__":
    main()
