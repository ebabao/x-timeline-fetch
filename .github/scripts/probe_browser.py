import datetime
import os
import re
from playwright.sync_api import sync_playwright

URLS = [
    "https://nitter.tiekoetter.com/SCMPChinese",
    "https://twstalker.com/SCMPChinese",
    "https://sotwe.com/SCMPChinese",
    "https://xcancel.com/SCMPChinese",
]

def snowflake(tid):
    try:
        return datetime.datetime.fromtimestamp(((int(tid) >> 22) + 1288834974657) / 1000, datetime.timezone.utc).strftime("%Y-%m-%d")
    except Exception:
        return "?"

os.makedirs("/tmp/browser_hits", exist_ok=True)
with sync_playwright() as p:
    browser = p.chromium.launch(headless=True, args=["--disable-blink-features=AutomationControlled", "--no-sandbox"])
    context = browser.new_context(
        user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
        locale="en-US", viewport={"width": 1365, "height": 900},
    )
    context.add_init_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")
    for url in URLS:
        page = context.new_page()
        print("\n===", url, flush=True)
        try:
            page.goto(url, wait_until="domcontentloaded", timeout=60000)
            page.wait_for_timeout(20000)
            content = page.content()
            title = page.title()
            ids = set(re.findall(r"(?:status/|id_str[\"\\' :]+)(\d{15,22})", content))
            dates = sorted({snowflake(i) for i in ids}, reverse=True)
            print("final:", page.url, "title:", title, "bytes:", len(content), "ids:", len(ids), "dates:", dates[:6], flush=True)
            print("text:", page.locator("body").inner_text()[:700].replace("\n", " / "), flush=True)
            name = re.sub(r"[^A-Za-z0-9]+", "_", url)
            with open("/tmp/browser_hits/" + name + ".html", "w", encoding="utf-8") as f:
                f.write(content)
            page.screenshot(path="/tmp/browser_hits/" + name + ".png", full_page=False)
            if dates and dates[0] >= "2026-01-01":
                print("*** RECENT TIMELINE HIT ***", flush=True)
        except Exception as e:
            print("ERROR", repr(e), flush=True)
        page.close()
    browser.close()
