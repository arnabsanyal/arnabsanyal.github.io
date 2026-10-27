#!/usr/bin/env python3
"""
Script to generate the site logo and favicon SVGs from exact geometry

The mark is an equilateral "A": every band (legs, crossbar, chevron, feet) is
T units thick and every gap between parts is G units wide, so the logo stays
symmetric and crisp at any size. Edit PALETTES and re-run to recolour it.

Usage: python3 scripts/make_logo.py
"""

import math
import os

# Geometry (apex at the origin, y pointing down)
S3 = math.sqrt(3)
H = 300.0           # height of the outer triangle
T = 27.0            # band thickness
G = 13.5            # gap between parts
YC = 206.0          # top of the crossbar (bottom of the counter)
YB = YC + T         # bottom of the crossbar

# (main, accent) colours for each file
PALETTES = {
    "logo.svg": ("#f7f3f3", "#ff5c66"),       # for dark backgrounds
    "logo-dark.svg": ("#0c0404", "#bd0518"),  # for light backgrounds
}
FAVICON = {"file": "favicon.svg", "tile": "#2b2c2f", "colors": PALETTES["logo.svg"]}
TITLE = "Arnab Sanyal"
IMAGES_DIR = "images"


def half_width(y, apex):
    """Half-width at height y of a 60-degree triangle whose apex is at y=apex."""
    return (y - apex) / S3


def fmt(v):
    return f"{v:.2f}".rstrip("0").rstrip(".")


def rounded_polygon(points):
    """
    Build a closed SVG path from (x, y, radius) vertices, replacing each
    corner with a circular fillet of the given radius.
    """
    n = len(points)
    corners = []
    for i in range(n):
        px, py, _ = points[i - 1]
        vx, vy, r = points[i]
        nx, ny, _ = points[(i + 1) % n]
        a, b = (px - vx, py - vy), (nx - vx, ny - vy)
        la, lb = math.hypot(*a), math.hypot(*b)
        ua, ub = (a[0] / la, a[1] / la), (b[0] / lb, b[1] / lb)
        angle = math.acos(max(-1.0, min(1.0, ua[0] * ub[0] + ua[1] * ub[1])))
        d = r / math.tan(angle / 2) if r else 0
        assert d <= min(la, lb) / 2 + 1e-6, f"radius {r} too large at {points[i]}"
        start = (vx + ua[0] * d, vy + ua[1] * d)
        end = (vx + ub[0] * d, vy + ub[1] * d)
        sweep = 0 if ua[0] * ub[1] - ua[1] * ub[0] > 0 else 1
        corners.append((start, end, r, sweep))

    path = f"M{fmt(corners[0][1][0])} {fmt(corners[0][1][1])}"
    for start, end, r, sweep in corners[1:] + corners[:1]:
        path += f"L{fmt(start[0])} {fmt(start[1])}"
        if r:
            path += f"A{fmt(r)} {fmt(r)} 0 0 {sweep} {fmt(end[0])} {fmt(end[1])}"
    return path + "Z"


def shapes(dx, dy):
    """Return (main_path, accent_path) translated by (dx, dy)."""
    a_in = 2 * T                        # apex of the counter
    outer = [(0, 0, 6), (half_width(H, 0), H, 3), (half_width(H, a_in), H, 3),
             (half_width(YB, a_in), YB, 34), (-half_width(YB, a_in), YB, 34),
             (-half_width(H, a_in), H, 3), (-half_width(H, 0), H, 3)]
    counter = [(0, a_in, 6), (half_width(YC, a_in), YC, 22),
               (-half_width(YC, a_in), YC, 22)]

    # Chevron sits G inside the counter and is T thick
    c_out, c_in, c_bot = a_in + 2 * G, a_in + 2 * G + 2 * T, YC - G
    chevron = [(0, c_out, 6), (half_width(c_bot, c_out), c_bot, 4),
               (half_width(c_bot, c_in), c_bot, 7), (0, c_in, 4),
               (-half_width(c_bot, c_in), c_bot, 7), (-half_width(c_bot, c_out), c_bot, 4)]

    # Feet sit G inside the legs and below the crossbar, and are T thick
    f_out, f_in, f_top = c_out, c_in, YB + G
    foot_left = [(-half_width(f_top, f_out), f_top, 20.5), (-half_width(f_top, f_in), f_top, 2.5),
                 (-half_width(H, f_in), H, 8), (-half_width(H, f_out), H, 2.5)]
    foot_right = [(-x, y, r) for x, y, r in reversed(foot_left)]

    move = lambda pts: [(x + dx, y + dy, r) for x, y, r in pts]
    main = rounded_polygon(move(outer)) + rounded_polygon(move(counter))
    accent = "".join(rounded_polygon(move(p)) for p in (chevron, foot_left, foot_right))
    return main, accent


def logo_svg(main_color, accent_color, pad=9):
    width, height = 2 * half_width(H, 0) + 2 * pad, H + 2 * pad
    main, accent = shapes(width / 2, pad)
    return (f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {fmt(width)} {fmt(height)}" role="img">'
            f'<title>{TITLE}</title>'
            f'<path fill="{main_color}" fill-rule="evenodd" d="{main}"/>'
            f'<path fill="{accent_color}" d="{accent}"/></svg>\n')


def favicon_svg(tile_color, main_color, accent_color, side=512):
    # The mark is scaled to ~78% of the tile width; the optical centre of a
    # triangle sits below its bounding-box centre, so nudge it down
    scale = 0.78 * side / (2 * half_width(H, 0))
    dx, dy = side / 2 / scale, (side / scale - H) / 2 + 8
    main, accent = shapes(dx, dy)
    return (f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {side} {side}" role="img">'
            f'<title>{TITLE}</title>'
            f'<rect width="{side}" height="{side}" rx="{side * 0.22:g}" fill="{tile_color}"/>'
            f'<g transform="scale({scale:.5f})">'
            f'<path fill="{main_color}" fill-rule="evenodd" d="{main}"/>'
            f'<path fill="{accent_color}" d="{accent}"/></g></svg>\n')


def main():
    """Main function"""
    script_dir = os.path.dirname(os.path.abspath(__file__))
    os.chdir(os.path.dirname(script_dir))

    for name, (main_color, accent_color) in PALETTES.items():
        path = os.path.join(IMAGES_DIR, name)
        with open(path, "w") as f:
            f.write(logo_svg(main_color, accent_color))
        print(f"✓ Wrote {path}")

    path = os.path.join(IMAGES_DIR, FAVICON["file"])
    with open(path, "w") as f:
        f.write(favicon_svg(FAVICON["tile"], *FAVICON["colors"]))
    print(f"✓ Wrote {path}")


if __name__ == "__main__":
    main()
