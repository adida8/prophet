"""Capture a slice of the site list."""
import asyncio, json, os, sys
from pathlib import Path
from playwright.async_api import async_playwright

ROOT = Path("/sessions/wonderful-sleepy-carson/mnt/prophet/branding/research")
SHOTS = ROOT / "screenshots"
SHOTS.mkdir(parents=True, exist_ok=True)

ALL = [
    ("oddschecker",     "https://www.oddschecker.com/",          "odds"),
    ("pinnacle",        "https://www.pinnacle.com/",              "odds"),
    ("oddsportal",      "https://www.oddsportal.com/",            "odds"),
    ("smarkets",        "https://smarkets.com/",                  "odds"),
    ("polymarket",      "https://polymarket.com/",                "odds"),
    ("actionnetwork",   "https://www.actionnetwork.com/",         "odds"),
    ("theathletic",     "https://www.nytimes.com/athletic/football/",  "publication"),
    ("tifofootball",    "https://www.tifofootball.com/",          "publication"),
    ("scoutedftbl",     "https://scoutedftbl.com/",               "publication"),
    ("theblizzard",     "https://www.theblizzard.co.uk/",         "publication"),
    ("coachesvoice",    "https://www.coachesvoice.com/",          "publication"),
    ("thesetpieces",    "https://thesetpieces.com/",              "publication"),
    ("fotmob",          "https://www.fotmob.com/",                "consumer"),
    ("sofascore",       "https://www.sofascore.com/",             "consumer"),
    ("bbcsport",        "https://www.bbc.co.uk/sport/football",   "consumer"),
    ("skysports",       "https://www.skysports.com/football",     "consumer"),
    ("goal",            "https://www.goal.com/en",                "consumer"),
    ("bet365",          "https://www.bet365.com/",                "avoid"),
    ("williamhill",     "https://www.williamhill.com/",           "avoid"),
    ("paddypower",      "https://www.paddypower.com/",            "avoid"),
]


async def capture(p, name, url, bucket):
    target = SHOTS / f"{name}.png"
    if target.exists() and target.stat().st_size > 5000:
        print(f"cached {name}", flush=True)
        return
    browser = await p.chromium.launch(headless=True, args=["--no-sandbox"])
    context = await browser.new_context(
        viewport={"width": 1280, "height": 800},
        user_agent="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0 Safari/537.36",
        locale="en-GB",
    )
    page = await context.new_page()
    try:
        await page.goto(url, wait_until="domcontentloaded", timeout=15000)
        await page.wait_for_timeout(2200)
        await page.screenshot(path=str(target), full_page=False, clip={"x":0,"y":0,"width":1280,"height":800})
        print(f"ok {name}", flush=True)
    except Exception as e:
        print(f"err {name}: {e.__class__.__name__}", flush=True)
    finally:
        await context.close()
        await browser.close()


async def main():
    start = int(sys.argv[1]) if len(sys.argv) > 1 else 0
    end   = int(sys.argv[2]) if len(sys.argv) > 2 else len(ALL)
    async with async_playwright() as p:
        for name, url, bucket in ALL[start:end]:
            await capture(p, name, url, bucket)

asyncio.run(main())
