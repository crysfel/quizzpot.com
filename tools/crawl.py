#!/usr/bin/env python3
"""Crawl the public pages of quizzpot.com into a static site (clean URLs).

    python3 -I tools/crawl.py [--out raw] [--max 3000]

Writes raw (unmodified-content) pages to OUT, with links rewritten to the static
layout:  /a/b -> a/b/index.html,  /blog?page=N -> blog/page/N/index.html.
Assets (/assets, images, fonts referenced from CSS) are saved at their own path.
Log of every URL: OUT/../crawl-log.tsv
"""
import argparse, html, re, sys, time, urllib.error, urllib.parse, urllib.request
from pathlib import Path

ORIGIN = "https://quizzpot.com"
HOSTS = {"quizzpot.com", "www.quizzpot.com"}
# Not public / not static-able (sign-in walls), or decided to leave out (forum: other people's posts).
SKIP = ("/forum", "/members", "/subscribe", "/signin", "/signup", "/signout", "/sign_", "/users", "/user/", "/password",
        "/admin", "/contact", "/quiz", "/auth", "/session", "/profile", "/account", "/notifications")
UA = "static-archiver/1.0 (site owner)"
ASSET_EXT = re.compile(r"\.(css|js|png|jpe?g|gif|svg|ico|webp|woff2?|ttf|eot|otf|mp4|pdf|zip)$", re.I)

ap = argparse.ArgumentParser()
ap.add_argument("--out", default="raw")
ap.add_argument("--max", type=int, default=3000)
ap.add_argument("--delay", type=float, default=0.15)
args = ap.parse_args()
OUT = Path(args.out)


def norm(url, base):
    """Return (kind, key) for a same-site URL worth fetching, else None. key = path[?page=N]"""
    u = urllib.parse.urlsplit(urllib.parse.urljoin(base, html.unescape(url.strip())))
    if u.scheme not in ("http", "https") or u.hostname not in HOSTS:
        return None
    path = urllib.parse.unquote(u.path) or "/"
    if path != "/" and path.endswith("/"):
        path = path.rstrip("/")
    if path.startswith(SKIP) or path.endswith(("/download_video", "/download_code")):
        return ("skip", path)
    if ASSET_EXT.search(path):
        return ("asset", path)
    q = urllib.parse.parse_qs(u.query)
    if u.query:
        if path in ("/blog", "/courses") and list(q) == ["page"] and q["page"][0].isdigit():
            n = int(q["page"][0])
            return ("page", path if n == 1 else f"{path}?page={n}")
        return ("skip", f"{path}?{u.query}")
    return ("page", path)


def local_path(key):
    if "?page=" in key:
        p, n = key.split("?page=")
        return f"{p.lstrip('/')}/page/{n}/index.html"
    if ASSET_EXT.search(key):
        return key.lstrip("/")
    return (key.strip("/") + "/index.html").lstrip("/")


def static_url(key):
    if "?page=" in key:
        p, n = key.split("?page=")
        return f"{p}/page/{n}/"
    if ASSET_EXT.search(key):
        return urllib.parse.quote(key)
    return urllib.parse.quote(key if key == "/" else key + "/")


def fetch(key):
    req = urllib.request.Request(ORIGIN + urllib.parse.quote(key, safe="/?=&"), headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=30) as r:
        return r.status, r.headers.get_content_type(), r.read(), r.geturl()


ATTR = re.compile(r'''(\s(?:href|src|data-src|poster)\s*=\s*)(["'])(.*?)\2''', re.I | re.S)
SRCSET = re.compile(r'''(\ssrcset\s*=\s*)(["'])(.*?)\2''', re.I | re.S)
CSSURL = re.compile(r'''url\(\s*(['"]?)([^'")]+)\1\s*\)''', re.I)

queue, seen, log = ["/", "/courses", "/blog"], set(), []
pages = 0
while queue and pages < args.max:
    key = queue.pop(0)
    if key in seen:
        continue
    seen.add(key)
    try:
        status, ctype, body, final = fetch(key)
    except urllib.error.HTTPError as e:
        log.append((key, str(e.code), "", "")); continue
    except Exception as e:  # noqa: BLE001
        log.append((key, "ERR", type(e).__name__, "")); continue
    fu = urllib.parse.urlsplit(final)
    if fu.hostname not in HOSTS:
        log.append((key, "offsite-redirect", final, "")); continue
    dest = OUT / local_path(key)
    dest.parent.mkdir(parents=True, exist_ok=True)
    base = ORIGIN + key.split("?")[0]

    def found(u):
        n = norm(u, base)
        if not n:
            return None
        kind, k = n
        if kind == "skip":
            log.append((k, "skipped", "", key)) if k not in seen else None
            seen.add(k)
            return None
        if k not in seen:
            queue.append(k)
        return k

    if ctype == "text/html":
        pages += 1
        text = body.decode("utf-8", "replace")

        def sub_attr(m):
            k = found(m.group(3)) if not m.group(3).startswith(("#", "mailto:", "javascript:", "tel:")) else None
            return m.group(1) + m.group(2) + (static_url(k) if k else m.group(3)) + m.group(2)

        def sub_srcset(m):
            parts = []
            for item in m.group(3).split(","):
                bits = item.strip().split()
                if bits:
                    k = found(bits[0]); bits[0] = static_url(k) if k else bits[0]
                parts.append(" ".join(bits))
            return m.group(1) + m.group(2) + ", ".join(parts) + m.group(2)

        text = ATTR.sub(sub_attr, text)
        text = SRCSET.sub(sub_srcset, text)
        text = CSSURL.sub(lambda m: f"url({m.group(1)}{static_url(k) if (k := found(m.group(2))) else m.group(2)}{m.group(1)})", text)
        dest.write_text(text, "utf-8")
    elif ctype == "text/css":
        text = body.decode("utf-8", "replace")
        text = CSSURL.sub(lambda m: f"url({m.group(1)}{static_url(k) if (k := found(m.group(2))) else m.group(2)}{m.group(1)})"
                          if not m.group(2).startswith("data:") else m.group(0), text)
        dest.write_text(text, "utf-8")
    else:
        dest.write_bytes(body)
    log.append((key, str(status), ctype, str(dest)))
    print(f"{len(seen):5} {status} {key}", file=sys.stderr)
    time.sleep(args.delay)

logf = OUT.parent / "crawl-log.tsv"
logf.write_text("url\tstatus\ttype\tsaved_or_from\n" + "\n".join("\t".join(r) for r in log) + "\n", "utf-8")
print(f"done: {pages} html pages, {len(seen)} urls seen, {len(queue)} still queued; log {logf}", file=sys.stderr)
