"""Renderer stub tests — PNGs are valid, sha matches, dim is 1080×1350."""

from __future__ import annotations

import asyncio
import hashlib
import struct
from pathlib import Path

from desk.social.renderer import CAROUSEL_SIZE, StubRenderer


def _read_png_size(path: Path) -> tuple[int, int]:
    data = path.read_bytes()
    assert data[:8] == b"\x89PNG\r\n\x1a\n"
    # IHDR chunk starts at byte 8; the 4-byte length, 4-byte type,
    # then 13 bytes of payload: width(4), height(4), bit_depth(1),
    # colour_type(1), compression(1), filter(1), interlace(1).
    width, height = struct.unpack(">II", data[16:24])
    return width, height


def test_stub_renders_four_slides(fra_mex_pick, tmp_path: Path) -> None:
    renderer = StubRenderer()
    slides = asyncio.run(renderer.render_carousel(fra_mex_pick, output_dir=tmp_path))
    assert len(slides) == 4
    for n, s in enumerate(slides, start=1):
        assert s.slide_no == n
        assert s.png_path.is_file()
        # Sha matches the file content.
        on_disk = s.png_path.read_bytes()
        assert hashlib.sha256(on_disk).hexdigest() == s.png_sha256


def test_stub_pngs_are_correct_size(fra_mex_pick, tmp_path: Path) -> None:
    renderer = StubRenderer()
    slides = asyncio.run(renderer.render_carousel(fra_mex_pick, output_dir=tmp_path))
    for s in slides:
        w, h = _read_png_size(s.png_path)
        assert (w, h) == (CAROUSEL_SIZE.width, CAROUSEL_SIZE.height)


def test_stub_pngs_differ_per_slide(fra_mex_pick, tmp_path: Path) -> None:
    """Palette tweak per slide → distinct sha256 across the carousel."""
    renderer = StubRenderer()
    slides = asyncio.run(renderer.render_carousel(fra_mex_pick, output_dir=tmp_path))
    shas = {s.png_sha256 for s in slides}
    assert len(shas) == 4
