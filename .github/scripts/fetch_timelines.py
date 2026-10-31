#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""跑在 GitHub Runner 上的 X 时间线抓取脚本（无需登录、无需 API key）。

三通道降级：
  F. FxTwitter v2 —— https://api.fxtwitter.com/2/profile/<handle>/statuses
     按时间倒序返回最新推文，正文/时间/互动齐全，当前最稳定的 latest 通道。
  A. guest GraphQL —— X 前端那套协议（Nitter / twscrape 同源）
     注意：2026-10 实测 guest 的 UserTweets 多数只返回 profile_best_highlights（历史精选）。
  B. syndication SSR —— https://syndication.twitter.com/srv/timeline-profile/screen-name/<h>
     给 X widget 用的免鉴权接口；GitHub IP 常被 429，仅作最后兜底。

Usage:
    python3 fetch_timelines.py --accounts "SCMPChinese business" --limit 40 --outdir data
"""
import os
import re
import sys
import json
import time
import random
import argparse
import requests

UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36")
BEARER = ("AAAAAAAAAAAAAAAAAAAAANRILgAAAAAAnNwIzUejRCOuH5E6I8xnZz4puTs"
          "%3D1Zv7ttfk8LF81IUq16cHjhLTvJu4FA33AGWWjCpTnA")
GQL = "https://x.com/i/api/graphql"
OP_USER_BY_SCREEN = "Gb-d6r0vxPOADdG62OEBpQ/UserByScreenName"
OP_USER_TWEETS = "SXVCYB8XHSS25nzIljNtZA/UserTweets"
SYND = ("https://syndication.twitter.com/srv/timeline-profile/"
        "screen-name/{handle}")
CJK = re.compile(r"[\u4e00-\u9fff]")

FEATURES = {
    "articles_preview_enabled": False,
    "c9s_tweet_anatomy_moderator_badge_enabled": True,
    "communities_web_enable_tweet_community_results_fetch": True,
    "creator_subscriptions_quote_tweet_preview_enabled": False,
    "creator_subscriptions_tweet_preview_api_enabled": True,
    "freedom_of_speech_not_reach_fetch_enabled": True,
    "graphql_is_translatable_rweb_tweet_is_translatable_enabled": True,
    "longform_notetweets_consumption_enabled": True,
    "longform_notetweets_inline_media_enabled": True,
    "longform_notetweets_rich_text_read_enabled": True,
    "responsive_web_edit_tweet_api_enabled": True,
    "responsive_web_enhance_cards_enabled": False,
    "responsive_web_graphql_exclude_directive_enabled": True,
    "responsive_web_graphql_skip_user_profile_image_extensions_enabled": False,
    "responsive_web_grok_community_note_auto_translation_is_enabled": False,
    "responsive_web_graphql_timeline_navigation_enabled": True,
    "responsive_web_grok_imagine_annotation_enabled": False,
    "responsive_web_media_download_video_enabled": False,
    "responsive_web_profile_redirect_enabled": True,
    "responsive_web_twitter_article_tweet_consumption_enabled": True,
    "rweb_tipjar_consumption_enabled": True,
    "rweb_video_timestamps_enabled": True,
}

NITTER_FALLBACK = ["twiiit.com", "nitter.net", "xcancel.com", "nitter.poast.org"]


def log(msg):
    print(msg, flush=True)


# ------------------------------------------------------------------ 通道 A
class Guest:
    def __init__(self):
        self.s = requests.Session()
        self.s.headers.update({
            "User-Agent": UA,
            "Authorization": "Bearer " + BEARER,
            "Accept-Language": "zh-CN,zh;q=0.9",
            "x-twitter-client-language": "zh-CN",
        })
        if not self._activate():
            raise RuntimeError("guest token 获取失败")

    def _activate(self):
        for attempt in range(3):
            try:
                r = self.s.post("https://api.x.com/1.1/guest/activate.json",
                                timeout=25)
                if r.status_code == 200:
                    self.token = r.json()["guest_token"]
                    self.s.headers["x-guest-token"] = self.token
                    return True
            except Exception as e:
                log("      activate 异常: {}".format(str(e)[:60]))
            time.sleep(2 + attempt * 2)
        return False

    def gql(self, op, variables, retry=True):
        # op 形如 "<queryId>/<OperationName>"，已含操作名，直接拼即可。
        # 之前写成 "{}/{}/{}".format(GQL, op, op.split("/")[1]) 会把操作名重复一遍，
        # 变成 .../<hash>/UserByScreenName/UserByScreenName —— X 返回非 200，
        # 于是 uid() 永远拿到 None，表现为"查不到 uid"。
        url = "{}/{}".format(GQL, op)
        # 注意：不要带 features 参数。2026-10 实测（GitHub Runner 诊断）：
        # 传入一堆已废弃的 feature flag 会让 X 直接拒绝请求；
        # 只带 variables 反而 UserByScreenName / UserTweets 都返回 200。
        params = {"variables": json.dumps(variables, separators=(",", ":"))}
        try:
            r = self.s.get(url, params=params, timeout=30)
        except Exception as e:
            if retry:
                time.sleep(3)
                self._activate()
                return self.gql(op, variables, retry=False)
            return None
        if r.status_code in (401, 403, 429) and retry:
            time.sleep(3)
            self._activate()
            return self.gql(op, variables, retry=False)
        return r

    def uid(self, screen_name):
        r = self.gql(OP_USER_BY_SCREEN,
                     {"screen_name": screen_name, "withSafetyModeUserFields": True})
        if r is None:
            log("      uid 请求无响应")
            return None
        if r.status_code != 200:
            log("      uid HTTP {} : {}".format(r.status_code, r.text[:160]))
            return None
        try:
            result = r.json()["data"]["user"]["result"]
            # rest_id 在顶层；部分响应里只给 base64 的 id，需兜底
            rid = result.get("rest_id")
            if rid:
                return rid
            raw = result.get("id", "")
            if raw.startswith("VXNlcjo"):
                import base64
                return base64.b64decode(raw).decode().split(":")[-1]
            log("      uid 响应缺少 rest_id，键={}".format(list(result.keys())[:12]))
            return None
        except Exception as e:
            log("      uid 解析异常 {} : {}".format(type(e).__name__, r.text[:160]))
            return None

    def tweets(self, uid, count=40, cursor=None):
        v = {"userId": str(uid), "count": count,
             "includePromotedContent": False,
             "withQuickPromoteEligibilityTweetFields": True,
             "withVoice": True, "withV2Timeline": True}
        if cursor:
            v["cursor"] = cursor
        r = self.gql(OP_USER_TWEETS, v)
        if r is None:
            return [], None, "network"
        if r.status_code != 200:
            return [], None, r.status_code
        try:
            result = r.json()["data"]["user"]["result"]
            # X 在 2026 年把 timeline_v2 改名成 timeline，两种都兼容
            tl = result.get("timeline_v2") or result.get("timeline") or {}
            ins = tl["timeline"]["instructions"]
        except Exception:
            return [], None, "structure"
        entries, next_cursor = [], None
        for i in ins:
            for e in i.get("entries", []):
                if e.get("entryId", "").startswith("cursor-bottom"):
                    next_cursor = e.get("content", {}).get("value")
                entries.append(e)
        return entries, next_cursor, None


def simplify_gql(entries):
    out = []
    for e in entries:
        eid = e.get("entryId", "") or ""
        content = e.get("content") or {}
        # entryId 前缀只是辅助判断；新版响应里可能缺 entryId，
        # 所以最终以「有没有 tweet_results」为准
        if eid and not eid.startswith("tweet-"):
            continue
        tw = (content.get("itemContent", {})
              .get("tweet_results", {}).get("result", {}))
        if not tw:
            continue
        if "tweet" in tw:
            tw = tw["tweet"]
        lg = tw.get("legacy", {})
        us = tw.get("core", {}).get("user_results", {}).get("result", {})
        # 新版 X 把 name/screen_name 从 legacy 挪到了 core，两个都读
        ul = us.get("legacy") or {}
        uc = us.get("core") or {}
        text = lg.get("full_text") or lg.get("text") or ""
        note = tw.get("note_tweet", {}).get("note_tweet_results", {}).get("result", {})
        if note.get("text"):
            text = note["text"]
        tid = lg.get("id_str") or tw.get("rest_id")
        screen = ul.get("screen_name") or uc.get("screen_name") or us.get("screen_name")
        name = ul.get("name") or uc.get("name")
        out.append({
            "id": tid, "time": lg.get("created_at"), "user": screen,
            "name": name, "text": text,
            "reply": lg.get("reply_count"), "like": lg.get("favorite_count"),
            "rt": lg.get("retweet_count"),
            "view": (tw.get("views") or {}).get("count"),
            "lang": lg.get("lang"),
            "url": "https://x.com/{}/status/{}".format(screen, tid),
            "src": "guest-gql",
        })
    return [t for t in out if t["id"]]


def channel_gql(handle, limit=40, pages=3):
    g = Guest()
    uid = g.uid(handle)
    if not uid:
        return None, "查不到 uid"
    items, cursor = [], None
    for _ in range(pages):
        entries, cursor, err = g.tweets(uid, 40, cursor)
        if err:
            if items:
                break
            return None, "timeline 失败: {}".format(err)
        items += simplify_gql(entries)
        seen, ded = set(), []
        for t in sorted(items, key=lambda x: str(x["id"]), reverse=True):
            if t["id"] in seen:
                continue
            seen.add(t["id"])
            ded.append(t)
        items = ded
        if len(items) >= limit or not cursor:
            break
        time.sleep(random.uniform(1.0, 2.0))
    return items[:limit], None


# ------------------------------------------------------------------ 通道 B
def parse_synd(html_text, handle):
    m = re.search(r'<script id="__NEXT_DATA__" type="application/json">'
                  r'([\s\S]*?)</script>', html_text)
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
        tw = ((e.get("content") or {}).get("tweet") or {})
        if not isinstance(tw, dict) or not tw:
            continue
        tid = tw.get("id_str") or tw.get("conversation_id_str")
        if not tid or tid in seen:
            continue
        seen.add(tid)
        u = tw.get("user") or {}
        out.append({
            "id": tid, "time": tw.get("created_at"),
            "user": u.get("screen_name") or handle, "name": u.get("name"),
            "text": tw.get("full_text") or tw.get("text") or "",
            "reply": tw.get("reply_count"), "like": tw.get("favorite_count"),
            "rt": tw.get("retweet_count"), "lang": tw.get("lang"),
            "url": "https://x.com/{}/status/{}".format(
                u.get("screen_name") or handle, tid),
            "src": "syndication",
        })
    return [t for t in out if t["text"].strip()]


def channel_synd(handle, limit=40):
    h = {"User-Agent": UA, "Accept": "text/html,application/xhtml+xml,*/*;q=0.8",
         "Accept-Language": "zh-CN,zh;q=0.9",
         "Referer": "https://platform.twitter.com/"}
    try:
        r = requests.get(SYND.format(handle=handle), headers=h, timeout=30)
        if r.status_code != 200 or "__NEXT_DATA__" not in r.text:
            return None, "syndication HTTP {}".format(r.status_code)
        items = parse_synd(r.text, handle)
        if not items:
            return None, "syndication 解析为空"
        items.sort(key=lambda x: str(x["id"]), reverse=True)
        return items[:limit], None
    except Exception as e:
        return None, "syndication 异常: {}".format(str(e)[:70])


# ------------------------------------------------------------------ 通道 FxTwitter v2
def channel_fx2(handle, limit=40):
    """免登录、按时间倒序的最新时间线（当前唯一稳定给出 latest 的通道）。"""
    url = "https://api.fxtwitter.com/2/profile/{}/statuses".format(handle)
    last = ""
    for attempt in range(3):
        try:
            r = requests.get(url, headers={"User-Agent": UA}, timeout=35)
            j = r.json()
            if r.status_code == 200 and j.get("code") == 200 and j.get("results"):
                out = []
                for t in j["results"][:limit]:
                    if t.get("type") not in (None, "status"):
                        continue
                    raw_media = (t.get("media") or {}).get("all", []) if isinstance(t.get("media"), dict) else []
                    out.append({
                        "id": t.get("id"),
                        "time": t.get("created_at"),
                        "user": (t.get("author") or {}).get("screen_name") or handle,
                        "name": (t.get("author") or {}).get("name"),
                        "text": t.get("text") or "",
                        "reply": t.get("replies"),
                        "like": t.get("likes"),
                        "rt": t.get("reposts"),
                        "view": t.get("views"),
                        "lang": t.get("lang"),
                        "media": [m.get("url") for m in raw_media if isinstance(m, dict) and m.get("url")][:4],
                        "url": t.get("url") or "https://x.com/{}/status/{}".format(handle, t.get("id")),
                        "src": "fxtwitter-v2",
                    })
                return out, None
            last = "HTTP {} / code {}".format(r.status_code, j.get("code"))
        except Exception as e:
            last = "{}: {}".format(type(e).__name__, str(e)[:70])
        time.sleep(2 + attempt * 2)
    return None, last


# ------------------------------------------------------------------ 编排
def fetch(handle, limit=40):
    """先 FxTwitter v2 最新时间线，失败再试 guest GraphQL / syndication"""
    try:
        items, err = channel_fx2(handle, limit)
        if items:
            return items, "fxtwitter-v2"
        last = "fxtwitter-v2: {}".format(err)
    except Exception as e:
        last = "fxtwitter-v2: {}: {}".format(type(e).__name__, str(e)[:70])
    try:
        items, err = channel_gql(handle, limit)
        if items:
            return items, "guest-gql"
        last += " | guest-gql: {}".format(err)
    except Exception as e:
        last += " | guest-gql: {}: {}".format(type(e).__name__, str(e)[:70])
    time.sleep(1.5)
    items, err2 = channel_synd(handle, limit)
    if items:
        return items, "syndication"
    return [], "{} | syndication: {}".format(last, err2)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--accounts", default="")
    ap.add_argument("--accounts-file", default="accounts.txt")
    ap.add_argument("--limit", type=int, default=40)
    ap.add_argument("--outdir", default="data")
    args = ap.parse_args()

    accs = [a.strip() for a in args.accounts.split() if a.strip()]
    if not accs and os.path.exists(args.accounts_file):
        accs = []
        for l in open(args.accounts_file, encoding="utf-8"):
            l = l.split("#")[0].strip()
            if l and not l.startswith(";"):
                accs.append(l.split()[0])
    # 去重保序
    seen, ordered = set(), []
    for a in accs:
        if a not in seen:
            seen.add(a)
            ordered.append(a)
    accs = ordered
    if not accs:
        log("没有指定账号")
        return
    os.makedirs(args.outdir, exist_ok=True)

    summary = []
    for h in accs:
        try:
            log("=== @{}".format(h))
            items, src = fetch(h, args.limit)
            if not items:
                log("   失败: {}".format(src))
                summary.append({"handle": h, "ok": False, "src": src,
                                "new": 0, "total": 0, "cn": 0})
                continue
            fp = os.path.join(args.outdir, "{}.json".format(h))
            old = json.load(open(fp, encoding="utf-8")) if os.path.exists(fp) else []
            have = {t["id"] for t in old}
            added = [t for t in items if t["id"] not in have]
            merged = sorted(old + added, key=lambda x: str(x["id"]), reverse=True)
            # 只保留最近 500 条，避免仓库无限膨胀
            merged = merged[:500]
            json.dump(merged, open(fp, "w", encoding="utf-8"),
                      ensure_ascii=False, indent=1)
            cn = len([t for t in merged if CJK.search(t.get("text") or "")])
            cn_new = len([t for t in added if CJK.search(t.get("text") or "")])
            log("   通道 {} | 新增 {} 条（中文 {}），累计 {} 条（中文 {}）".format(
                src, len(added), cn_new, len(merged), cn))
            summary.append({"handle": h, "ok": True, "src": src, "new": len(added),
                            "total": len(merged), "cn": cn, "cn_new": cn_new})
        except Exception as e:
            msg = "{}: {}".format(type(e).__name__, str(e)[:80])
            log("   异常: {}".format(msg))
            summary.append({"handle": h, "ok": False, "src": msg,
                            "new": 0, "total": 0, "cn": 0})
        time.sleep(random.uniform(1.5, 3.0))

    json.dump({"ran_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
               "summary": summary},
              open(os.path.join(args.outdir, "_run_summary.json"), "w",
                   encoding="utf-8"), ensure_ascii=False, indent=1)
    ok = sum(1 for s in summary if s["ok"])
    log("\n完成：{}/{} 个账号成功".format(ok, len(summary)))
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
