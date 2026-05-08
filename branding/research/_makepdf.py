"""Render landscape_filled.html to PDF via headless Chromium."""
import asyncio
from pathlib import Path
from playwright.async_api import async_playwright

ROOT = Path("/sessions/wonderful-sleepy-carson/mnt/prophet/branding/research")
HTML = ROOT / "landscape_filled.html"
PDF  = ROOT / "landscape.pdf"


async def main():
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True, args=["--no-sandbox"])
        ctx = await browser.new_context(viewport={"width": 1100, "height": 1500})
        page = await ctx.new_page()
        await page.goto("file://" + str(HTML), wait_until="networkidle")
        await page.wait_for_timeout(800)
        await page.pdf(path=str(PDF), format="A4",
                       margin={"top":"14mm","bottom":"14mm","left":"14mm","right":"14mm"},
                       print_background=True, prefer_css_page_size=True)
        await browser.close()
        print("ok", PDF, PDF.stat().st_size)

asyncio.run(main())
