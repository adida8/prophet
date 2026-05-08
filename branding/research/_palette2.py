"""Better palette extraction.

For each screenshot:
- Sample 3 regions: top 120px (header strip), middle band (120-560px), full image
- For each region, median-cut to 16, then re-rank by saturation-weighted population
- Merge across regions, dedup, return top 5

Saturation weighting: a color with high chroma tends to be a brand accent. We score:
    score = pop * (0.6 + 0.4*S) * (1 if not pure_grey else 0.5)
Plus we always reserve one "background" slot — the highest-luminance non-pure-grey region color.
"""
import os, json, math
from pathlib import Path
from PIL import Image
from collections import Counter

ROOT = Path("/sessions/wonderful-sleepy-carson/mnt/prophet/branding/research")
SHOTS = ROOT / "screenshots"


def to_hex(rgb):
    return "#{:02X}{:02X}{:02X}".format(*rgb)


def rgb_to_hsv(rgb):
    r,g,b = [x/255 for x in rgb]
    mx, mn = max(r,g,b), min(r,g,b)
    v = mx
    s = 0 if mx == 0 else (mx-mn)/mx
    if mx == mn:
        h = 0
    elif mx == r:
        h = (60*((g-b)/(mx-mn)) + 360) % 360
    elif mx == g:
        h = 60*((b-r)/(mx-mn)) + 120
    else:
        h = 60*((r-g)/(mx-mn)) + 240
    return h, s, v


def color_dist(a, b):
    rmean = (a[0]+b[0])/2
    dr, dg, db = a[0]-b[0], a[1]-b[1], a[2]-b[2]
    return ((2 + rmean/256)*dr*dr + 4*dg*dg + (2 + (255-rmean)/256)*db*db)**0.5


def is_grey(rgb, tol=10):
    return max(rgb)-min(rgb) < tol


def luminance(rgb):
    return 0.2126*rgb[0] + 0.7152*rgb[1] + 0.0722*rgb[2]


def quantize_region(img, n=16):
    pal_img = img.quantize(colors=n, method=Image.Quantize.MEDIANCUT)
    palette = pal_img.getpalette()
    counts = Counter(pal_img.getdata())
    out = []
    for idx, count in counts.most_common(n):
        rgb = (palette[idx*3], palette[idx*3+1], palette[idx*3+2])
        out.append((rgb, count))
    return out


def extract(path):
    img = Image.open(path).convert("RGB")
    w, h = img.size
    img.thumbnail((1024, 640))
    w, h = img.size
    header = img.crop((0, 0, w, min(int(h*0.18), 130)))
    middle = img.crop((0, int(h*0.18), w, int(h*0.62)))
    full   = img

    bag = {}  # rgb -> total weighted score
    sources = {}
    for region, weight in [(header, 1.4), (middle, 1.1), (full, 0.9)]:
        items = quantize_region(region, 16)
        total = sum(c for _, c in items) or 1
        for rgb, count in items:
            share = count / total
            h_, s_, v_ = rgb_to_hsv(rgb)
            sat_boost = 0.5 + 0.9 * s_
            grey_pen = 0.55 if is_grey(rgb) else 1.0
            # de-emphasize pure black/white slightly so we get brand accents alongside bg
            lum = luminance(rgb)
            extreme_pen = 0.7 if (lum > 245 or lum < 8) else 1.0
            score = share * sat_boost * grey_pen * extreme_pen * weight
            bag[rgb] = bag.get(rgb, 0) + score
            sources.setdefault(rgb, 0)
            sources[rgb] += share * weight

    # dedup near-duplicates (keep one with highest score)
    sorted_colors = sorted(bag.items(), key=lambda x: -x[1])
    deduped = []
    for rgb, score in sorted_colors:
        merged = False
        for i, (rgb0, s0) in enumerate(deduped):
            if color_dist(rgb, rgb0) < 30:
                deduped[i] = (rgb0, s0 + score)
                merged = True
                break
        if not merged:
            deduped.append((rgb, score))

    deduped.sort(key=lambda x: -x[1])

    # Always include a background color: highest-luminance color where lum>200 or lowest where lum<40,
    # if not already in top 5
    top5 = [rgb for rgb, _ in deduped[:5]]
    # ensure a true bg is present
    bg_candidates = [rgb for rgb, _ in deduped if luminance(rgb) > 220]
    dark_candidates = [rgb for rgb, _ in deduped if luminance(rgb) < 40]
    have_light = any(luminance(c) > 220 for c in top5)
    have_dark = any(luminance(c) < 40 for c in top5)

    return [{"hex": to_hex(rgb), "rgb": list(rgb),
             "share": round(sources.get(rgb, 0)/3, 3),
             "lum": round(luminance(rgb), 1),
             "sat": round(rgb_to_hsv(rgb)[1], 2)}
            for rgb in top5]


def main():
    out = {}
    for f in sorted(os.listdir(SHOTS)):
        if not f.endswith('.png'):
            continue
        name = f.replace('.png', '')
        out[name] = extract(SHOTS / f)
    with open(ROOT / "palettes.json", "w") as fp:
        json.dump(out, fp, indent=2)
    print(json.dumps(out, indent=2))


if __name__ == "__main__":
    main()
