# -*- coding: utf-8 -*-
"""英文推文 → 中文：Bing 翻译免密钥通道。

为什么用 Bing 而不是 Google
--------------------------
沙箱网络对 translate.googleapis.com / translate.google.com 直接超时（IP 层封锁），
而 cn.bing.com 可达。Bing 网页翻译器背后就是 `ttranslatev3` 接口：
先用 GET /translator 拿一组 (key, token)，再 POST 文本即可，无需 API Key。
2026-10 实测返回 usedLLM=true，金融术语译得比旧版 NMT 准。

限制
----
* token 有效期约 1 小时，过期返回 205/401，需重新握手。
* 单次请求文本上限约 1000 字符，长推文自动分段后拼接。
* 触发风控会返回 429，退避后换会话重试。
"""
import re
import time
import random
import requests

UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36")
HOSTS = ["https://cn.bing.com", "https://www.bing.com"]
MAX_CHUNK = 900


class BingTranslator:
    def __init__(self, host=HOSTS[0]):
        self.host = host
        self.s = requests.Session()
        self.s.headers.update({
            "User-Agent": UA,
            "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
            "Referer": host + "/translator",
        })
        self.key = None
        self.token = None
        self.ig = None
        self.iid = None
        self.born = 0
        self.count = 0

    # ------------------------------------------------------------ 握手
    def handshake(self):
        r = self.s.get(self.host + "/translator", timeout=25)
        r.raise_for_status()
        html = r.text
        m = re.search(r"params_AbusePreventionHelper\s*=\s*\[([^\]]+)\]", html)
        if not m:
            raise RuntimeError("未找到 AbusePrevention 参数（页面结构可能变更）")
        parts = [p.strip().strip('"') for p in m.group(1).split(",")]
        self.key, self.token = parts[0], parts[1]
        ig = re.search(r'IG:"([^"]+)"', html)
        iid = re.search(r'data-iid="([^"]+)"', html)
        self.ig = ig.group(1) if ig else ""
        self.iid = iid.group(1) if iid else "translator.5023"
        self.born = time.time()
        self.count = 0
        return True

    def _ensure(self):
        # token 1 小时过期；这里 50 分钟主动换，或累计 200 次换
        if not self.token or time.time() - self.born > 3000 or self.count > 200:
            self.handshake()

    # ------------------------------------------------------------ 翻译
    def _post(self, text, to="zh-Hans"):
        url = "{}/ttranslatev3?isVertical=1&&IG={}&IID={}".format(
            self.host, self.ig, self.iid)
        data = {"fromLang": "auto-detect", "to": to, "text": text,
                "token": self.token, "key": self.key}
        r = self.s.post(url, data=data, timeout=30)
        self.count += 1
        if r.status_code == 429:
            raise RuntimeError("RATE_LIMIT")
        if r.status_code in (205, 401, 403):
            raise RuntimeError("TOKEN_EXPIRED")
        r.raise_for_status()
        j = r.json()
        if isinstance(j, dict) and j.get("statusCode"):
            raise RuntimeError("API {}".format(j.get("statusCode")))
        return j[0]["translations"][0]["text"]

    def translate(self, text, retries=3):
        text = (text or "").strip()
        if not text:
            return ""
        chunks = _split(text)
        outs = []
        for ch in chunks:
            outs.append(self._one(ch, retries))
            time.sleep(0.35 + random.random() * 0.25)
        return "".join(outs) if len(outs) > 1 else outs[0]

    def _one(self, text, retries):
        last = None
        for i in range(retries):
            try:
                self._ensure()
                return self._post(text)
            except Exception as e:
                last = e
                msg = str(e)
                if msg in ("TOKEN_EXPIRED", "RATE_LIMIT"):
                    self.token = None
                    time.sleep(2 + i * 2)
                else:
                    time.sleep(1 + i)
        raise RuntimeError("翻译失败: {}".format(str(last)[:80]))


def _split(text):
    """按句号/换行切到 900 字符以内，避免超长被截断"""
    if len(text) <= MAX_CHUNK:
        return [text]
    out, buf = [], ""
    for seg in re.split(r"(?<=[.!?。！？\n])\s*", text):
        if len(buf) + len(seg) > MAX_CHUNK and buf:
            out.append(buf)
            buf = seg
        else:
            buf += ("" if not buf else " ") + seg if not buf.endswith("\n") else seg
    if buf:
        out.append(buf)
    # 仍超长的硬切
    final = []
    for s in out:
        while len(s) > MAX_CHUNK:
            final.append(s[:MAX_CHUNK])
            s = s[MAX_CHUNK:]
        if s:
            final.append(s)
    return final or [text[:MAX_CHUNK]]


if __name__ == "__main__":
    t = BingTranslator()
    print(t.translate("Fed officials signalled one more hike as core inflation cooled to 3.1%."))
