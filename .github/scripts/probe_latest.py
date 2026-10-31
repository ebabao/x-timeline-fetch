import json
import time
import datetime
import requests

HANDLE = "SCMPChinese"
BEARER = "AAAAAAAAAAAAAAAAAAAAANRILgAAAAAAnNwIzUejRCOuH5E6I8xnZz4puTs%3D1Zv7ttfk8LF81IUq16cHjhLTvJu4FA33AGWWjCpTnA"
UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"
GQL = "https://x.com/i/api/graphql"
FEATURES = {
    "articles_preview_enabled": True,
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
    "standardized_nudges_misinfo": True,
    "tweet_awards_web_tipping_enabled": False,
    "tweet_with_visibility_results_prefer_gql_limited_actions_policy_enabled": True,
    "tweet_with_visibility_results_prefer_gql_media_interstitial_enabled": False,
    "tweetypie_unmention_optimization_enabled": True,
    "verified_phone_label_enabled": False,
    "view_counts_everywhere_api_enabled": True,
    "responsive_web_grok_analyze_button_fetch_trends_enabled": False,
    "premium_content_api_read_enabled": False,
    "profile_label_improvements_pcf_label_in_post_enabled": False,
    "responsive_web_grok_share_attachment_enabled": False,
    "responsive_web_grok_analyze_post_followups_enabled": False,
    "responsive_web_grok_image_annotation_enabled": False,
    "responsive_web_grok_analysis_button_from_backend": False,
    "responsive_web_grok_analyze_post_from_backend": False,
    "responsive_web_jetfuel_frame": False,
    "rweb_video_screen_enabled": True,
    "responsive_web_grok_show_grok_translated_post": True,
}

s = requests.Session()
s.headers.update({"User-Agent": UA, "Authorization": "Bearer " + BEARER,
                  "x-twitter-active-user": "yes", "x-twitter-client-language": "en"})

def snowflake_date(tid):
    try:
        ms = (int(tid) >> 22) + 1288834974657
        return datetime.datetime.fromtimestamp(ms / 1000, datetime.timezone.utc).strftime("%Y-%m-%d %H:%M")
    except Exception:
        return "?"

def summarize(name, r):
    print("\n###", name)
    print("HTTP", r.status_code, "bytes", len(r.content), flush=True)
    if r.status_code != 200:
        print(r.text[:500])
        return
    try:
        data = r.json()
    except Exception:
        print("non-json", r.text[:300])
        return
    tweets = []
    components = set()
    instruction_types = set()
    def walk(x):
        if isinstance(x, dict):
            if isinstance(x.get("component"), str):
                components.add(x["component"])
            if isinstance(x.get("type"), str) and ("Timeline" in x["type"] or "tweet" in x["type"].lower()):
                instruction_types.add(x["type"])
            legacy = x.get("legacy")
            if isinstance(legacy, dict) and legacy.get("full_text"):
                tid = legacy.get("id_str") or x.get("rest_id")
                tweets.append((str(tid), legacy.get("created_at"), legacy["full_text"][:160]))
            for v in x.values():
                walk(v)
        elif isinstance(x, list):
            for v in x:
                walk(v)
    walk(data)
    print("components:", sorted(components)[:12])
    print("instruction types:", sorted(instruction_types)[:12])
    uniq = {t[0]: t for t in tweets if t[0] and t[0] != "None"}
    ordered = sorted(uniq.values(), key=lambda t: int(t[0]), reverse=True)
    print("tweets:", len(ordered))
    for tid, created, text in ordered[:4]:
        print(" ", tid, snowflake_date(tid), "|", created, "|", text.replace("\n", " / "))
    if ordered:
        open("/tmp/latest_probe_hit.json", "w").write(json.dumps(data, ensure_ascii=False))

