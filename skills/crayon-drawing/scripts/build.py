#!/usr/bin/env python3
"""Build a crayon scene into one self-contained HTML page.

Usage: build.py SCENE [OUT]

SCENE is an HTML fragment: the panels, then a <script> that calls crayon.draw.
OUT defaults to SCENE with ".scene.html" replaced by ".html". Prints OUT.
"""

import sys
from pathlib import Path

ASSETS = Path(__file__).resolve().parent.parent / "assets"
FONTS = "https://fonts.googleapis.com/css2?family=Gaegu:wght@700&family=Patrick+Hand&display=swap"


def main(args):
    if len(args) not in (1, 2):
        sys.exit(__doc__)
    scene = Path(args[0])
    if len(args) == 2:
        out = Path(args[1])
    elif scene.name.endswith(".scene.html"):
        out = scene.with_name(scene.name.removesuffix(".scene.html") + ".html")
    else:
        sys.exit("Name the scene NAME.scene.html, or pass the output path.")
    body = scene.read_text()
    lowered = body.lower()
    if "<html" in lowered or "<head" in lowered or "<body" in lowered:
        sys.exit(f"{scene} must be a fragment: panels and a <script>, without <html>, <head> or <body>.")
    if "crayon.draw(" not in body:
        sys.exit(f"{scene} never calls crayon.draw({{ ... }}), so nothing would be drawn.")
    css = (ASSETS / "crayon.css").read_text()
    js = (ASSETS / "crayon.js").read_text()
    out.write_text(
        f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<link rel="stylesheet" href="{FONTS}">
<style>
{css}</style>
<script>
{js}</script>
</head>
<body>
{body.rstrip()}
</body>
</html>
"""
    )
    print(out)


if __name__ == "__main__":
    main(sys.argv[1:])
