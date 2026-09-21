#!/usr/bin/env python3
"""
Auto-repost for Instagram + X, with the Instagram feed as the single source.

Every 4 hours (GitHub Actions cron) it takes the next old post from the IG
backlog (everything posted before CUTOFF, newest first) and:
  - re-publishes it to Instagram as a new post
  - cross-posts the same item to X as a brand-new tweet (caption as text,
    media downloaded from Instagram and re-uploaded)

The backlog build saves its progress after every page, so if a run is ever
canceled or times out mid-build, the next run resumes where it left off.
Progress lives in state.json; both files are committed back by the workflow.
"""

import json
import os
import shutil
import tempfile
import time
from datetime import datetime, timezone
from pathlib import Path

import requests
from requests_oauthlib import OAuth1Session

# ----------------------------------------------------------------- settings

CUTOFF = datetime(2025, 8, 1, tzinfo=timezone.utc)  # repost posts strictly OLDER
# than this moment. Aug 1 2025 = "July 2025 and earlier".

MAX_TRIES = 3             # skip an item after this many consecutive failures
TWEET_MAX = 280           # X text limit; longer captions get truncated
X_STRIP_HASHTAGS = False  # True = remove #hashtags from the X version only

STATE_FILE = Path("state.json")
IG_QUEUE_FILE = Path("ig_queue.json")

GRAPH = "https://graph.facebook.com/v26.0"
UPLOAD_URL = "https://upload.x.com/2/media/upload"  # if uploads 404, switch to
# "https://api.x.com/2/media/upload"
TWEET_URL = "https://api.x.com/2/tweets"

# ----------------------------------------------------------------- clients

IG_TOKEN = os.environ.get("IG_TOKEN", "")
IG_USER_ID = os.environ.get("IG_USER_ID", "")

_x = [os.environ.get(k, "") for k in
      ("X_API_KEY", "X_API_SECRET", "X_ACCESS_TOKEN", "X_ACCESS_TOKEN_SECRET")]
X = OAuth1Session(*_x) if all(_x) else None

S = requests.Session()     # reused connections - makes backlog paging much faster
S.headers.update({"User-Agent": "Mozilla/5.0 (repost-bot)"})


# ----------------------------------------------------------------- helpers

def load_json(path, default):
    try:
        return json.loads(Path(path).read_text(encoding="utf-8"))
    except FileNotFoundError:
        return default


def save_json(path, obj):
    Path(path).write_text(json.dumps(obj, indent=1, ensure_ascii=False),
                          encoding="utf-8")


# ------------------------------------------------- backlog (Instagram feed)

def ig_queue():
    """
    All IG feed posts older than CUTOFF, newest first.

    Checkpoints to ig_queue.json after every page: if this run dies partway
    (timeout/cancel), the next run resumes from the saved cursor. Only the
    opaque pagination cursor is saved - never the token.
    """
    cache = load_json(IG_QUEUE_FILE, None)
    if isinstance(cache, dict) and cache.get("done"):
        return cache["items"]

    items = cache.get("items", []) if isinstance(cache, dict) else []
    after = cache.get("after") if isinstance(cache, dict) else None
    pages = cache.get("pages", 0) if isinstance(cache, dict) else 0
    limit = 25      # auto-shrinks if IG rejects the page size

    if pages:
        print(f"resuming backlog build from page {pages + 1} "
              f"({len(items)} old posts collected so far)")

    while True:
        params = {"fields": "id,timestamp", "limit": limit,
                  "access_token": IG_TOKEN}
        if after:
            params["after"] = after
        r = S.get(f"{GRAPH}/{IG_USER_ID}/media", params=params,
                  timeout=30).json()
        if "error" in r:
            msg = r["error"].get("message", "")
            if "reduce the amount of data" in msg.lower() and limit > 5:
                limit = 10 if limit > 10 else 5
                print(f"page too large for IG - retrying with limit {limit}")
                continue
            raise RuntimeError("IG list error: " + msg)

        for p in r.get("data", []):
            ts = datetime.strptime(p["timestamp"], "%Y-%m-%dT%H:%M:%S%z")
            if ts < CUTOFF:
                items.append({"id": p["id"], "ts": p["timestamp"]})

        after = r.get("paging", {}).get("cursors", {}).get("after")
        if not r.get("data"):
            after = None                        # empty page = end of feed
        pages += 1
        if pages % 5 == 0 or not after:
            print(f"backlog build: {pages} pages read, "
                  f"{len(items)} old posts so far")

        save_json(IG_QUEUE_FILE, {"done": not after, "after": after,
                                  "pages": pages, "items": items})
        if not after:
            items.sort(key=lambda i: i["ts"], reverse=True)
            save_json(IG_QUEUE_FILE, {"done": True, "after": None,
                                      "pages": pages, "items": items})
            return items


