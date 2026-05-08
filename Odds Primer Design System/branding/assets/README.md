# Odds Primer · PNG asset set

Generated 2026-05-06 from the locked v2 logo system. Source Serif 4 ExtraBold + 4-bar glyph (heights 22 · 38 · 65 · 30, flame on the third bar). Cream `#FAF7F0` / navy `#0E2240` / dustier flame `#D9461C`.

All files are PNG. Backgrounds are either cream, navy, or transparent. Where a transparent variant exists, prefer it for compositing onto custom surfaces.

## What's where

| Folder | What it's for |
|---|---|
| `lockups/` | Glyph + wordmark, primary horizontal lockup. Use for hero, masthead-as-image, press kit. Editorial variant adds the `22 · 38 · 65 · 30` mono colophon row. |
| `wordmark/` | "Odds Primer" set in Source Serif 4 800, no glyph. Use when the glyph appears separately on the same surface. |
| `glyph/` | The 4-bar glyph alone, square canvases, multiple sizes (32 / 64 / 128 / 256 / 512 / 1024). Three variants per size: cream, navy, transparent. |
| `glyph-trio/` | The 3-bar trio fallback for tiny rendering (16 / 32). Use anywhere the 4-bar mark would crush — favicons, OS-level icons, list bullets. |
| `favicon/` | Drop into your site's `public/` or root. 16 uses the trio; 32 / 48 / 192 / 512 use the full glyph. |
| `app-icon/` | iOS touch icon (180) and App Store / Play Store master (1024). |
| `avatar/` | Square profile pictures for social accounts. 400 (most platforms) and 1024 (Twitter / X master). Cream and navy variants of each. |
| `watermark/` | Low-opacity overlays for image annotations. `faint` is ~30% opacity (subtle), `medium` is ~60% (visible but not dominant). Lockup and glyph-only variants. Transparent background. |

## File naming convention

`<asset>-<size>-<variant>.png`

- `<asset>`: lockup, wordmark, glyph, glyph-trio, favicon, app-icon, avatar, watermark
- `<size>`: pixels (longest side)
- `<variant>`: `cream` (paper bg), `navy` (ink bg, inverted), `transparent` (no bg)

## When to use which

| Surface | Recommended file |
|---|---|
| Website favicon (root `favicon.ico` replacement) | `favicon/favicon-32.png` + `favicon/favicon-16.png` (link both) |
| Apple touch icon | `app-icon/app-icon-180.png` |
| PWA icon / Android home screen | `favicon/favicon-192.png`, `favicon/favicon-512.png` |
| Social profile (Twitter/X, LinkedIn, Threads) | `avatar/avatar-400-cream.png` (or `-navy` if the platform uses dark chrome) |
| Email signature / forum avatar | `avatar/avatar-400-cream.png` |
| Press kit / homepage hero / "About" page | `lockups/lockup-primary-cream.png` |
| Dark-bg surface (presentations, slides) | `lockups/lockup-primary-navy.png` |
| Editorial / colophon / about-the-numbers | `lockups/lockup-editorial-cream.png` |
| Slide deck / one-pager wordmark only | `wordmark/wordmark-cream.png` |
| Image annotation / chart corner | `watermark/watermark-lockup-faint.png` |
| Inline glyph on cream surface | `glyph/glyph-128-transparent.png` (sized down with CSS) |

## Notes on rendering

- **Source Serif 4 ExtraBold** is rasterized into the lockups and wordmark — the wordmark text is permanent pixels, not selectable. Good for surfaces that don't have web fonts (social cards, native app splash screens, email).
- For surfaces that do have web fonts, prefer the SVGs in `../glyph-bars.svg` and `../wordmark.svg` so the text stays selectable and scales infinitely.
- All cream/navy backgrounds are fully opaque. The transparent glyphs have no background and can be composited freely.
- Watermarks ship at 30% and 60% alpha. Drop opacity further in your image editor if you need fainter.

## Regenerating

The render script lives in your session's working directory (`/tmp/render_all_assets.py` during this build). To regenerate (e.g. after a logo geometry tweak), update the script's `draw_glyph` function or wordmark size constants and rerun.
