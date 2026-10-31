#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""实验：哪种 features 组合能让 UserTweets 返回「真实时间线」而不是「精选推文」。

背景：guest token 调用 UserTweets 时，若缺合适 features，X 返回的
instructions 里 clientEventInfo.component = "profile_best_highlights"，
即算法精选的历史推文（@SCMPChinese 甚至给到 2016 年）。

判定标准：对比返回推文的 snowflake 时间戳，越接近当前时间越好。
"""
import json
import time
import datetime
import requests

UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36")
BEARER = ("AAAAAAAAAAAAAAAAAAAAANRILgAAAAAAnNwIzUejRCOuH5E6I8xnZz4puTs"
          "%3D1Zv7ttfk8LF81IUq16cHjhLTvJu4FA33AGWWjCpTnA")
OP_USER = "Gb-d6r0vxPOADdG62OEBpQ/UserByScreenName"
OP_TWEETS = "SXVCYB8XHSS25nzIljNtZA/UserTweets"
OP_REPLIES = "xOhkmRac04YFZbXJXWjM9w/UserTweetsAndReplies"
GQL = "https://x.com/i/api/graphql"
HANDLE = "SCMPChinese"

# 组 1：无 features（现状）
F_NONE = None

# 组 2：完整（twscrape 2025 版）
F_FULL = {
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
    "responsive_web_graphql_timeline_navigation_enabled": True,
    "responsive_web_media_download_video_enabled": False,
    "responsive_web_twitter_article_tweet_consumption_enabled": True,
    "rweb_tipjar_consumption_enabled": True,
    "rweb_video_timestamps_enabled": True,
    "tweet_awards_web_tipping_enabled": False,
    "view_counts_everywhere_api_enabled": True,
    "unified_cards_ad_metadata_container_dynamic_card_content_query_enabled": False,
    "profile_label_improvements_pcf_label_in_post_enabled": True,
    "premium_content_api_read_enabled": False,
    "responsive_web_grok_analysis_button_from_backend": False,
    "responsive_web_grok_analyze_button_fetch_trends_enabled": False,
    "responsive_web_grok_analyze_post_followups_enabled": False,
    "responsive_web_grok_share_attachment_enabled": False,
}

# 组 3：精简（只留与时间线导航相关的开关）
F_MIN = {
    "responsive_web_graphql_timeline_navigation_enabled": True,
    "responsive_web_graphql_exclude_directive_enabled": True,
    "longform_notetweets_consumption_enabled": True,
    "longform_notetweets_rich_text_read_enabled": True,
    "longform_notetweets_inline_media_enabled": True,
    "rweb_video_timestamps_enabled": True,
    "view_counts_everywhere_api_enabled": True,
    "freedom_of_speech_not_reach_fetch_enabled": True,
    "tweet_awards_web_tipping_enabled": False,
    "responsive_web_edit_tweet_api_enabled": True,
}

# 组 4：在精简基础上加常见必填项（X 新版常要求）
F_MIN2 = dict(F_MIN)
F_MIN2.update({
    "articles_preview_enabled": True,
    "c9s_tweet_anatomy_moderator_badge_enabled": True,
    "creator_subscriptions_tweet_preview_api_enabled": True,
    "graphql_is_translatable_rweb_tweet_is_translatable_enabled": True,
    "responsive_web_enhance_cards_enabled": False,
    "responsive_web_media_download_video_enabled": False,
    "responsive_web_twitter_article_tweet_consumption_enabled": True,
    "rweb_tipjar_consumption_enabled": True,
})


def snow_ts(tid):
    try:
        return datetime.datetime.utcfromtimestamp(
            ((int(tid) >> 22) + 1288834974657) / 1000).strftime("%Y-%m-%d")
    except Exception:
        return "?"


def collect(ins_list):
    """从 instructions 里抽出推文 + 记录 component 标记"""
    tweets, comps = [], set()
    for i in ins_list:
        for e in i.get("entries", []) or []:
            c = e.get("content") or {}
            cei = c.get("clientEventInfo") or {}
            if cei.get("component"):
                comps.add(cei["component"])
            item = c.get("itemContent") or {}
            r = (item.get("tweet_results") or {}).get("result") or {}
            if r.get("__typename") == "TweetWithVisibilityResults":
                r = r.get("tweet", {})
            lg = r.get("legacy") or {}
            tid = lg.get("id_str") or r.get("rest_id")
            if tid:
                tweets.append(tid)
    return tweets, comps


def main():
    s = requests.Session()
    s.headers.update({"User-Agent": UA, "Authorization": "Bearer " + BEARER,
                      "Accept-Language": "zh-CN,zh;q=0.9"})
    r = s.post("https://api.x.com/1.1/guest/activate.json", timeout=30)
    s.headers["x-guest-token"] = r.json()["guest_token"]
    print("guest token OK\n", flush=True)

    r = s.get("{}/{}".format(GQL, OP_USER),
              params={"variables": json.dumps(
                  {"screen_name": HANDLE, "withSafetyModeUserFields": True},
                  separators=(",", ":"))}, timeout=30)
    uid = r.json()["data"]["user"]["result"]["rest_id"]
    print("uid = {}\n".format(uid), flush=True)

    variants = [("无features", F_NONE), ("完整features", F_FULL),
                ("精简features", F_MIN), ("精简+必填", F_MIN2)]
    ops = [("UserTweets", OP_TWEETS), ("UserTweetsAndReplies", OP_REPLIES)]

    for opname, op in ops:
        for label, feats in variants:
            v = {"userId": str(uid), "count": 40,
                 "includePromotedContent": False,
                 "withQuickPromoteEligibilityTweetFields": True,
                 "withVoice": True, "withV2Timeline": True}
            params = {"variables": json.dumps(v, separators=(",", ":"))}
            if feats is not None:
                params["features"] = json.dumps(feats, separators=(",", ":"))
            try:
                rr = s.get("{}/{}".format(GQL, op), params=params, timeout=30)
                if rr.status_code != 200:
                    print("  {:22s} {:12s} HTTP {} {}".format(
                        opname, label, rr.status_code, rr.text[:90]), flush=True)
                    continue
                ins = rr.json()["data"]["user"]["result"]["timeline"]["timeline"]["instructions"]
                tws, comps = collect(ins)
                newest = snow_ts(tws[0]) if tws else "-"
                oldest = snow_ts(tws[-1]) if tws else "-"
                print("  {:22s} {:12s} 条数={:3d} 最新={} 最旧={} 标记={}".format(
                    opname, label, len(tws), newest, oldest, sorted(comps)[:3]),
                    flush=True)
            except Exception as e:
                print("  {:22s} {:12s} 异常 {}".format(opname, label, str(e)[:80]), flush=True)
            time.sleep(1.2)


if __name__ == "__main__":
    main()
