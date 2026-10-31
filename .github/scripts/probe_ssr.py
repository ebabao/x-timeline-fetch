import concurrent.futures
import datetime
import os
import re
import urllib.parse
import requests

UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"
H = "SCMPChinese"
T = "https://syndication.twitter.com/srv/timeline-profile/screen-name/" + H
URLS = []
for p in ["with_replies", "media", "?f=live", "?tab=timeline"]:
    URLS.append("https://r.jina.ai/https://x.com/" + H + "/" + p)
    URLS.append("https://x-com.translate.goog/" + H + "/" + p + ("&" if "?" in p else "?") + "_x_tr_sl=auto&_x_tr_tl=en&_x_tr_hl=en&_x_tr_pto=wapp")
URLS += [
    "https://r.jina.ai/" + T,
    "https://r.jina.ai/http://syndication.twitter.com/srv/timeline-profile/screen-name/" + H,
    "https://syndication-twitter-com.translate.goog/srv/timeline-profile/screen-name/" + H + "?_x_tr_sl=auto&_x_tr_tl=en&_x_tr_hl=en&_x_tr_pto=wapp",
    "https://proxy.corsfix.com/?" + T,
    "https://api.allorigins.win/raw?url=" + urllib.parse.quote(T, safe=""),
    "https://api.codetabs.com/v1/proxy?quest=" + urllib.parse.quote(T, safe=""),
    "https://cors.isomorphic-git.org/" + T,
]

def snowflake(tid):
    try:
        return datetime.datetime.fromtimestamp(((int(tid) >> 22) + 1288834974657) / 1000, datetime.timezone.utc).strftime("%Y-%m-%d")
    except Exception:
        return "?"

def probe(url):
    try:
        r = requests.get(url, headers={"User-Agent": UA, "Origin": "https://corsfix.com", "Accept-Language": "en-US,en;q=0.9"}, timeout=55)
        ids = set(re.findall(r"(?:status/|id_str[\"\\' :]+)(\d{15,22})", r.text))
        dates = sorted({snowflake(i) for i in ids}, reverse=True)
        recent = bool(dates and dates[0] >= "2026-01-01")
        print("%s code=%s bytes=%s ids=%s dates=%s %s" % ("RECENT" if recent else "", r.status_code, len(r.content), len(ids), dates[:5], url), flush=True)
        print(r.text[:180].replace("\n", " "), flush=True)
        if len(r.content) > 10000 or recent:
            os.makedirs("/tmp/ssr_hits", exist_ok=True)
            name = re.sub(r"[^A-Za-z0-9]+", "_", url)[:150]
            with open("/tmp/ssr_hits/" + name + ".txt", "w", encoding="utf-8") as f:
                f.write(r.text)
        if recent:
            print("*** RECENT TIMELINE HIT ***", flush=True)
            for c in re.findall(r"[\u4e00-\u9fff][^<>\"\\]{8,100}", r.text)[:4]:
                print("CN", c[:120], flush=True)
    except Exception as e:
        print("ERR", url, repr(e)[:180], flush=True)

with concurrent.futures.ThreadPoolExecutor(max_workers=6) as ex:
    list(ex.map(probe, URLS))
print("DONE", flush=True)
