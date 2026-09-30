"""買取店サイトへのアクセス。

店舗ごとに1つ作って使う。同じ店舗への連続アクセスは間隔を空け、
一時的なエラーのときだけ数回やり直す。
"""
import time

import requests

USER_AGENT = "Mozilla/5.0 (compatible; KaitoriRadar/0.1)"
TIMEOUT = 30      # 秒
INTERVAL = 2.0    # 同じ店舗へのアクセス間隔（秒）
RETRIES = 2


class Http:
    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update({
            "User-Agent": USER_AGENT,
            "Accept-Language": "ja,en;q=0.8",
        })
        self._last = 0.0

    def get(self, url, **kwargs):
        return self.request("GET", url, **kwargs)

    def post(self, url, **kwargs):
        return self.request("POST", url, **kwargs)

    def request(self, method, url, **kwargs):
        for attempt in range(RETRIES + 1):
            wait = self._last + INTERVAL - time.monotonic()
            if wait > 0:
                time.sleep(wait)
            try:
                res = self.session.request(method, url, timeout=TIMEOUT, **kwargs)
                res.raise_for_status()
                return res
            except requests.RequestException:
                if attempt == RETRIES:
                    raise
                time.sleep(5 * (attempt + 1))
            finally:
                self._last = time.monotonic()
