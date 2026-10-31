import datetime
import json
import os
import re
import time
from curl_cffi import requests

HANDLES = [x.strip() for x in os.environ.get(
    "HANDLES",
    "SCMPChinese,cnfinancewatch,baoshu88,fxtrader,dmjk001,business,SCMPNews,nytchinese,bbcchinese,RFI_Cn,ReutersChina,CrushTheShorts"
).split(",") if x.strip()]
os.makedirs("/tmp/syndication_latest", exist_ok=True)

def ts(tid):
    return datetime.datetime.fromtimestamp(((int(tid) >> 22) + 1288834974657) / 1000, datetime.timezone.utc).strftime("%Y-%m-%d %H:%M")

summary = []
consecutive_429 = 0
for i, handle in enumerate(HANDLES):
    if i:
        time.sleep(12)
    url = "https://syndication.twitter.com/srv/timeline-profile/screen-name/" + handle
    try:
        r = requests.get(url, impersonate="safari", timeout=45)
    except Exception as e:
        print(handle, "ERROR", repr(e), flush=True)
        summary.append({"handle": handle, "status": "error", "error": str(e)[:120]})
        continue
    reset = r.headers.get("x-rate-limit-reset")
    reset_s = datetime.datetime.fromtimestamp(int(reset), datetime.timezone.utc).strftime("%H:%M:%S") if reset and reset.isdigit() else "?"
    print(handle, "HTTP", r.status_code, "bytes", len(r.content), "reset", reset_s, flush=True)
    if r.status_code != 200:
        print(r.text[:120], flush=True)
        summary.append({"handle": handle, "status": r.status_code, "reset": reset_s})
        if r.status_code == 429:
            consecutive_429 += 1
            if consecutive_429 >= 2:
                print("two consecutive 429, stop to preserve the window", flush=True)
                break
        continue
    consecutive_429 = 0
    text = r.text
    ids = sorted(set(re.findall(r'"id_str"\s*:\s*"(\d+)"', text)), key=int, reverse=True)
    dates = [(x, ts(x)) for x in ids]
    chinese = [x for x in re.findall(r"[\u4e00-\u9fff][^<>\"\\]{8,120}", text)][:3]
    print("  tweets", len(ids), "newest", dates[:3], "cn", chinese[:1], flush=True)
    with open("/tmp/syndication_latest/" + handle + ".html", "w", encoding="utf-8") as f:
        f.write(text)
    summary.append({"handle": handle, "status": 200, "tweets": len(ids),
                    "newest": dates[0][1] if dates else None,
                    "oldest": dates[-1][1] if dates else None,
                    "cn_sample": chinese[0] if chinese else None})

with open("/tmp/syndication_latest/_summary.json", "w", encoding="utf-8") as f:
    json.dump(summary, f, ensure_ascii=False, indent=1)
print("SUMMARY", json.dumps(summary, ensure_ascii=False)[:1800], flush=True)
