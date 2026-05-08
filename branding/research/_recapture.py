"""Re-capture screenshots that were obstructed by cookie modals.

Approach: navigate, wait, then attempt to click any of a wide set of common cookie-banner
accept buttons by text or selector. If found, click and wait. Then screenshot.
"""
import asyncio, sys
from pathlib import Path
from playwright.async_api import async_playwright

ROOT = Path("/sessions/wonderful-sleepy-carson/mnt/prophet/branding/research")
SHOTS = ROOT / "screenshots"

# Sites where we want a clean re-render
TARGETS = [
    ("bbcsport",      "https://www.bbc.co.uk/sport/football"),
    ("scoutedftbl",   "https://scoutedftbl.com/"),
    ("theathletic",   "https://www.nytimes.com/athletic/football/"),
    ("tifofootball",  "https://www.tifofootball.com/"),
    ("oddsportal",    "https://www.oddsportal.com/"),
    ("oddschecker",   "https://www.oddschecker.com/"),
    ("paddypower",    "https://www.paddypower.com/"),
    ("williamhill",   "https://www.williamhill.com/"),
    ("bet365",        "https://www.bet365.com/"),
    ("goal",          "https://www.goal.com/en"),
    ("skysports",     "https://www.skysports.com/football"),
    ("sofascore",     "https://www.sofascore.com/"),
    ("fotmob",        "https://www.fotmob.com/"),
    ("polymarket",    "https://polymarket.com/"),
    ("actionnetwork", "https://www.actionnetwork.com/"),
    ("pinnacle",      "https://www.pinnacle.com/"),
    ("thesetpieces",  "https://thesetpieces.com/"),
    ("theblizzard",   "https://www.theblizzard.co.uk/"),
    ("coachesvoice",  "https://www.coachesvoice.com/"),
    ("betfair",       "https://www.betfair.com/exchange/plus/football"),
]

ACCEPT_TEXTS = ["I agree", "Accept", "Accept all", "Accept All", "Accept all cookies",
                "I accept", "Got it", "Allow all", "Allow All", "Agree",
                "Aceptar", "ACCEPT", "Continue", "Yes, I agree", "Accept Cookies",
                "Agree and continue"]

BLOCK_RESOURCES = {"image","media","font"}  # speed up


async def kill_overlay(page):
    # try the OneTrust standard
    sels = [
        "#onetrust-accept-btn-handler",
        "#truste-consent-button",
        "button[aria-label='Accept all']",
        "button[aria-label='I agree']",
        "button[id*='accept']",
        "button[class*='accept']",
        "button.fc-cta-consent",
        "button[mode='primary']",
    ]
    for sel in sels:
        try:
            btn = await page.query_selector(sel)
            if btn:
                await btn.click(timeout=1500)
                await page.wait_for_timeout(800)
                return True
        except Exception:
            pass
    # Fallback: text-match
    for txt in ACCEPT_TEXTS:
        try:
            await page.get_by_role("button", name=txt).first.click(timeout=1500)
            await page.wait_for_timeout(800)
            return True
        except Exception:
            try:
                await page.get_by_text(txt, exact=True).first.click(timeout=1500)
                await page.wait_for_timeout(800)
                return True
            except Exception:
                pass
    return False


async def capture(p, name, url):
    target = SHOTS / f"{name}.png"
    browser = await p.chromium.launch(headless=True, args=["--no-sandbox"])
    ctx = await browser.new_context(
        viewport={"width": 1280, "height": 800},
        user_agent="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0 Safari/537.36",
        locale="en-GB",
    )
    page = await ctx.new_page()
    try:
        await page.goto(url, wait_until="domcontentloaded", timeout=15000)
        await page.wait_for_timeout(1800)
        clicked = await kill_overlay(page)
        await page.wait_for_timeout(1200 if clicked else 600)
        await page.screenshot(path=str(target), clip={"x":0,"y":0,"width":1280,"height":800})
        print(f"ok {name} (clicked={clicked})", flush=True)
    except Exception as e:
        print(f"err {name}: {e.__class__.__name__}: {str(e)[:80]}", flush=True)
    finally:
        await ctx.close()
        await browser.close()


async def main():
    start = int(sys.argv[1]) if len(sys.argv) > 1 else 0
    end   = int(sys.argv[2]) if len(sys.argv) > 2 else len(TARGETS)
    async with async_playwright() as p:
        for name, url in TARGETS[start:end]:
            await capture(p, name, url)


asyncio.run(main())
