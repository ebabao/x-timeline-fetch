# -*- coding: utf-8 -*-
"""页面生成核心：把推文列表渲染成单文件工作台。

同一份逻辑被两处调用，保证本地和云端产出一致：
  1. hub.py build     —— 从本地 SQLite 取数
  2. build_site.py    —— 跑在 GitHub Runner 上，直接读 data/*.json
"""
import re
import os
import json
import datetime

import meta

URL_RE = re.compile(r"https?://\S+")
CJK = re.compile(r"[\u4e00-\u9fff]")

# 轻量主题词表：不调模型，靠关键词命中给每条资讯打标
TOPICS = [
    ("美联储", ["美联储", "联储", "fomc", "powell", "鲍威尔", "rate cut", "降息", "加息"]),
    ("通胀", ["通胀", "cpi", "ppi", "inflation", "物价"]),
    ("美股", ["美股", "标普", "纳斯达克", "道指", "s&p", "nasdaq", "dow", "wall street"]),
    ("A股港股", ["a股", "沪指", "上证", "深成", "港股", "恒生", "北向", "创业板"]),
    ("汇率", ["人民币", "汇率", "美元指数", "离岸", "在岸", "yuan", "currency", "dollar"]),
    ("原油能源", ["原油", "油价", "opec", "天然气", "布伦特", "oil", "gas", "energy"]),
    ("AI科技", ["人工智能", "芯片", "英伟达", "nvidia", "半导体", "算力", "大模型",
               "ai", "chips", "chip", "semiconductor", "openai"]),
    ("财报", ["财报", "营收", "净利", "earnings", "revenue", "guidance", "profit"]),
    ("关税贸易", ["关税", "制裁", "贸易", "出口管制", "tariff", "sanction", "trade war"]),
    ("黄金", ["黄金", "金价", "白银", "gold", "silver"]),
]


def has_cjk(s):
    return bool(CJK.search(s or ""))


def split_links(text):
    """把正文里的长链接剥出来 —— 媒体号爱把整条 URL 塞进正文，留着会撑坏卡片。"""
    urls = URL_RE.findall(text or "")
    body = URL_RE.sub("", text or "")
    body = re.sub(r"[ \t]+\n", "\n", body)
    body = re.sub(r"\n[ \t]*\n[\s]*", "\n", body)
    body = re.sub(r"[ \t]{2,}", " ", body)
    links = []
    for u in urls[:3]:
        u = u.rstrip(").,，。")
        host = re.sub(r"^https?://(www\.)?", "", u).split("/")[0]
        links.append({"u": u, "d": host})
    return body.strip(), links


def topic_of(*texts):
    hay = " ".join([t for t in texts if t])
    if not hay:
        return []
    low = hay.lower()
    out = []
    for name, words in TOPICS:
        for w in words:
            if re.search(r"[a-z]", w):
                # 英文短词必须卡词边界，否则 "ai" 会命中 said / chair / airlines
                if re.search(r"\b" + re.escape(w) + r"\b", low):
                    out.append(name)
                    break
            elif w in hay:
                out.append(name)
                break
    return out


def build_items(rows, days=0, max_items=1000):
    """rows: [{id, handle, ts, text, zh, media, url, like, reply, rt, view, lang}]

    zh 为 None 表示还没译；text 本身是中文时按"中文原生"处理。
    """
    since = 0
    if days:
        since = int(datetime.datetime.now().timestamp()) - days * 86400
    rows = [r for r in rows if (r.get("ts") or 0) >= since]
    rows.sort(key=lambda r: r.get("ts") or 0, reverse=True)
    rows = rows[:max_items]

    items = []
    for r in rows:
        raw = r.get("text") or ""
        native = has_cjk(raw)
        zh_in = raw if native else r.get("zh")
        body_en, links = split_links(raw)
        body_zh = None
        if zh_in:
            body_zh, links_zh = split_links(zh_in)
            links = links or links_zh
            if not body_zh:
                body_zh = zh_in
        items.append({
            "id": str(r.get("id")),
            "h": r.get("handle"),
            "ts": r.get("ts") or 0,
            "zh": body_zh,
            "en": body_en,
            "zh_src": "native" if native else ("bing" if zh_in else ""),
            "lang": r.get("lang") or "",
            "m": r.get("media") or [],
            "u": r.get("url") or "",
            "l": [x["d"] for x in links],
            "ln": links,
            "t": topic_of(body_zh, body_en),
            "lk": r.get("like") or 0,
            "rt": r.get("rt") or 0,
            "rp": r.get("reply") or 0,
            "vw": r.get("view") or 0,
        })
    return items


def build_payload(items, last_sync=None, total_all=None):
    now = int(datetime.datetime.now().timestamp())
    acc_rows = {}
    for i in items:
        a = acc_rows.setdefault(i["h"], {"total": 0, "last_ts": 0})
        a["total"] += 1
        a["last_ts"] = max(a["last_ts"], i["ts"])

    accounts = []
    for h, a in acc_rows.items():
        mm = meta.meta_for(h)
        accounts.append({"handle": mm["handle"], "name": mm["name"],
                         "group": mm["group"], "accent": mm["accent"],
                         "note": mm["note"], "total": a["total"], "last_ts": a["last_ts"]})
    accounts.sort(key=lambda x: (meta.group_order(x["group"]), -x["total"]))

    cn = len([i for i in items if i["zh"]])
    pending = len([i for i in items if i["en"] and not i["zh"]])
    return {
        "generated_at": datetime.datetime.now().astimezone().isoformat(timespec="seconds"),
        "stats": {
            "total": total_all or len(items),
            "today": len([i for i in items if i["ts"] >= now - 86400]),
            "week": len([i for i in items if i["ts"] >= now - 7 * 86400]),
            "cn": cn,
            "pending": pending,
            "accounts": len(accounts),
            "last_sync": last_sync or now,
        },
        "groups": meta.GROUPS,
        "accounts": accounts,
        "items": items,
        "view": {"count": len(items), "cn": cn},
    }


def render(payload, template_path=None):
    template_path = template_path or os.path.join(
        os.path.dirname(os.path.abspath(__file__)), "template.html")
    tpl = open(template_path, encoding="utf-8").read()
    js = json.dumps(payload, ensure_ascii=False, separators=(",", ":"))
    js = js.replace("</", "<\\/")
    html = tpl.replace("__DATA__", js)
    return html.replace("12 SOURCES", "{} SOURCES".format(len(payload["accounts"])))