def fetch_post(item_id):
    """Fresh details for one IG post (CDN media URLs are short-lived)."""
    r = S.get(f"{GRAPH}/{item_id}", params={
        "fields": "caption,media_type,media_url,children{media_type,media_url}",
        "access_token": IG_TOKEN}, timeout=30).json()
    if "error" in r:
        raise RuntimeError("IG fetch error: " + r["error"].get("message", ""))
    return r


# ---------------------------------------------------- repost to Instagram

def ig_publish(post):
    """Re-publish one IG post as a new post. True on success."""
    caption = post.get("caption") or ""

    def container(payload):
        c = S.post(f"{GRAPH}/{IG_USER_ID}/media", data=payload,
                   timeout=120).json()
        if "error" in c:
            raise RuntimeError("IG container error: " + c["error"].get("message", ""))
        return c["id"]

    def child(c):
        d = {"is_carousel_item": "true", "access_token": IG_TOKEN}
        if c["media_type"] == "VIDEO":
            d |= {"media_type": "VIDEO", "video_url": c["media_url"]}
        else:
            d["image_url"] = c["media_url"]
        return container(d)

    if post["media_type"] == "CAROUSEL":
        kids = [child(c) for c in post.get("children", {}).get("data", [])]
        cid = container({"media_type": "CAROUSEL", "children": ",".join(kids),
                         "caption": caption, "access_token": IG_TOKEN})
    elif post["media_type"] == "VIDEO":
        try:    # try as a Reel first, plain video post as fallback
            cid = container({"media_type": "REELS", "video_url": post["media_url"],
                             "caption": caption, "access_token": IG_TOKEN})
        except RuntimeError as e:
            print(e)
            cid = container({"media_type": "VIDEO", "video_url": post["media_url"],
                             "caption": caption, "access_token": IG_TOKEN})
    else:
        cid = container({"image_url": post["media_url"], "caption": caption,
                         "access_token": IG_TOKEN})

    for _ in range(60):                     # wait for processing (videos)
        s = S.get(f"{GRAPH}/{cid}", params={"fields": "status_code",
                 "access_token": IG_TOKEN}, timeout=30).json()
        if s.get("status_code") == "FINISHED":
            break
        if s.get("status_code") == "ERROR":
            print("IG processing error")
            return False
        time.sleep(5)

    p = S.post(f"{GRAPH}/{IG_USER_ID}/media_publish",
               data={"creation_id": cid, "access_token": IG_TOKEN},
               timeout=30).json()
    if "error" in p:
        print("IG publish error:", p["error"].get("message"))
        return False
    print("IG posted:", p["id"])
    return True


# ---------------------------------------------------- cross-post to X

def download_media(url, dest_dir):
    """Download an IG CDN file. Returns local path or None."""
    base = url.split("?")[0].split("/")[-1] or "media"
    path = Path(dest_dir) / base
    with S.get(url, stream=True, timeout=180) as r:
        if not r.ok:
            print(f"download failed {r.status_code}: {url[:100]}")
            return None
        ctype = r.headers.get("Content-Type", "")
        if "video" in ctype and path.suffix.lower() not in (".mp4", ".mov"):
            path = path.with_suffix(".mp4")
        elif "image" in ctype and path.suffix.lower() not in (".jpg", ".jpeg",
                                                              ".png", ".webp"):
            path = path.with_suffix(".jpg")
        with open(path, "wb") as f:
            for chunk in r.iter_content(1024 * 1024):
                f.write(chunk)
    return str(path)


def media_id(response):
    if not response.ok:
        print(f"X upload error {response.status_code}: {response.text[:200]}")
        return None
    body = response.json() if response.text.strip() else {}
    return (body.get("data") or {}).get("id") or body.get("media_id_string")


def upload_simple(path):
    with open(path, "rb") as f:
        r = X.post(UPLOAD_URL, data={"media_category": "tweet_image"},
                   files={"media": f}, timeout=300)
    return media_id(r)


