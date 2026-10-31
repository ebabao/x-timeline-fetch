#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""探针 3：在 GitHub Runner 内套代理访问 syndication，绕开 Runner IP 的 429。

Runner 是共享 Azure 出口 IP，几乎必然被 X 限流。但 Runner 能访问 GitHub，
所以可以实时拉免费代理列表，用 SOCKS5 代理换出口 IP 去取 syndication ——
这正是本地沙箱验证过可行的路子（曾成功取回 473KB 完整时间线）。
"""
import re
import json
import time
import random
import datetime
import requests
from concurrent.futures import ThreadPoolExecutor, as_completed

UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36")
HANDLE = "SCMPChinese"
URL = "https://syndication.twitter.com/srv/timeline-profile/screen-name/" + HANDLE


def snow_ts(tid):
    try:
        return datetime.datetime.utcfromtimestamp(
            ((int(tid) >> 22) + 1288834974657) / 1000).strftime("%Y-%m-%d %H:%M")
    except Exception:
        return "?"


def parse_synd(html_text):
    m = re.search(r'<script id="__NEXT_DATA__" type="application/json">([\s\S]*?)</script>',
                  html_text)
    if not m:
        return []
    try:
        d = json.loads(m.group(1))
    except Exception:
        return []
    found = []

    def walk(n):
        if isinstance(n, dict):
            if isinstance(n.get("entries"), list):
                found.extend([x for x in n["entries"] if isinstance(x, dict)])
            for v in n.values():
                walk(v)
        elif isinstance(n, list):
            for v in n:
                walk(v)
    walk(d)
    out, seen = [], set()
    for e in found:
        tw = (e.get("content") or {}).get("tweet") or {}
        if not isinstance(tw, dict) or not tw:
            continue
        tid = tw.get("id_str")
        if not tid or tid in seen:
            continue
        seen.add(tid)
        out.append((tid, (tw.get("full_text") or "").replace("\n", " ")[:50]))
    return out


print("=" * 62)
print("步骤 1：从 GitHub 拉免费 SOCKS5 代理列表")
print("=" * 62)
proxy_files = {
    "socks5": "https://raw.githubusercontent.com/TheSpeedX/PROXY-List/master/socks5.txt",
    "http": "https://raw.githubusercontent.com/TheSpeedX/PROXY-List/master/http.txt",
}
pool = []
for kind, url in proxy_files.items():
    try:
        r = requests.get(url, timeout=30)
        lines = [l.strip() for l in r.text.splitlines() if l.strip() and ":" in l]
        pool += ["socks5://" + l if kind == "socks5" else "http://" + l for l in lines]
        print("  {}: {} 条".format(kind, len(lines)))
    except Exception as e:
        print("  {} 拉取失败 {}".format(kind, str(e)[:60]))

random.shuffle(pool)
sample = pool[:400]
print("  合计 {} 条，本轮测试 {} 条".format(len(pool), len(sample)))

print("\n" + "=" * 62)
print("步骤 2：并发用代理打 syndication")
print("=" * 62)

hits, tried = [], 0


def probe(proxy):
    try:
        r = requests.get(URL, headers={"User-Agent": UA},
                         proxies={"http": proxy, "https": proxy}, timeout=12)
        if r.status_code == 200:
            tws = parse_synd(r.text)
            if tws:
                return proxy, tws
        return None
    except Exception:
        return None


t0 = time.time()
with ThreadPoolExecutor(max_workers=40) as ex:
    futs = {ex.submit(probe, p): p for p in sample}
    for f in as_completed(futs):
        tried += 1
        if tried % 50 == 0:
            print("  进度 {}/{} 命中 {} 用时 {:.0f}s".format(
                tried, len(sample), len(hits), time.time() - t0), flush=True)
        r = f.result()
        if r:
            hits.append(r)
            proxy, tws = r
            print("  ★ HIT {} 条 最新={} 代理={}".format(
                len(tws), snow_ts(tws[0][0]), proxy), flush=True)
            if len(hits) >= 2:
                ex.shutdown(wait=False, cancel_futures=True)
                break

print("\n" + "=" * 62)
print("结果：{} / {} 命中".format(len(hits), tried))
print("=" * 62)
if hits:
    proxy, tws = hits[0]
    print("★ 可用代理: " + proxy)
    print("★ 拿到 {} 条真实时间线".format(len(tws)))
    print("  最新: {}  {}".format(snow_ts(tws[0][0]), tws[0][1]))
    print("  最旧: {}  {}".format(snow_ts(tws[-1][0]), tws[-1][1]))
    print("\n结论：Actions + 代理 + syndication 可行")
else:
    print("未命中。说明这批免费代理在 Runner 上也不可用。")
