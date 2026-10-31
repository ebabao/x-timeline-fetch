#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""探针 2：既然 guest GraphQL 只能看 highlights，测别的能拿「真实时间线」的路。

候选：
  A. syndication timeline-profile（返回按时间倒序的真实时间线，但按 IP 限流）
     测不同 UA / Referer / 重试间隔，看 429 是否可绕
  B. cdn.syndication.twimg.com/tweet-result（单条，确认可用）
  C. GraphQL SearchTimeline / SearchAdaptive（按 from:handle 搜最新）
  D. profile 页的 __NEXT_DATA__（x.com 主页 SSR 数据）
"""
import json
import re
import time
import datetime
import requests

UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36")
BEARER = ("AAAAAAAAAAAAAAAAAAAAANRILgAAAAAAnNwIzUejRCOuH5E6I8xnZz4puTs"
          "%3D1Zv7ttfk8LF81IUq16cHjhLTvJu4FA33AGWWjCpTnA")
HANDLE = "SCMPChinese"


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
        out.append((tid, (tw.get("full_text") or "")[:40].replace("\n", " ")))
    return out


print("=" * 62)
print("A. syndication timeline-profile —— 重试 / 换头 能否绕 429")
print("=" * 62)
variants = [
    ("默认UA", {"User-Agent": UA}),
    ("加Referer", {"User-Agent": UA, "Referer": "https://platform.twitter.com/"}),
    ("Googlebot", {"User-Agent": "Mozilla/5.0 (compatible; Googlebot/2.1; "
                                "+http://www.google.com/bot.html)"}),
    ("无UA", {"User-Agent": ""}),
]
for label, h in variants:
    for attempt in range(2):
        try:
            r = requests.get(
                "https://syndication.twitter.com/srv/timeline-profile/screen-name/" + HANDLE,
                headers=h, timeout=30)
            n = len(parse_synd(r.text)) if r.status_code == 200 else 0
            print("  {:12s} 第{}次 status={} len={:7d} 解析={} retry-after={}".format(
                label, attempt + 1, r.status_code, len(r.text), n,
                r.headers.get("retry-after", "-")), flush=True)
            if n:
                tws = parse_synd(r.text)
                print("     ★ 最新={} 最旧={}".format(
                    snow_ts(tws[0][0]), snow_ts(tws[-1][0])))
                print("     ★ 样例: " + tws[0][1])
                raise SystemExit(0)
        except SystemExit:
            raise
        except Exception as e:
            print("  {:12s} 异常 {}".format(label, str(e)[:60]), flush=True)
        time.sleep(8)

print("\n" + "=" * 62)
print("B. GraphQL SearchTimeline / SearchAdaptive")
print("=" * 62)
s = requests.Session()
s.headers.update({"User-Agent": UA, "Authorization": "Bearer " + BEARER,
                  "Accept-Language": "zh-CN,zh;q=0.9"})
try:
    r = s.post("https://api.x.com/1.1/guest/activate.json", timeout=30)
    s.headers["x-guest-token"] = r.json()["guest_token"]
    print("  guest token OK")
except Exception as e:
    print("  token 失败", e)

# 常见的 SearchTimeline queryId（多试几个）
SEARCH_OPS = [
    "M1jEez78PEfVfbQLvlWMvx5r5hE/SearchTimeline",
    "Yw7NjQwwZDhVF_lS1d8KFw/SearchTimeline",
    "B4eQpCb0e1_9GrTkP9Y3GQ/SearchTimeline",
]
for op in SEARCH_OPS:
    v = {"rawQuery": "from:" + HANDLE, "count": 40,
         "querySource": "typed_query", "product": "Latest"}
    try:
        r = s.get("https://x.com/i/api/graphql/" + op,
                  params={"variables": json.dumps(v, separators=(",", ":"))}, timeout=30)
        print("  {:45s} status={} len={}".format(op[:44], r.status_code, len(r.text)), flush=True)
        if r.status_code == 200:
            txt = r.text
            ids = re.findall(r'"id_str":"(\d{15,25})"', txt)
            if ids:
                print("     ★ 拿到 {} 条，最新={} 最旧={}".format(
                    len(ids), snow_ts(ids[0]), snow_ts(ids[-1])))
                raise SystemExit(0)
    except SystemExit:
        raise
    except Exception as e:
        print("  异常", str(e)[:60])
    time.sleep(1.5)

print("\n" + "=" * 62)
print("C. x.com 主页 SSR（__NEXT_DATA__）")
print("=" * 62)
try:
    r = requests.get("https://x.com/" + HANDLE, headers={"User-Agent": UA}, timeout=30)
    print("  status={} len={} 含__NEXT_DATA__={}".format(
        r.status_code, len(r.text), "__NEXT_DATA__" in r.text))
    ids = re.findall(r'status/(\d{15,25})', r.text)
    if ids:
        print("  ★ 页面含 {} 个 status id，最新={}".format(len(set(ids)), snow_ts(ids[0])))
except Exception as e:
    print("  异常", str(e)[:60])

print("\n=== 探针2 结束 ===")
