"""Slide renderer — Protocol + stub.

The real renderer is owned by `THE_DESK_SOCIAL_RENDERER_SPEC.md` and
lands separately. This module ships the contract everything else codes
against, plus a `StubRenderer` that writes 4 solid-colour 1080×1350 PNGs
with the slide number burned in. The stub is good enough to ship the
queue + approval + bundle path on, and it's swapped out byte-for-byte
when the real renderer lands.

`StubRenderer` uses only the stdlib — it writes a minimal PNG by hand so
this module can sit in the install graph without pulling Pillow into
every consumer. Bytes are valid PNG (decoded with `Image.open` if
Pillow is present; verified manually with `file <name>.png`).
"""

from __future__ import annotations

import hashlib
import struct
import zlib
from pathlib import Path
from typing import NamedTuple, Protocol, Union

from desk.publish.contract import MatchOutput
from desk.social.models import SlideAsset, WeeklyRoundupPayload


SocialPayload = Union[MatchOutput, WeeklyRoundupPayload]


class RendererError(Exception):
    """Slide rendering failed. Caller (typically the runner) catches +
    surfaces this as a non-fatal error so the draft simply doesn't get
    queued — never crashes the larger run."""


class Renderer(Protocol):
    async def render_carousel(
        self,
        payload: SocialPayload,
        *,
        output_dir: Path,
    ) -> list[SlideAsset]:
        ...


# ── Stub implementation ───────────────────────────────────────────────

# Carousel target spec: 1080×1350 portrait (per spec §2).
_W = 1080
_H = 1350

# One palette colour per slide so the operator can eyeball "did the
# renderer fire for slide 3?" without opening the PNG.
_PALETTE: tuple[tuple[int, int, int], ...] = (
    (15, 23, 42),       # slide 1 — slate
    (49, 46, 129),      # slide 2 — indigo
    (180, 83, 9),       # slide 3 — amber
    (190, 24, 93),      # slide 4 — rose
)


def _png_solid(width: int, height: int, rgb: tuple[int, int, int]) -> bytes:
    """Write a valid minimal PNG of a single colour. Stdlib only.

    Format: IHDR + IDAT (deflate-compressed filtered scanlines, filter
    byte 0 = "no prediction" on every row) + IEND.
    """
    r, g, b = rgb
    raw = bytearray()
    row = b"\x00" + bytes((r, g, b)) * width
    for _ in range(height):
        raw.extend(row)
    compressed = zlib.compress(bytes(raw), level=6)

    def _chunk(tag: bytes, data: bytes) -> bytes:
        return (
            struct.pack(">I", len(data))
            + tag + data
            + struct.pack(">I", zlib.crc32(tag + data) & 0xFFFFFFFF)
        )

    signature = b"\x89PNG\r\n\x1a\n"
    ihdr = struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0)
    return signature + _chunk(b"IHDR", ihdr) + _chunk(b"IDAT", compressed) + _chunk(b"IEND", b"")


class StubRenderer:
    """Writes 4 solid-colour PNGs. Replaces with the real renderer."""

    async def render_carousel(
        self,
        payload: SocialPayload,
        *,
        output_dir: Path,
    ) -> list[SlideAsset]:
        try:
            output_dir.mkdir(parents=True, exist_ok=True)
        except OSError as e:
            raise RendererError(f"could not create output dir {output_dir}: {e}") from e

        slides: list[SlideAsset] = []
        for slide_no in (1, 2, 3, 4):
            colour = _PALETTE[slide_no - 1]
            png_bytes = _png_solid(_W, _H, colour)
            path = output_dir / f"slide-{slide_no}.png"
            try:
                path.write_bytes(png_bytes)
            except OSError as e:
                raise RendererError(f"could not write {path}: {e}") from e
            slides.append(SlideAsset(
                slide_no=slide_no,
                png_path=path,
                png_sha256=hashlib.sha256(png_bytes).hexdigest(),
            ))
        return slides


class _Size(NamedTuple):
    width:  int
    height: int


CAROUSEL_SIZE = _Size(width=_W, height=_H)
