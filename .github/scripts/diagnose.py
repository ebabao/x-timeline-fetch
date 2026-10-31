#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""跑在 GitHub Runner 上：探测 X 当前到底接受什么请求。

目的不是抓数据，而是搞清楚「哪条路现在还能走」：
  1) guest token 能不能拿
  2) 硬编码的 queryId 是否已失效（返回什么错误码/错误体）
  3) 从 x.com 的 JS bundle 里动态提取最新 queryId 是否可行
  4) syndication / fxtwitter / nitter 各通道在 Runner 上的真实状态
"""
import json
import re
import time
import requests

UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36")
BEARER = ("AAAAAAAAAAAAAAAAAAAAANRILgAAAAAAnNwIzUejRCOuH5E6I8xnZz4puTs"
          "%3D1Zv7ttfk8LF81IUq16cHjhLTvJu4FA33AGWWjCpTnA")
HANDLE = "SCMPChinese"
s = requests.Session()
s.headers.update({"User-Agent": UA, "Authorization": "Bearer " + BEARER,
                  "Accept-Language": "zh-CN,zh;q=0.9"})


def show(title, r, limit=700):
    body = (r.text or "")[:limit].replace("\n", " ")
    print("\n### {}\n  status={} len={}\n  body: {}".format(
        title, r.status_code, len(r.text or ""), body), flush=True)


print("=" * 60)
print("1) guest/activate")
print("=" * 60)
token = None
try:
    r = s.post("https://api.x.com/1.1/guest/activate.json", timeout=30)
    show("guest activate", r)
    if r.status_code == 200:
        token = r.json().get("guest_token")
        s.headers["x-guest-token"] = token
        print("  ✓ guest_token = {}".format(token))
except Exception as e:
    print("  异常: {}".format(str(e)[:200]))

if token:
    print("\n" + "=" * 60)
    print("2) 硬编码 queryId 是否失效")
    print("=" * 60)
    for op, name in [("Gb-d6r0vxPOADdG62OEBpQ", "UserByScreenName"),
                     ("SXVCYB8XHSS25nzIljNtZA", "UserTweets")]:
        try:
            url = "https://x.com/i/api/graphql/{}/{}".format(op, name)
            if name == "UserByScreenName":
                v = {"screen_name": HANDLE, "withSafetyModeUserFields": True}
            else:
                v = {"userId": "2643944580", "count": 20,
                     "includePromotedContent": False,
                     "withQuickPromoteEligibilityTweetFields": True,
                     "withVoice": True, "withV2Timeline": True}
            r = s.get(url, params={"variables": json.dumps(v)}, timeout=30)
            show("{} ({})".format(name, op), r, 900)
        except Exception as e:
            print("  {} 异常: {}".format(name, str(e)[:150]))

print("\n" + "=" * 60)
print("3) 从 x.com JS bundle 动态提取最新 queryId")
print("=" * 60)
found_ops = {}
try:
    r = requests.get("https://x.com/{}".format(HANDLE),
                     headers={"User-Agent": UA}, timeout=40)
    print("  x.com/{} -> status={} len={}".format(HANDLE, r.status_code, len(r.text)))
    # 主 JS 入口
    js_urls = set(re.findall(r'https://abs\.twimg\.com/[^"\']+?\.js', r.text))
    print("  首页内发现 JS 入口 {} 个".format(len(js_urls)))
    for u in list(js_urls)[:6]:
        print("    - " + u[:110])
    # 也试试 main.*.js
    if not js_urls:
        js_urls = set(re.findall(r'(https://abs\.twimg\.com/responsive-web/[^"\']+)', r.text))
    for u in list(js_urls)[:8]:
        try:
            jr = requests.get(u, headers={"User-Agent": UA}, timeout=30)
            ops = re.findall(r'queryId:"([A-Za-z0-9_-]{15,30})",operationName:"(\w+)"', jr.text)
            if ops:
                print("  {} -> 提取到 {} 个 operation".format(u[-50:], len(ops)))
                for qid, on in ops:
                    found_ops[on] = qid
        except Exception as e:
            print("  JS 拉取异常: {}".format(str(e)[:80]))
    for k in ["UserByScreenName", "UserTweets", "UserTweetsAndReplies"]:
        print("  ★ {} = {}".format(k, found_ops.get(k, "未找到")))
except Exception as e:
    print("  异常: {}".format(str(e)[:200]))

print("\n" + "=" * 60)
print("4) 动态 queryId 复测（若提取到）")
print("=" * 60)
if token and found_ops.get("UserByScreenName"):
    try:
        url = "https://x.com/i/api/graphql/{}/UserByScreenName".format(
            found_ops["UserByScreenName"])
        v = {"screen_name": HANDLE, "withSafetyModeUserFields": True}
        r = s.get(url, params={"variables": json.dumps(v)}, timeout=30)
        show("UserByScreenName (动态 queryId)", r, 900)
    except Exception as e:
        print("  异常: {}".format(str(e)[:150]))
else:
    print("  跳过（无 token 或未提取到 queryId）")

print("\n" + "=" * 60)
print("5) 其它通道在 Runner 上的状态")
print("=" * 60)
checks = [
    ("syndication", "https://syndication.twitter.com/srv/timeline-profile/screen-name/" + HANDLE),
    ("fxtwitter", "https://api.fxtwitter.com/" + HANDLE),
    ("twiscan", "https://twiscan.com/en/x/" + HANDLE),
    ("nitter twiiit", "https://twiiit.com/" + HANDLE),
    ("nitter.net", "https://nitter.net/" + HANDLE),
]
for name, url in checks:
    try:
        r = requests.get(url, headers={"User-Agent": UA}, timeout=30)
        extra = ""
        if "__NEXT_DATA__" in r.text:
            extra = "含__NEXT_DATA__"
        if "timeline-item" in r.text:
            extra = "含timeline-item x{}".format(r.text.count("timeline-item"))
        print("  {:14s} status={} len={:7d} {}".format(name, r.status_code, len(r.text), extra))
        if name == "fxtwitter" and r.status_code == 200:
            try:
                u = r.json().get("user", {})
                print("       名称={} 粉丝={}".format(u.get("name"), u.get("followers")))
            except Exception:
                pass
    except Exception as e:
        print("  {:14s} 异常 {}".format(name, str(e)[:80]))

print("\n=== 诊断结束 ===")
