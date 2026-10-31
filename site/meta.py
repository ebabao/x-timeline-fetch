# -*- coding: utf-8 -*-
"""信源元数据：账号分组、显示名、主题色、说明。

分组用于工作台左侧导航；accent 用于卡片左侧竖条与头像底色。
"""

# 分组顺序即工作台展示顺序
GROUPS = [
    {"key": "core", "label": "自选监控", "desc": "你长期盯的 5 个交易/调研号"},
    {"key": "media", "label": "财经媒体", "desc": "南华早报、彭博、路透"},
    {"key": "cn_media", "label": "中文媒体", "desc": "华语财经与时政"},
]

ACCOUNTS = {
    # ── 一、自选监控 ──────────────────────────────────────────
    "cnfinancewatch": {
        "name": "华尔街观察", "group": "core", "accent": "#e8b44a",
        "note": "美股 / 财报快照，偶发中文",
    },
    "fxtrader": {
        "name": "外汇交易员", "group": "core", "accent": "#4ea1ff",
        "note": "宏观数据与人民币汇率，中文为主",
    },
    "dmjk001": {
        "name": "大猫调研", "group": "core", "accent": "#7c6cf0",
        "note": "调研纪要，中英混发",
    },
    "baoshu88": {
        "name": "包叔", "group": "core", "accent": "#f0684a",
        "note": "市场评论，中文为主",
    },
    "CrushTheShorts": {
        "name": "建材批发鱼哥", "group": "core", "accent": "#3fc98a",
        "note": "美股做空视角，中文",
    },
    # ── 二、财经媒体 ──────────────────────────────────────────
    "SCMPNews": {
        "name": "南华早报", "group": "media", "accent": "#d94f5c",
        "note": "南华早报英文主号 · 103.8 万粉",
    },
    "SCMPChinese": {
        "name": "南早中文網", "group": "media", "accent": "#a8535c",
        "note": "2016-09 后停更，保留作历史存档",
    },
    "business": {
        "name": "彭博", "group": "media", "accent": "#5b8def",
        "note": "彭博主号 · 1048 万粉 · 无独立中文号",
    },
    "ReutersChina": {
        "name": "路透中文", "group": "media", "accent": "#e07b39",
        "note": "路透中文",
    },
    # ── 三、中文媒体 ──────────────────────────────────────────
    "nytchinese": {
        "name": "纽约时报中文网", "group": "cn_media", "accent": "#9aa4b2",
        "note": "中文深度报道",
    },
    "bbcchinese": {
        "name": "BBC 中文", "group": "cn_media", "accent": "#c0392b",
        "note": "中文快讯",
    },
    "RFI_Cn": {
        "name": "RFI 华语", "group": "cn_media", "accent": "#2e9e8f",
        "note": "法国国际广播电台中文",
    },
}

DEFAULT_ACCENT = "#6b7688"


def meta_for(handle):
    m = ACCOUNTS.get(handle) or {}
    return {
        "handle": handle,
        "name": m.get("name") or handle,
        "group": m.get("group") or "media",
        "accent": m.get("accent") or DEFAULT_ACCENT,
        "note": m.get("note") or "",
    }


def group_order(key):
    for i, g in enumerate(GROUPS):
        if g["key"] == key:
            return i
    return len(GROUPS)
