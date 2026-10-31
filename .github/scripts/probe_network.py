import concurrent.futures
import datetime
import html
import json
import os
import re
import requests

UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"
H = "SCMPChinese"
FULL = "?dnt=true&embedId=twitter-widget-0&frame=false&hideBorder=false&hideFooter=false&hideHeader=false&hideScrollBar=false&lang=en&maxHeight=600px&origin=https%3A%2F%2Fplatform.twitter.com&sessionId=0123456789abcdef0123456789abcdef&showHeader=true&showReplies=false&transparent=false&widgetsVersion=26155f7e52b7e0%3A1702314776716"
URLS = [
    "https://syndication.twitter.com/srv/timeline-profile/screen-name/" + H,
    "https://syndication.twitter.com/srv/timeline-profile/screen-name/" + H + FULL,
    "https://cdn.syndication.twimg.com/timeline/profile?screen_name=" + H + "&dnt=true&lang=en",
    "https://publish.twitter.com/oembed?url=https://x.com/" + H,
    "https://r.jina.ai/https://x.com/" + H,
    "https://r.jina.ai/http://twitter.com/" + H,
    "https://r.jina.ai/https://twstalker.com/" + H,
    "https://twstalker.com/" + H,
    "https://www.twstalker.com/" + H,
    "https://sotwe.com/" + H,
    "https://www.sotwe.com/" + H,
    "https://x-com.translate.goog/" + H + "?_x_tr_sl=auto&_x_tr_tl=zh-CN&_x_tr_hl=zh-CN",
    "https://twiscan.com/en/x/" + H,
]
for host in ["nitter.net", "xcancel.com", "nitter.poast.org", "nitter.privacyredirect.com", "lightbrd.com", "twiiit.com", "twetero.com", "nitter.tiekoetter.com", "nitter.space", "nitter.1d4.us", "nitter.kavin.rocks", "nitter.unixfox.eu", "nitter.namazso.eu", "nitter.oksocial.net", "nitter.adminforge.de", "nitter.catsarch.com", "nitter.perennialte.ch", "nitter.eu.projectsegfau.lt", "nitter.moomoo.me", "nitter.nerdvpn.de"]:
    URLS.append("https://" + host + "/" + H)

def snowflake(tid):
    try:
        return datetime.datetime.fromtimestamp(((int(tid) >> 22) + 1288834974657) / 1000, datetime.timezone.utc).strftime("%Y-%m-%d")
    except Exception:
        return "?"

def probe(url):
    try:
        r = requests.get(url, headers={"User-Agent": UA, "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8"}, timeout=18, allow_redirects=True)
        text = r.text
        ids = set(re.findall(r"(?:status/|id_str[\\\"': ]+)(\d{15,22})", text))
        dates = sorted({snowflake(i) for i in ids}, reverse=True)
        title = re.search(r"<title[^>]*>(.*?)</title>", text, re.I | re.S)
        title = html.unescape(re.sub(r"\s+", " ", title.group(1))).strip()[:80] if title else ""
        chinese = re.findall(r"[\u4e00-\u9fff][^<>\"\\]{8,90}", text)
        useful = r.status_code == 200 and (len(ids) > 0 or len(chinese) > 3 or "timeline-item" in text or "__NEXT_DATA__" in text)
        marker = "HIT" if useful else ""
        print("%-4s code=%s bytes=%-7s ids=%-3s dates=%s %s\n     %s\n     title=%s cn=%s" % (
            marker, r.status_code, len(r.content), len(ids), ",".join(dates[:3]), url, r.url[:120], title, len(chinese)), flush=True)
        if useful:
            os.makedirs("/tmp/probe_hits", exist_ok=True)
            name = re.sub(r"[^A-Za-z0-9]+", "_", url)[:150]
            with open("/tmp/probe_hits/" + name + ".html", "w", encoding="utf-8") as f:
                f.write(text)
            for c in chinese[:3]:
                print("     CN", c[:120], flush=True)
    except Exception as e:
        print("ERR  %-95s %s" % (url[:95], str(e)[:90]), flush=True)

print("RUNNER_OS=", os.environ.get("RUNNER_OS"), "targets=", len(URLS), flush=True)
with concurrent.futures.ThreadPoolExecutor(max_workers=8) as ex:
    list(ex.map(probe, URLS))
print("DONE", flush=True)
