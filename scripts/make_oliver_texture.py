#!/usr/bin/env python3
"""
Script to repaint the Live2D "hijiki" cat texture as Oliver

Oliver is a grey shorthair tabby: blue-grey fur with darker mackerel
stripes, banded legs and tail, a tabby "M" on the forehead, a white muzzle
and chin, a cream/buff belly, pale toes, a pink nose and green-gold eyes.

The model's geometry and motions are untouched; only the texture atlas is
repainted, part by part. Each part is a rectangle on the 2048x2048 atlas
(found by rendering the model with every part in a different colour).

Usage: python3 scripts/make_oliver_texture.py   (needs numpy and Pillow with WebP)
"""

import json
import os

import numpy as np
from PIL import Image, ImageFilter

SRC_TEXTURE = "live2dw/assets/moc/hijiki.2048/texture_00.png"
SRC_MODEL = "live2dw/assets/hijiki.model.json"
OUT_TEXTURE = "live2dw/assets/moc/oliver.2048/texture_00.webp"
OUT_MODEL = "live2dw/assets/oliver.model.json"
SEED = 7

# Atlas parts as (x0, y0, x1, y1) in texture pixels
PARTS = {
    "head":        (1428, 28, 2003, 540),
    "body":        (529, 29, 1382, 1067),
    "chest":       (1384, 606, 2029, 1439),
    "upper_leg_l": (12, 37, 286, 540),
    "upper_leg_r": (317, 33, 600, 542),
    "lower_leg_l": (23, 578, 240, 1054),
    "lower_leg_r": (268, 578, 488, 1055),
    "tail":        (418, 1095, 1391, 1375),
    "front_paws":  (30, 1093, 424, 1267),
    "back_paws":   (24, 1315, 398, 1451),
    "muzzle":      (956, 1372, 1211, 1478),
    "chin":        (967, 1894, 1201, 2031),
    "nose":        (1041, 1297, 1124, 1364),
    "inner_ears":  (1248, 1431, 1586, 1691),
    "ear_tufts":   (1648, 1708, 2022, 1961),
    "whiskers_l":  (31, 1492, 450, 1929),
}

# Oliver's palette (sRGB 0-255)
FUR_DARK = np.array([84, 79, 80])
FUR_LIGHT = np.array([148, 140, 137])
STRIPE = np.array([66, 63, 66])
CREAM = np.array([196, 174, 152])
WHITE = np.array([232, 228, 222])
PAW = np.array([186, 180, 176])
NOSE = np.array([186, 122, 116])
INNER_EAR = np.array([172, 142, 138])
WHISKER = np.array([226, 224, 220])


