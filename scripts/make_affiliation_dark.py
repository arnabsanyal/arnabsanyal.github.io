#!/usr/bin/env python3
"""Make the dark-mode variants of the two-colour affiliation logos.

Each of these logos is one brand colour on white (or white on the brand
colour). For dark mode the two colours swap: the brand colour becomes the
background and the white becomes the artwork, or the reverse for logos that
are already a filled square (AMD, Qualcomm).

Every pixel is treated as a mix of the brand colour and white. Its share of
brand colour, t, comes from how far it is from white relative to the brand
colour itself, so anti-aliased edges keep their in-between shades. The
swapped pixel is t * white + (1 - t) * brand.

Logos that are not already a filled square are first padded to a square on
white, so in dark mode they all become rounded brand-colour squares.

Usage: python3 scripts/make_affiliation_dark.py   (from the repo root)
"""
from statistics import median

from PIL import Image

SIZE = 256      # output is SIZE x SIZE
MARGIN = 0.12   # padding around the artwork for logos that get padded

LOGOS = {  # source -> (output, pad to square with a margin?)
    "images/affiliations/amd.png": ("images/affiliations/amd-dark.webp", False),
    "images/affiliations/qualcomm.jpeg": ("images/affiliations/qualcomm-dark.webp", False),
    "images/affiliations/mtk.jpg": ("images/affiliations/mtk-dark.webp", True),
    "images/affiliations/uta.png": ("images/affiliations/uta-dark.webp", True),
    "images/affiliations/usc.jpg": ("images/affiliations/usc-dark.webp", True),
    "images/affiliations/iitkgp.png": ("images/affiliations/iitkgp-dark.webp", True),
}


def on_white(im):
    """The logo as it looks on the light-mode tile."""
    flat = Image.new("RGBA", im.size, (255, 255, 255, 255))
    flat.alpha_composite(im.convert("RGBA"))
    return flat.convert("RGB")


def pad_square(im):
    inner = round(SIZE * (1 - 2 * MARGIN))
    im = im.copy()
    im.thumbnail((inner, inner), Image.LANCZOS)
    sq = Image.new("RGB", (SIZE, SIZE), (255, 255, 255))
    sq.paste(im, ((SIZE - im.width) // 2, (SIZE - im.height) // 2))
    return sq


def depth(p):
    """How far a pixel is from white, 0 (white) to 1 (a fully saturated or black pixel)."""
    return (255 - min(p)) / 255


def swap(im):
    px = list(im.getdata())
    d = [depth(p) for p in px]
    cut = 0.5 * max(d)
    strong = sorted(x for x in d if x > cut)
    ref = strong[int(0.7 * (len(strong) - 1))]  # a typical fully-brand pixel
    brand = tuple(round(median(p[i] for p, x in zip(px, d) if x >= ref)) for i in range(3))
    out = []
    for x in d:
        t = min(1.0, x / ref)
        out.append(tuple(round(t * 255 + (1 - t) * c) for c in brand))
    res = Image.new("RGB", im.size)
    res.putdata(out)
    return res, brand


for src, (dst, pad) in LOGOS.items():
    logo = on_white(Image.open(src))
    logo = pad_square(logo) if pad else logo.resize((SIZE, SIZE), Image.LANCZOS)
    dark, brand = swap(logo)
    dark.save(dst, "WEBP", quality=90, method=6)
    print("wrote", dst, "brand", "#%02x%02x%02x" % brand)
