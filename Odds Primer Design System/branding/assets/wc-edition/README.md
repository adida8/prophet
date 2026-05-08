# Odds Primer · World Cup 2026 edition · PNG asset set

The locked logo + the WC 2026 edition mark, applied as cover treatment across launch surfaces. Per the locked framing: **Odds Primer is the masthead; World Cup 2026 is the issue.** The logo is never modified — the edition lives in layout hierarchy.

Generated 2026-05-06.

## What's where

| Folder | What it's for |
|---|---|
| `lockups/` | Locked logo + edition strip beneath. Horizontal (2400×1200) for hero / press kit, stacked square (1500×1500) for square surfaces. Cream + navy variants of each. |
| `avatars/` | Square profile pictures with WC 2026 edition mark below the glyph. Use during the WC duration on Twitter/X, LinkedIn, Threads, and any other social account. 400 (most platforms) and 1024 (Twitter master). Cream + navy each. |
| `banners/` | Cover banners for high-visibility surfaces. Twitter cover (1500×500), LinkedIn banner (1584×396), email header (1200×300), Instagram-style social square (1200×1200). |

## File names

`wc-<asset>-<size>-<variant>.png`

- `wc-` prefix on every file — distinguishes from base-brand assets in the parent folder
- `<asset>`: lockup-primary, lockup-stacked, avatar, cover, social-square
- `<size>`: pixels (longest side)
- `<variant>`: `cream` (paper bg) / `navy` (ink bg, inverted)

## When to use which

| Surface | Recommended file |
|---|---|
| Twitter / X cover photo | `banners/wc-cover-1500x500-cream.png` |
| LinkedIn banner | `banners/wc-cover-linkedin-cream.png` |
| Email newsletter header | `banners/wc-cover-email-1200x300-cream.png` |
| Instagram / Threads post (square) | `banners/wc-social-square-1200-cream.png` |
| Twitter / X profile picture | `avatars/wc-avatar-400-cream.png` |
| Twitter / X profile picture, master | `avatars/wc-avatar-1024-cream.png` |
| Slide deck / press kit hero | `lockups/wc-lockup-primary-cream.png` |
| Dark surfaces / launch announcement | `lockups/wc-lockup-primary-navy.png` |
| Square one-pager / poster | `lockups/wc-lockup-stacked-cream.png` |

## Design rules baked in

- **"World Cup 2026"** is set in Inter Tight Bold (700) navy, slightly stronger tracking. The dominant edition mark.
- **"Edition 01"** and the descriptor are set in Inter Tight Medium (500) ink-soft / graphite. Quiet supporting copy.
- **Warm-paper strip** background `#F2EDE0` separates the edition mark from the locked logo on horizontal lockups.
- **Hairline rule** in `--rule` (`#D9D2BE`) sits between the locked logo and the edition copy.
- **Flame** appears only on the third bar of the glyph. Never on the edition copy. Never as a separator.
- **No FIFA imagery, no trophy, no host-country flag, no soccer ball, no badge.** Editorial restraint enforced.

## When to retire

These assets are **editioned, not skinned**. When the WC concludes, swap profiles and headers back to the base-brand assets in the parent `png/` folder. The edition mark becomes Edition 02 (whatever the next issue is) — same construction, different copy.
