#!/usr/bin/env python3
"""Turn the white backgrounds (and white fills) of affiliation logos into transparency.

The site shows these logos on a light tile in light mode and on the bare card
in dark mode, so their white backgrounds must become transparent rather than
a white square. This is GIMP-style "colour to alpha" against white: each
pixel keeps the least alpha that reproduces it over white, so anti-aliased
edges stay smooth. Near-white JPEG noise is clipped to fully transparent.

Usage: python3 scripts/make_affiliation_alpha.py   (from the repo root)
"""
from PIL import Image

LOGOS = {  # source -> (output, width, height)
    "images/affiliations/usc.jpg": ("images/affiliations/usc.webp", 234, 240),
    "images/affiliations/lab126.jpg": ("images/affiliations/lab126.webp", 240, 240),
    "images/affiliations/mtk.jpg": ("images/affiliations/mtk.webp", 240, 152),
    "images/affiliations/uta.png": ("images/affiliations/uta.webp", 240, 240),
}
NOISE = 0.06  # alpha below this (JPEG speckle on the white) becomes 0


def white_to_alpha(im):
    # existing transparency counts as white, so it stays transparent
    flat = Image.new("RGBA", im.size, (255, 255, 255, 255))
    flat.alpha_composite(im.convert("RGBA"))
    im = flat.convert("RGB")
    out = Image.new("RGBA", im.size)
    src, dst = im.load(), out.load()
    for y in range(im.height):
        for x in range(im.width):
            r, g, b = src[x, y]
            a = max(255 - r, 255 - g, 255 - b) / 255
            a = 0.0 if a < NOISE else (a - NOISE) / (1 - NOISE)
            if a == 0:
                dst[x, y] = (0, 0, 0, 0)
                continue
            # un-blend from white: c = a*c' + (1-a)*255
            px = tuple(max(0, min(255, round((c - 255 * (1 - a)) / a))) for c in (r, g, b))
            dst[x, y] = px + (round(a * 255),)
    return out


for src, (dst, w, h) in LOGOS.items():
    logo = Image.open(src)
    logo = logo.resize((w, h), Image.LANCZOS)
    white_to_alpha(logo).save(dst, "WEBP", quality=90, alpha_quality=100, method=6)
    print("wrote", dst)
