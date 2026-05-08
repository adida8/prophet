"""Extract dominant palettes from rendered screenshots.

Strategy:
- crop top 70% of the image to avoid bottom cookie banners
- median-cut to 24 colors
- sort by population
- dedup near-duplicates by simple Lab-ish distance in RGB space
- return top 5
"""
import os, json
from pathlib import Path
from PIL import Image
from collections import Counter

ROOT = Path("/sessions/wonderful-sleepy-carson/mnt/prophet/branding/research")
SHOTS = ROOT / "screenshots"


def to_hex(rgb):
    return "#{:02X}{:02X}{:02X}".format(*rgb)


def color_dist(a, b):
    # weighted RGB approximation of perceptual distance (Colour Mine)
    rmean = (a[0]+b[0])/2
    dr, dg, db = a[0]-b[0], a[1]-b[1], a[2]-b[2]
    return ((2 + rmean/256)*dr*dr + 4*dg*dg + (2 + (255-rmean)/256)*db*db)**0.5


def is_pure_grey(rgb, tol=8):
    r,g,b = rgb
    return abs(r-g) < tol and abs(g-b) < tol and abs(r-b) < tol


def luminance(rgb):
    return 0.2126*rgb[0] + 0.7152*rgb[1] + 0.0722*rgb[2]


def extract(path):
    img = Image.open(path).convert("RGB")
    w, h = img.size
    # Crop top 70% — usually clear of cookie banners
    img = img.crop((0, 0, w, int(h*0.7)))
    # Resize for speed
    img.thumbnail((640, 400))
    # Median-cut quantize
    pal_img = img.quantize(colors=24, method=Image.Quantize.MEDIANCUT)
    palette = pal_img.getpalette()  # flat [r,g,b,r,g,b,...]
    counts = Counter(pal_img.getdata())
    items = []
    for idx, count in counts.most_common(24):
        rgb = (palette[idx*3], palette[idx*3+1], palette[idx*3+2])
        items.append((rgb, count))
    total = sum(c for _, c in items)

    # Step 1: dedup near-duplicates (greedy — keep highest count, merge close ones into it)
    deduped = []
    for rgb, count in items:
        merged = False
        for i, (rgb0, c0) in enumerate(deduped):
            if color_dist(rgb, rgb0) < 35:
                deduped[i] = (rgb0, c0 + count)
                merged = True
                break
        if not merged:
            deduped.append((rgb, count))

    # Score = log-population * brand-likely weight (penalize pure grey/white slightly)
    import math
    scored = []
    for rgb, count in deduped:
        share = count / total
        weight = 1.0
        lum = luminance(rgb)
        if is_pure_grey(rgb) and (lum > 235 or lum < 18):
            weight *= 0.45  # de-emphasize pure white/black bg
        elif is_pure_grey(rgb):
            weight *= 0.7
        scored.append((rgb, share, share*weight))

    scored.sort(key=lambda x: -x[2])
    # Keep top 5 + ensure at least one bg (highest-luminance) and brightest hue color
    top5 = [s for s in scored[:5]]
    return [{"hex": to_hex(rgb), "rgb": list(rgb), "share": round(share, 3)}
            for rgb, share, _ in top5]


def main():
    out = {}
    for f in sorted(os.listdir(SHOTS)):
        if not f.endswith('.png'):
            continue
        name = f.replace('.png', '')
        out[name] = extract(SHOTS / f)
    print(json.dumps(out, indent=2))


if __name__ == "__main__":
    main()