def gql(name, op, variables, features=None, field_toggles=None):
    params = {"variables": json.dumps(variables, separators=(",", ":"))}
    if features is not None:
        params["features"] = json.dumps(features, separators=(",", ":"))
    if field_toggles is not None:
        params["fieldToggles"] = json.dumps(field_toggles, separators=(",", ":"))
    try:
        r = s.get(GQL + "/" + op, params=params, timeout=35)
        summarize(name, r)
        return r
    except Exception as e:
        print("\n###", name, "ERROR", repr(e), flush=True)

print("=== guest token ===", flush=True)
r = s.post("https://api.x.com/1.1/guest/activate.json", timeout=30)
print(r.status_code, r.text[:160], flush=True)
if r.status_code != 200:
    raise SystemExit(1)
s.headers["x-guest-token"] = r.json()["guest_token"]

uid = "2643944580"
r = gql("new UserByScreenName", "AMIBMjtxEEATh4z8V9GtRg/UserByScreenName",
        {"screen_name": HANDLE, "withSafetyModeUserFields": True}, FEATURES)
if r is not None and r.status_code == 200:
    try:
        uid = r.json()["data"]["user"]["result"]["rest_id"]
    except Exception:
        pass
print("uid =", uid, flush=True)

v = {"userId": uid, "count": 20, "includePromotedContent": False,
     "withQuickPromoteEligibilityTweetFields": True, "withVoice": True, "withV2Timeline": True}
gql("NEW UserTweets + latest features", "OdBLACRZ0-9NikpJotaT7g/UserTweets", v, FEATURES)
gql("NEW UserTweets no features", "OdBLACRZ0-9NikpJotaT7g/UserTweets", v)
v2 = dict(v, withCommunity=True)
gql("NEW UserTweetsAndReplies + latest features", "M9Tz6NGTHeRzqHOPdj9I7g/UserTweetsAndReplies", v2, FEATURES)
gql("NEW SearchTimeline Latest", "BYppgupFFS2yqVmmRNjlsw/SearchTimeline",
    {"rawQuery": "from:" + HANDLE, "count": 20, "product": "Latest", "querySource": "typed_query"},
    FEATURES, {"withArticleRichContentState": False})

legacy_urls = [
    ("legacy profile timeline", "https://x.com/i/api/2/timeline/profile/%s.json" % uid,
     {"count": 20, "include_replies": "false", "include_rts": "true"}),
    ("legacy adaptive search", "https://x.com/i/api/2/search/adaptive.json",
     {"q": "from:" + HANDLE, "count": 20, "tweet_search_mode": "live"}),
    ("legacy user_timeline", "https://x.com/i/api/1.1/statuses/user_timeline.json",
     {"user_id": uid, "count": 20, "tweet_mode": "extended"}),
]
for name, url, params in legacy_urls:
    try:
        r = s.get(url, params=params, timeout=30)
        summarize(name, r)
    except Exception as e:
        print("\n###", name, "ERROR", repr(e), flush=True)

print("\n=== full syndication widget URL ===", flush=True)
synd_params = {
    "dnt": "true", "embedId": "twitter-widget-0", "frame": "false",
    "hideBorder": "false", "hideFooter": "false", "hideHeader": "false",
    "hideScrollBar": "false", "lang": "en", "maxHeight": "600px",
    "origin": "https://platform.twitter.com", "sessionId": "0" * 32,
    "showHeader": "true", "showReplies": "false", "transparent": "false",
    "widgetsVersion": "26155f7e52b7e0:1702314776716",
}
try:
    r = requests.get("https://syndication.twitter.com/srv/timeline-profile/screen-name/" + HANDLE,
                     params=synd_params, headers={"User-Agent": UA, "Referer": "https://platform.twitter.com/"}, timeout=35)
    print("HTTP", r.status_code, "bytes", len(r.content), r.text[:300])
    if r.status_code == 200:
        open("/tmp/syndication_latest.html", "w").write(r.text)
except Exception as e:
    print("ERROR", repr(e))
print("\n=== probe latest done ===", flush=True)
