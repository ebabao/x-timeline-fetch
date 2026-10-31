# -*- coding: utf-8 -*-
"""英文推文 → 中文：双通道自动选路。

为什么需要两个通道
------------------
* 本地沙箱：translate.googleapis.com 被 IP 封锁（TLS 握手超时），但 cn.bing.com 可达。
* GitHub Runner：Bing 的 /translator 页面在 Azure 数据中心 IP 上被风控（返回 HTML 而非 JSON），
  而 Google 的 gtx 端点完全正常。

所以启动时探一次路：哪个通道能翻出东西就用哪个，运行中失败就切另一个。
调用方只用 translate()，不用关心底下是谁。
"""
import re
import time
import random
import requests

UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36")
BING_HOSTS = ["https://cn.bing.com", "https://www.bing.com"]
GOOGLE = "https://translate.googleapis.com/translate_a/single"
CHUNK = 900


def _split(text):
    """按句末标点切到 CHUNK 以内，避免超长被截断"""
    if len(text) <= CHUNK:
        return [text]
    out, buf = [], ""
    for seg in re.split(r"(?<=[.!?。！？\n])\s*", text):
        if len(buf) + len(seg) > CHUNK and buf:
            out.append(buf)
            buf = seg
        else:
            buf = (buf + " " + seg) if buf else seg
    if buf:
        out.append(buf)
    final = []
    for s in out:
        while len(s) > CHUNK:
            final.append(s[:CHUNK])
            s = s[CHUNK:]
        if s:
            final.append(s)
    return final or [text[:CHUNK]]


class BingTranslator:
    """对外只暴露 translate()；类名沿用历史调用方。"""

    def __init__(self, engine=None):
        self.engine = engine
        self.s = requests.Session()
        self.s.headers.update({"User-Agent": UA,
                               "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8"})
        self._b = {"host": BING_HOSTS[0], "key": None, "token": None,
                   "ig": None, "iid": None, "born": 0, "n": 0}
        self.fail_streak = 0

    # ---------------------------------------------------------- Google
    def _google(self, text):
        r = self.s.get(GOOGLE, params={"client": "gtx", "sl": "auto", "tl": "zh-CN",
                                       "dt": "t", "q": text}, timeout=8)
        r.raise_for_status()
        j = r.json()
        return "".join(seg[0] for seg in j[0] if seg and seg[0])

    # ---------------------------------------------------------- Bing
    def _bing_handshake(self):
        for host in BING_HOSTS:
            try:
                r = self.s.get(host + "/translator", timeout=20)
                if r.status_code != 200:
                    continue
                m = re.search(r"params_AbusePreventionHelper\s*=\s*\[([^\]]+)\]", r.text)
                if not m:
                    continue
                parts = [p.strip().strip('"') for p in m.group(1).split(",")]
                ig = re.search(r'IG:"([^"]+)"', r.text)
                iid = re.search(r'data-iid="([^"]+)"', r.text)
                self._b.update({"host": host, "key": parts[0], "token": parts[1],
                                "ig": ig.group(1) if ig else "",
                                "iid": iid.group(1) if iid else "translator.5023",
                                "born": time.time(), "n": 0})
                return True
            except Exception:
                continue
        return False

    def _bing(self, text):
        st = self._b
        if not st["token"] or time.time() - st["born"] > 3000 or st["n"] > 150:
            if not self._bing_handshake():
                raise RuntimeError("BING_HANDSHAKE")
        url = "{}/ttranslatev3?isVertical=1&&IG={}&IID={}".format(
            st["host"], st["ig"], st["iid"])
        r = self.s.post(url, data={"fromLang": "auto-detect", "to": "zh-Hans",
                                   "text": text, "token": st["token"], "key": st["key"]},
                        timeout=25)
        st["n"] += 1
        if r.status_code in (205, 401, 403, 429):
            st["token"] = None
            raise RuntimeError("BING_TOKEN")
        r.raise_for_status()
        body = r.text.strip()
        if not body.startswith(("[", "{")):
            # 风控时返回 HTML 验证页，直接 r.json() 会报 Expecting value
            raise RuntimeError("BING_HTML")
        j = r.json()
        if isinstance(j, dict) and j.get("statusCode"):
            raise RuntimeError("BING_API")
        return j[0]["translations"][0]["text"]

    # ---------------------------------------------------------- 选路
    def _probe(self):
        for name, fn in (("google", self._google), ("bing", self._bing)):
            try:
                if fn("market update"):
                    self.engine = name
                    return name
            except Exception:
                continue
        self.engine = "google"
        return "google"

    def translate(self, text, retries=3):
        text = (text or "").strip()
        if not text:
            return ""
        if not self.engine:
            self._probe()
        outs = []
        for ch in _split(text):
            outs.append(self._one(ch, retries))
            time.sleep(0.25 + random.random() * 0.2)
        return "".join(outs) if len(outs) > 1 else outs[0]

    def _one(self, text, retries):
        last = None
        for i in range(retries):
            fn = self._google if self.engine == "google" else self._bing
            try:
                out = fn(text)
                self.fail_streak = 0
                return out
            except Exception as e:
                last = e
                self.fail_streak += 1
                time.sleep(0.8 + i * 0.8)
        # 当前通道彻底不行就换另一个再试一次
        other = "bing" if self.engine == "google" else "google"
        try:
            fn = self._google if other == "google" else self._bing
            out = fn(text)
            self.engine = other
            self.fail_streak = 0
            return out
        except Exception as e:
            last = e
        raise RuntimeError("翻译失败: {}".format(str(last)[:70]))


if __name__ == "__main__":
    t = BingTranslator()
    print(t.translate("Fed officials signalled one more hike as core inflation cooled to 3.1%."))
    print("engine:", t.engine)