def upload_chunked(path, media_type, category):
    init = {"command": "INIT", "media_type": media_type,
            "media_category": category, "total_bytes": os.path.getsize(path)}
    r = X.post(UPLOAD_URL, json=init, timeout=300)
    if not r.ok:
        r = X.post(UPLOAD_URL, data=init, timeout=300)
    mid = media_id(r)
    if not mid:
        return None
    with open(path, "rb") as f:
        for seg, chunk in enumerate(iter(lambda: f.read(4 * 1024 * 1024), b"")):
            r = X.post(UPLOAD_URL,
                       data={"command": "APPEND", "media_id": mid,
                             "segment_index": seg},
                       files={"media": ("chunk", chunk)}, timeout=300)
            if not r.ok:
                print(f"X append error {r.status_code}: {r.text[:200]}")
                return None
    fin = {"command": "FINALIZE", "media_id": mid}
    r = X.post(UPLOAD_URL, json=fin, timeout=300)
    if not r.ok:
        r = X.post(UPLOAD_URL, data=fin, timeout=300)
    if not r.ok:
        print(f"X finalize error {r.status_code}: {r.text[:200]}")
        return None
    body = r.json() if r.text.strip() else {}
    info = (body.get("data") or {}).get("processing_info") or body.get("processing_info")
    while info and info.get("state") not in ("succeeded", "FINISHED"):
        if info.get("state") in ("failed", "ERROR"):
            print("X media processing failed")
            return None
        time.sleep(min(info.get("check_after_secs", 5), 30))
        r = X.get(UPLOAD_URL, params={"command": "STATUS", "media_id": mid},
                  timeout=30)
        body = r.json() if r.text.strip() else {}
        info = ((body.get("data") or {}).get("processing_info")
                or body.get("processing_info"))
    return mid


def upload(path):
    ext = Path(path).suffix.lower()
    if ext in (".mp4", ".mov"):
        return upload_chunked(path, "video/mp4" if ext == ".mp4" else "video/quicktime",
                              "tweet_video")
    if os.path.getsize(path) > 5 * 1024 * 1024:     # big image: chunked upload
        return upload_chunked(path, "image/jpeg", "tweet_image")
    return upload_simple(path)


def x_post(post):
    """Cross-post one IG item to X as a new tweet. True on success."""
    tmp = tempfile.mkdtemp()
    try:
        # X allows one video OR up to four photos per tweet
        if post["media_type"] == "CAROUSEL":
            kids = post.get("children", {}).get("data", [])
            vids = [c for c in kids if c["media_type"] == "VIDEO"]
            picks = vids[:1] if vids else [c for c in kids
                                            if c["media_type"] != "VIDEO"][:4]
        elif post["media_type"] == "VIDEO":
            picks = [post]
        else:
            picks = [post]

        ids = []
        for m in picks:
            f = download_media(m["media_url"], tmp)
            if f:
                mid = upload(f)
                if mid:
                    ids.append(mid)

        text = post.get("caption") or ""
        if X_STRIP_HASHTAGS:
            text = " ".join(w for w in text.split() if not w.startswith("#"))
        payload = {}
        if text:
            payload["text"] = text[:TWEET_MAX]
        if ids:
            payload["media"] = {"media_ids": ids}
        if not payload:
            print("X item has no caption and no usable media - skipping")
            return False
        r = X.post(TWEET_URL, json=payload, timeout=60)
        if r.ok:
            print("X posted:", r.json()["data"]["id"])
            return True
        print(f"X post error {r.status_code}: {r.text[:300]}")
        return False
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


# -------------------------------------------------------------------- main

def run_platform(name, state, idx_key, fail_key, queue, post_fn):
    """Post the next queue item; remember progress; skip after MAX_TRIES fails."""
    idx, fails = state.get(idx_key, 0), state.get(fail_key, 0)
    print(f"{name} backlog: {len(queue)} items, next: #{idx + 1}")
    if idx >= len(queue):
        print(f"{name}: backlog exhausted")
        return
    try:
        ok = post_fn(queue[idx])
    except Exception as e:                  # never let one platform kill the run
        print(f"{name} error: {e}")
        ok = False
    if ok:
        state[idx_key] = idx + 1
        state[fail_key] = 0
    else:
        state[fail_key] = fails + 1
        if state[fail_key] >= MAX_TRIES:
            print(f"{name}: giving up on item #{idx + 1}, skipping it")
            state[idx_key] = idx + 1
            state[fail_key] = 0
    save_json(STATE_FILE, state)


def main():
    if not (IG_TOKEN and IG_USER_ID):
        print("IG credentials missing - cannot build the backlog, nothing to do")
        return

    state = load_json(STATE_FILE, {"x": 0, "ig": 0, "x_fail": 0, "ig_fail": 0})
    cache = load_json(IG_QUEUE_FILE, None)
    if isinstance(cache, list:               # old-format cache
        igq = cache
    elif isinstance(cache, dict) and cache.get("done"):
        igq = cache["items"]
    else:
        try:
            igq = ig_queue()
            print(f"IG backlog built: {len(igq)} items")
        except Exception as e:
            print("IG backlog build interrupted, will resume next run:", e)
            return

    if X:
        run_platform("X", state, "x", "x_fail", igq,
                     lambda item: x_post(fetch_post(item["id"])))
    else:
        print("X credentials not set - skipping X")

    run_platform("IG", state, "ig", "ig_fail", igq,
                 lambda item: ig_publish(fetch_post(item["id"])))


if __name__ == "__main__":
    main()
