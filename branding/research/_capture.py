"""Capture homepage screenshots for the 20-site sample, then extract dominant colors."""
import asyncio
import json
import os
import sys
from pathlib import Path

from playwright.async_api import async_playwright

ROOT = Path("/sessions/wonderful-sleepy-carson/mnt/prophet/branding/research")
SHOTS = ROOT / "screenshots"
SHOTS.mkdir(parents=True, exist_ok=True)

SITES = [
    # Direct competitors / odds
    ("oddschecker",     "https://www.oddschecker.com/",          "odds"),
    ("pinnacle",        "https://www.pinnacle.com/",              "odds"),
    ("oddsportal",      "https://www.oddsportal.com/",            "odds"),
    ("smarkets",        "https://smarkets.com/",                  "odds"),
    ("polymarket",      "https://polymarket.com/",                "odds"),
    ("actionnetwork",   "https://www.actionnetwork.com/",         "odds"),
    # Adjacent quality football publications
    ("theathletic",     "https://www.nytimes.com/athletic/football/",  "publication"),
    ("tifofootball",    "https://www.tifofootball.com/",          "publication"),
    ("scoutedftbl",     "https://scoutedftbl.com/",               "publication"),
    ("theblizzard",     "https://www.theblizzard.co.uk/",         "publication"),
    ("coachesvoice",    "https://www.coachesvoice.com/",          "publication"),
    ("thesetpieces",    "https://thesetpieces.com/",              "publication"),
    # Football-native consumer
    ("fotmob",          "https://www.fotmob.com/",                "consumer"),
    ("sofascore",       "https://www.sofascore.com/",             "consumer"),
    ("bbcsport",        "https://www.bbc.co.uk/sport/football",   "consumer"),
    ("skysports",       "https://www.skysports.com/football",     "consumer"),
    ("goal",            "https://www.goal.com/en",                "consumer"),
    # AVOID — gambling promo
    ("bet365",          "https://www.bet365.com/",                "avoid"),
    ("williamhill",     "https://www.williamhill.com/",           "avoid"),
    ("paddypower",      "https://www.paddypower.com/",            "avoid"),
]

# Substitutes if needed
SUBS = [
    ("11freunde",       "https://11freunde.de/",                  "publication"),
    ("mundialmag",      "https://www.mundialmag.com/",            "publication"),
    ("footyheadlines",  "https://www.footyheadlines.com/",        "publication"),
]


async def capture(p, name, url, bucket):
    target = SHOTS / f"{name}.png"
    if target.exists() and target.stat().st_size > 5000:
        return {"name": name, "url": url, "bucket": bucket, "status": "cached"}
    browser = await p.chromium.launch(headless=True, args=["--no-sandbox", "--disable-blink-features=AutomationControlled"])
    context = await browser.new_context(
        viewport={"width": 1280, "height": 800},
        user_agent="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0 Safari/537.36",
        locale="en-GB",
    )
    page = await context.new_page()
    status = "ok"
    try:
        await page.goto(url, wait_until="domcontentloaded", timeout=20000)
        # try to dismiss cookie banners by ignoring overlays — just wait briefly for layout
        await page.wait_for_timeout(2500)
        await page.screenshot(path=str(target), full_page=False, clip={"x":0,"y":0,"width":1280,"height":800})
    except Exception as e:
        status = f"err: {e.__class__.__name__}: {str(e)[:120]}"
    finally:
        await context.close()
        await browser.close()
    return {"name": name, "url": url, "bucket": bucket, "status": status}


async def main():
    targets = SITES.copy()
    if "--subs" in sys.argv:
        targets = SUBS
    results = []
    async with async_playwright() as p:
        # serial — friendlier to memory in sandbox
        for name, url, bucket in targets:
            r = await capture(p, name, url, bucket)
            print(r["status"], name, file=sys.stderr, flush=True)
            results.append(r)
    print(json.dumps(results, indent=2))


if __name__ == "__main__":
    asyncio.run(main())
