#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""跑在 GitHub Runner 上：把 data/*.json 直接渲染成工作台页面。

为什么要在云端生成
------------------
最初页面是在本地沙箱 build 的，但沙箱里的定时任务跑在**独立实例**上，
它写进自己磁盘的产物不会回流到用户看到的那份文件 —— 表现就是"库更新了、
页面没变"。把生成搬到 Runner，页面和数据就永远同源，本地只需要一次 pull。

译文缓存
--------
site/translations.json 存 {推文id: 中文}，随每次提交累积。
这样只有新推文才会调 Bing，不会每轮把 600 条全部重译。

用法：
    python3 build_site.py --datadir data --out docs/index.html --limit 300
"""
import os
import re
import sys
import json
import time
import glob
import argparse
import datetime

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
SITE = os.path.join(ROOT, "site")
sys.path.insert(0, SITE)

import site_build                      # noqa: E402
from translator import BingTranslator  # noqa: E402

TRANSLATIONS = os.path.join(SITE, "translations.json")


def parse_ts(t):
    if not t:
        return 0
    if isinstance(t, (int, float)):
        return int(t)
    raw = str(t).strip()
    for fmt in ("%a %b %d %H:%M:%S %z %Y", "%Y-%m-%dT%H:%M:%S%z", "%Y-%m-%d %H:%M:%S"):
        try:
            dt = datetime.datetime.strptime(raw, fmt)
            if dt.tzinfo:
                return int(dt.timestamp())
            return int(dt.replace(tzinfo=datetime.timezone.utc).timestamp())
        except ValueError:
            continue
    return 0


def load_raw(datadir):
    rows = []
    for fp in sorted(glob.glob(os.path.join(datadir, "*.json"))):
        name = os.path.basename(fp)
        if name.startswith("_"):
            continue
        handle = name[:-5]
        try:
            data = json.load(open(fp, encoding="utf-8"))
        except Exception as e:
            print("  读取失败 {}: {}".format(name, str(e)[:60]))
            continue
        if isinstance(data, dict):
            data = data.get("items") or data.get("data") or []
        for t in data:
            if not t.get("id"):
                continue
            rows.append({
                "id": str(t["id"]),
                "handle": t.get("user") or handle,
                "ts": parse_ts(t.get("time")),
                "text": t.get("text") or "",
                "zh": None,
                "media": t.get("media") or [],
                "url": t.get("url") or "https://x.com/{}/status/{}".format(handle, t["id"]),
                "like": t.get("like") or 0,
                "reply": t.get("reply") or 0,
                "rt": t.get("rt") or 0,
                "view": t.get("view") or 0,
                "lang": t.get("lang") or "",
            })
    # 同一推文可能被多个账号文件收录，按 id 去重
    seen, uniq = set(), []
    for r in rows:
        if r["id"] in seen:
            continue
        seen.add(r["id"])
        uniq.append(r)
    return uniq


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--datadir", default=os.path.join(ROOT, "data"))
    ap.add_argument("--out", default=os.path.join(ROOT, "docs", "index.html"))
    ap.add_argument("--limit", type=int, default=300, help="单轮最多新译多少条")
    ap.add_argument("--days", type=int, default=0)
    ap.add_argument("--max-items", type=int, default=1000)
    args = ap.parse_args()

    rows = load_raw(args.datadir)
    print("读到 {} 条推文（去重后）".format(len(rows)))

    trans = {}
    if os.path.exists(TRANSLATIONS):
        try:
            trans = json.load(open(TRANSLATIONS, encoding="utf-8"))
        except Exception:
            trans = {}
    print("译文缓存已有 {} 条".format(len(trans)))

    todo = [r for r in rows if r["text"] and not site_build.has_cjk(r["text"])
            and r["id"] not in trans]
    print("需要新译 {} 条（本轮上限 {}）".format(len(todo), args.limit))
    if todo:
        tr = BingTranslator()
        ok = fail = 0
        t0 = time.time()
        for i, r in enumerate(todo[:args.limit], 1):
            try:
                zh = tr.translate(r["text"])
                if zh:
                    trans[r["id"]] = zh
                    ok += 1
                else:
                    fail += 1
            except Exception as e:
                fail += 1
                print("  !! {} {}".format(r["id"], str(e)[:60]))
                if fail % 4 == 0:
                    tr = BingTranslator()
                time.sleep(1.2)
            if i % 25 == 0:
                print("  {}/{} · 成功 {} · {:.0f}s".format(i, min(len(todo), args.limit),
                                                           ok, time.time() - t0))
        print("翻译完成：成功 {} · 失败 {}".format(ok, fail))
        os.makedirs(os.path.dirname(TRANSLATIONS), exist_ok=True)
        json.dump(trans, open(TRANSLATIONS, "w", encoding="utf-8"),
                  ensure_ascii=False, indent=0)

    for r in rows:
        if not site_build.has_cjk(r["text"]):
            r["zh"] = trans.get(r["id"])

    items = site_build.build_items(rows, days=args.days, max_items=args.max_items)
    payload = site_build.build_payload(items, last_sync=int(time.time()), total_all=len(rows))
    html = site_build.render(payload)
    os.makedirs(os.path.dirname(args.out), exist_ok=True)
    open(args.out, "w", encoding="utf-8").write(html)
    print("页面已生成 {}（{:.0f} KB · {} 条 · {} 信源 · 中文可读 {}）".format(
        args.out, os.path.getsize(args.out) / 1024, len(items),
        len(payload["accounts"]), payload["view"]["cn"]))


if __name__ == "__main__":
    main()
