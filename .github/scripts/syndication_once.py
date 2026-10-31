import datetime
import json
import os
import re
import sys
from curl_cffi import requests

handle = os.environ.get("HANDLE", "SCMPChinese")
shard = os.environ.get("SHARD", "0")
url = "https://syndication.twitter.com/srv/timeline-profile/screen-name/" + handle
r = requests.get(url, impersonate="safari", timeout=40)
print("shard", shard, "status", r.status_code, "bytes", len(r.content), flush=True)
print("headers", json.dumps({k: v for k, v in r.headers.items() if k.lower() in ["retry-after", "x-rate-limit-reset", "server", "cf-ray"]}), flush=True)
if r.status_code != 200:
    print(r.text[:300], flush=True)
    sys.exit(0)
text = r.text
ids = sorted(set(re.findall(r'"id_str"\s*:\s*"(\d+)"', text)), key=int, reverse=True)
def dt(tid):
    return datetime.datetime.fromtimestamp(((int(tid) >> 22) + 1288834974657) / 1000, datetime.timezone.utc).isoformat()
print("tweet ids", len(ids), "newest", [(i, dt(i)) for i in ids[:5]], flush=True)
os.makedirs("/tmp/syndication_success", exist_ok=True)
with open("/tmp/syndication_success/timeline_" + handle + ".html", "w", encoding="utf-8") as f:
    f.write(text)
if ids and dt(ids[0]) >= "2026-01-01":
    print("*** LATEST TIMELINE SUCCESS ***", flush=True)
