#!/usr/bin/env python3
"""vgreq.py — PURE Python requests Voyager client (NO browser).
Uses fresh cookies from /tmp/li_cookies.json (extracted from the logged-in session).

Provides get/post/delete with correct LinkedIn Voyager headers + csrf-token.
"""
import json, requests, os

COOKIE_FILE = os.environ.get("VG_COOKIES", "/tmp/li_cookies.json")

def _load():
    li = json.load(open(COOKIE_FILE))
    csrf = li["JSESSIONID"].strip('"')
    cookie_str = "; ".join(f"{k}={v}" for k, v in li.items())
    return csrf, cookie_str

UA = ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/150.0.0.0 Safari/537.36")

def _headers(extra=None):
    csrf, cookie_str = _load()
    h = {
        "csrf-token": csrf,
        "x-restli-protocol-version": "2.0.0",
        "accept": "application/vnd.linkedin.normalized+json+2.1",
        "x-li-lang": "de_DE",
        "x-li-track": ('{"clientVersion":"1.13.45173","mpVersion":"1.13.45173",'
                       '"osName":"web","timezoneOffset":2,"timezone":"Europe/Berlin",'
                       '"deviceFormFactor":"DESKTOP","mpName":"voyager-web",'
                       '"displayDensity":1,"displayWidth":1440,"displayHeight":900}'),
        "user-agent": UA,
        "cookie": cookie_str,
        "referer": "https://www.linkedin.com/feed/",
        "origin": "https://www.linkedin.com",
    }
    if extra:
        h.update(extra)
    return h

def get(url, extra_headers=None):
    return requests.get(url, headers=_headers(extra_headers), allow_redirects=False, timeout=25)

def post(url, body=None, extra_headers=None, is_json=True):
    h = _headers(extra_headers)
    if is_json and body is not None and not isinstance(body, (str, bytes)):
        body = json.dumps(body)
    if body is not None:
        h["content-type"] = "application/json; charset=UTF-8"
    return requests.post(url, headers=h, data=body, allow_redirects=False, timeout=25)

def delete(url, extra_headers=None):
    return requests.delete(url, headers=_headers(extra_headers), allow_redirects=False, timeout=25)

if __name__ == "__main__":
    # Self-test: /me should return 200
    r = get("https://www.linkedin.com/voyager/api/me")
    print("Self-test /me:", r.status_code, "len", len(r.text))