def smooth_noise(shape, cells, rng):
    """Value noise: a coarse random grid upsampled with bicubic filtering."""
    h, w = shape
    grid = rng.random((max(2, h // cells), max(2, w // cells))).astype(np.float32)
    img = Image.fromarray((grid * 255).astype(np.uint8)).resize((w, h), Image.BICUBIC)
    return np.asarray(img, dtype=np.float32) / 255.0


def fbm(shape, rng):
    return (0.6 * smooth_noise(shape, 160, rng) + 0.3 * smooth_noise(shape, 48, rng)
            + 0.1 * smooth_noise(shape, 12, rng))


def smoothstep(e0, e1, x):
    t = np.clip((x - e0) / (e1 - e0), 0.0, 1.0)
    return t * t * (3 - 2 * t)


def part_uv(name):
    """Normalised (u, v) grids over a part's rectangle, plus its slices."""
    x0, y0, x1, y1 = PARTS[name]
    v, u = np.mgrid[0:y1 - y0, 0:x1 - x0].astype(np.float32)
    return (slice(y0, y1), slice(x0, x1)), u / (x1 - x0), v / (y1 - y0)


def stripes(coord, period, warp, width=0.3):
    """Soft periodic bands along `coord`; `warp` bends them so they look painted."""
    phase = (coord / period + warp) % 1.0
    return smoothstep(width, width * 0.5, np.abs(phase - 0.5) * 2)


def main():
    """Main function"""
    script_dir = os.path.dirname(os.path.abspath(__file__))
    os.chdir(os.path.dirname(script_dir))
    rng = np.random.default_rng(SEED)

    src = np.asarray(Image.open(SRC_TEXTURE).convert("RGBA"), dtype=np.float32)
    rgb, alpha = src[..., :3], src[..., 3]
    lum = rgb.mean(-1) / 255.0
    sat = (rgb.max(-1) - rgb.min(-1)) / 255.0
    out = rgb.copy()
    noise = fbm(lum.shape, rng)

    # 1. All dark, unsaturated fur becomes blue-grey, keeping the original shading
    fur = (alpha > 0) & (sat < 0.08) & (lum < 0.3)
    shade = smoothstep(0.08, 0.26, lum + (noise - 0.5) * 0.05)[..., None]
    out[fur] = (FUR_DARK + (FUR_LIGHT - FUR_DARK) * shade)[fur]
    stripe_mask = np.zeros(lum.shape, np.float32)

    # 2. Tabby markings, part by part
    sl, u, v = part_uv("head")
    n = noise[sl]
    m_mark = stripes(u - 0.5 + (u - 0.5) * v * 0.6, 0.075, n * 0.25, 0.32)
    m_mark *= smoothstep(0.30, 0.36, u) * smoothstep(0.70, 0.64, u) * smoothstep(0.44, 0.20, v)
    cheeks = stripes(v + (np.abs(u - 0.5) * 0.25), 0.07, n * 0.2, 0.3)
    cheeks *= smoothstep(0.42, 0.50, v) * smoothstep(0.72, 0.64, v) * smoothstep(0.24, 0.30, np.abs(u - 0.5))
    crown = stripes(u + n * 0.08, 0.11, 0, 0.25) * smoothstep(0.12, 0.0, v)
    stripe_mask[sl] = np.maximum.reduce([m_mark * 0.7, cheeks * 0.45, crown * 0.4])
    # lighter lower face around the muzzle
    face_light = smoothstep(0.62, 0.85, v) * smoothstep(0.24, 0.10, np.abs(u - 0.5))
    out[sl] += (WHITE - out[sl]) * (face_light * 0.55 * fur[sl])[..., None]

    sl, u, v = part_uv("body")
    n = noise[sl]
    ribs = stripes(u + np.sin(v * 5.0) * 0.04, 0.12, n * 0.6, 0.42)
    spine = smoothstep(0.18, 0.0, v) * 0.45
    stripe_mask[sl] = np.maximum(ribs * smoothstep(0.05, 0.2, v) * 0.38, spine)

    for leg in ("upper_leg_l", "upper_leg_r", "lower_leg_l", "lower_leg_r"):
        sl, u, v = part_uv(leg)
        n = noise[sl]
        bands = stripes(v + np.sin(u * 3.0) * 0.04, 0.16, n * 0.4, 0.4)
        fade = 0.5 if leg.startswith("upper") else 0.42
        stripe_mask[sl] = np.maximum(stripe_mask[sl], bands * fade)

    sl, u, v = part_uv("tail")
    n = noise[sl]
    rings = stripes(u, 0.09, n * 0.25, 0.42)
    tip = smoothstep(0.10, 0.03, u)
    stripe_mask[sl] = np.maximum(stripe_mask[sl], np.maximum(rings * 0.6, tip * 0.85))

    sl, u, v = part_uv("chest")
    n = noise[sl]
    necklace = stripes(v, 0.09, n * 0.2, 0.25) * smoothstep(0.2, 0.28, v) * smoothstep(0.5, 0.42, v)
    stripe_mask[sl] = np.maximum(stripe_mask[sl], necklace * 0.22)

    # soften the markings so they read as fur, not paint
    stripe_mask = np.asarray(Image.fromarray((stripe_mask * 255).astype(np.uint8)).filter(ImageFilter.GaussianBlur(4)), np.float32) / 255
    m = (stripe_mask * fur)[..., None]
    out += (STRIPE - out) * m

    # 3. Cream belly, white muzzle and chin, pale toes
    sl, u, v = part_uv("chest")
    belly = smoothstep(0.55, 0.92, v + (noise[sl] - 0.5) * 0.12) * smoothstep(0.5, 0.2, np.abs(u - 0.5))
    shade_c = (0.75 + 0.25 * smoothstep(0.08, 0.26, lum[sl]))[..., None]
    out[sl] += ((CREAM * shade_c) - out[sl]) * (belly * 0.6 * fur[sl])[..., None]

    for name, colour, amount in (("muzzle", WHITE, 0.9), ("chin", WHITE, 0.95),
                                 ("front_paws", PAW, 0.8), ("back_paws", PAW, 0.7)):
        sl, u, v = part_uv(name)
        k = (0.8 + 0.2 * smoothstep(0.08, 0.26, lum[sl]))[..., None]
        mask = (fur[sl] * amount)[..., None]
        if name == "muzzle":
            # keep the whisker dots visible
            mask = mask * (lum[sl] > 0.12)[..., None]
        out[sl] += (colour * k - out[sl]) * mask

    # 4. Pink nose and inner ears, light ear tufts and whiskers
    for name, colour in (("nose", NOSE), ("inner_ears", INNER_EAR)):
        sl, _, _ = part_uv(name)
        k = (0.7 + 0.6 * smoothstep(0.05, 0.45, lum[sl]))[..., None]
        out[sl] = np.where((alpha[sl] > 0)[..., None], colour * k, out[sl])

    sl, _, _ = part_uv("ear_tufts")
    out[sl] += (WHISKER - out[sl]) * (0.55 * (alpha[sl] > 0))[..., None]
    sl, _, _ = part_uv("whiskers_l")
    out[sl] = np.where((alpha[sl] > 0)[..., None] & (sat[sl] < 0.1)[..., None], WHISKER, out[sl])

    # 5. Green-gold eyes: shift the yellow irises towards chartreuse
    eyes = (alpha > 0) & (sat > 0.25) & (rgb[..., 0] > rgb[..., 2] + 60) & (rgb[..., 1] > rgb[..., 2] + 40)
    out[eyes] = out[eyes] * np.array([0.88, 0.93, 0.55])

    result = np.dstack([np.clip(out, 0, 255), alpha]).astype(np.uint8)
    os.makedirs(os.path.dirname(OUT_TEXTURE), exist_ok=True)
    # lossy WebP keeps the file near the original PNG's size without the banding of a 256-colour palette
    Image.fromarray(result, "RGBA").save(OUT_TEXTURE, quality=90, alpha_quality=100, method=6)
    print(f"✓ Wrote {OUT_TEXTURE}")

    with open(SRC_MODEL) as f:
        model = json.load(f)
    model["name"] = "oliver"
    model["textures"] = [os.path.relpath(OUT_TEXTURE, os.path.dirname(OUT_MODEL))]
    with open(OUT_MODEL, "w") as f:
        json.dump(model, f)
    print(f"✓ Wrote {OUT_MODEL}")


if __name__ == "__main__":
    main()
