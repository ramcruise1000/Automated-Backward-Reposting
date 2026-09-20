#!/usr/bin/env python3
"""
Auto-repost backlog for X + Instagram. Runs every 4 hours via GitHub Actions.

X:          old tweets re-created as brand-new tweets (media re-uploaded
            from the local X archive in data/tweets_media/).
Instagram:  old feed posts re-published as new posts via the Graph API.

Backlog = everything posted before CUTOFF, replayed newest-first.
Progress lives in state.json (committed back by the workflow).
The Instagram backlog is cached in ig_queue.json (built on first run).
"""

import json
import os
import time
from datetime import datetime, timezone
from pathlib import Path

import requests
from requests_oauthlib import OAuth1Session

# ----------------------------------------------------------------- settings

CUTOFF = datetime(2025, 8, 1, tzinfo=timezone.utc)  # repost posts strictly OLDER
# than this moment. Aug 1 2025 = "July 2025 and earlier". Use
# datetime(2025, 7, 1, tzinfo=timezone.utc) to start from June 2025 instead.

MAX_TRIES = 3          # skip a queue item after this many consecutive failures
TWEET_MAX = 280

MEDIA_DIR = Path("data/tweets_media")
STATE_FILE = Path("state.json")
IG_QUEUE_FILE = Path("ig_queue.json")

GRAPH = "https://graph.facebook.com/v22.0"
UPLOAD_URL = "https://upload.x.com/2/media/upload"  # if uploads 404, switch to
# "https://api.x.com/2/media/upload"
TWEET_URL = "https://api.x.com/2/tweets"

# ----------------------------------------------------------------- clients

IG_TOKEN = os.environ.get("IG_TOKEN", "")
IG_USER_ID = os.environ.get("IG_USER_ID", "")

_x = [os.environ.get(k, "") for k in
      ("X_API_KEY", "X_API_SECRET", "X_ACCESS_TOKEN", "X_ACCESS_TOKEN_SECRET")]
X = OAuth1Session(*_x) if all(_x) else None

_files = None   # cache: archive media filename -> Path


# ----------------------------------------------------------------- helpers

def load_json(path, default):
    try:
        return json.loads(Path(path).read_text(encoding="utf-8"))
    except FileNotFoundError:
        return default


def save_json(path, obj):
    Path(path).write_text(json.dumps(obj, indent=1, ensure_ascii=False),
                          encoding="utf-8")


# ------------------------------------------------------------ X: backlog

def archive_files():
    global _files
    if _files is None:
        _files = ({p.name: p for p in MEDIA_DIR.iterdir() if p.is_file()}
                  if MEDIA_DIR.is_dir() else {})
        if not _files:
            print("WARNING: data/tweets_media/ not found - X posts will be text-only")
    return _files


def match_file(base):
    """Best-effort match of a URL basename to a file in tweets_media/."""
    base = base.split("?")[0]
    files = archive_files()
    if base in files:
        return files[base]
    for name, path in files.items():       # some archive versions prefix tweet IDs
        if name.endswith("-" + base):
            return path
    stem = base.rsplit(".", 1)[0]
    for name, path in files.items():       # extension may differ after re-encoding
        if name.rsplit(".", 1)[0].endswith(stem):
            return path
    return None


def find_media_file(tweet_id, media):
    if media.get("type") == "photo":
        url = media.get("media_url_https") or media.get("media_url", "")
        return match_file(url.split("/")[-1])
    files = archive_files()                # video or animated GIF
    for name in sorted(files):
        if tweet_id in name and Path(name).suffix.lower() in (".mp4", ".mov", ".gif"):
            return files[name]
    variants = sorted(
        (v for v in media.get("video_info", {}).get("variants", [])
         if v.get("content_type") == "video/mp4"),
        key=lambda v: v.get("bitrate", 0), reverse=True)
    for v in variants:
        found = match_file(v["url"].split("/")[-1])
        if found:
            return found
    return None


def x_queue():
    """All own tweets (no retweets, no replies) older than CUTOFF, newest first."""
    items = []
    for js in sorted(Path("data").glob("tweets*.js")):
        raw = js.read_text(encoding="utf-8")
        rows = json.loads(raw[raw.index("["):].rstrip().rstrip(";"))
        for row in rows:
            t = row["tweet"]
            text = t.get("full_text", "")
            if text.startswith("RT @") or t.get("in_reply_to_status_id"):
                continue                    # skip retweets and replies
            ts = datetime.strptime(" ".join(t["created_at"].split()),
                                   "%a %b %d %H:%M:%S %z %Y")
            if ts >= CUTOFF:
                continue
            media = (t.get("extended_entities", {}).get("media")
                     or t.get("entities", {}).get("media", []))
            found = []
            for m in media:
                text = text.replace(m.get("url", ""), "")  # strip dead t.co links
                path = find_media_file(t["id_str"], m)
                if path:
                    found.append({"path": str(path),
                                  "alt": m.get("ext_alt_text") or ""})
            if text.strip() or found:
                items.append({"ts": ts.isoformat(), "text": text.strip(),
                              "media": found})
    items.sort(key=lambda i: i["ts"], reverse=True)
    return items


# ---------------------------------------------------------- X: media upload

def media_id(response):
    if not response.ok:
        print(f"X upload error {response.status_code}: {response.text[:200]}")
        return None
    body = response.json() if response.text.strip() else {}
    return (body.get("data") or {}).get("id") or body.get("media_id_string")


def set_alt_text(mid, alt):
    if not (alt and mid):
        return
    try:
        r = X.post(f"{UPLOAD_URL}/alt",
                   json={"media_id": str(mid), "text": alt[:1000]})
        if not r.ok:
            print(f"alt text not added ({r.status_code}) - continuing without it")
    except Exception as e:
        print("alt text not added:", e)


def upload_simple(path, category, alt):
    with open(path, "rb") as f:
        r = X.post(UPLOAD_URL, data={"media_category": category}, files={"media": f})
    mid = media_id(r)
    if mid:
        set_alt_text(mid, alt)
    return mid


def upload_chunked(path, media_type, category, alt=""):
    init = {"command": "INIT", "media_type": media_type,
            "media_category": category, "total_bytes": os.path.getsize(path)}
    r = X.post(UPLOAD_URL, json=init)
    if not r.ok:
        r = X.post(UPLOAD_URL, data=init)
    mid = media_id(r)
    if not mid:
        return None
    with open(path, "rb") as f:
        for seg, chunk in enumerate(iter(lambda: f.read(4 * 1024 * 1024), b"")):
            r = X.post(UPLOAD_URL,
                       data={"command": "APPEND", "media_id": mid,
                             "segment_index": seg},
                       files={"media": ("chunk", chunk)})
            if not r.ok:
                print(f"X append error {r.status_code}: {r.text[:200]}")
                return None
    fin = {"command": "FINALIZE", "media_id": mid}
    r = X.post(UPLOAD_URL, json=fin)
    if not r.ok:
        r = X.post(UPLOAD_URL, data=fin)
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
        r = X.get(UPLOAD_URL, params={"command": "STATUS", "media_id": mid})
        body = r.json() if r.text.strip() else {}
        info = ((body.get("data") or {}).get("processing_info")
                or body.get("processing_info"))
    if mid:
        set_alt_text(mid, alt)
    return mid


def upload_media(m):
    path, alt = m["path"], m.get("alt", "")
    ext = Path(path).suffix.lower()
    if ext in (".mp4", ".mov"):
        return upload_chunked(path,
                              "video/mp4" if ext == ".mp4" else "video/quicktime",
                              "tweet_video", alt)
    if ext == ".gif" and os.path.getsize(path) > 5 * 1024 * 1024:
        return upload_chunked(path, "image/gif", "tweet_gif", alt)
    return upload_simple(path, "tweet_gif" if ext == ".gif" else "tweet_image", alt)


# ------------------------------------------------------------- X: posting

def x_post(item):
    """Post one archive tweet as a brand-new tweet. True on success."""
    motion = [m for m in item["media"]
              if Path(m["path"]).suffix.lower() in (".mp4", ".mov", ".gif")]
    stills = [m for m in item["media"] if m not in motion]
    chosen = motion[:1] if motion else stills[:4]   # 1 video/GIF or up to 4 photos

    ids = []
    for m in chosen:
        if not os.path.exists(m["path"]):
            print("media file missing, posting without it:", m["path"])
            continue
        mid = upload_media(m)
        if mid:
            ids.append(mid)

    payload = {}
    if item["text"]:
        payload["text"] = item["text"][:TWEET_MAX]
    if ids:
        payload["media"] = {"media_ids": ids}
    if not payload:
        print("X item has no text and no usable media - skipping")
        return False
    r = X.post(TWEET_URL, json=payload)
    if r.ok:
        print("X posted:", r.json()["data"]["id"])
        return True
    print(f"X post error {r.status_code}: {r.text[:300]}")
    return False


# ---------------------------------------------------------- Instagram side

def ig_queue():
    """All IG feed posts older than CUTOFF, newest first (cached in the repo)."""
    out, url = [], f"{GRAPH}/{IG_USER_ID}/media"
    params = {"fields": "id,timestamp", "limit": 100, "access_token": IG_TOKEN}
    while url:
        r = requests.get(url, params=params, timeout=30).json()
        if "error" in r:
            raise RuntimeError("IG list error: " + r["error"].get("message", ""))
        for p in r.get("data", []):
            ts = datetime.strptime(p["timestamp"], "%Y-%m-%dT%H:%M:%S%z")
            if ts < CUTOFF:
                out.append({"id": p["id"], "ts": p["timestamp"]})
        url = r.get("paging", {}).get("next")
        params = None                       # 'next' already contains the params
    out.sort(key=lambda i: i["ts"], reverse=True)
    return out


def ig_repost(item_id):
    """Re-publish one IG post. True on success."""
    r = requests.get(f"{GRAPH}/{item_id}", params={
        "fields": "caption,media_type,media_url,children{media_type,media_url}",
        "access_token": IG_TOKEN}, timeout=30).json()
    if "error" in r:
        print("IG fetch error:", r["error"].get("message"))
        return False
    caption = r.get("caption") or ""

    def container(payload):
        c = requests.post(f"{GRAPH}/{IG_USER_ID}/media", data=payload,
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

    if r["media_type"] == "CAROUSEL":
        kids = [child(c) for c in r["children"]["data"]]
        cid = container({"media_type": "CAROUSEL", "children": ",".join(kids),
                         "caption": caption, "access_token": IG_TOKEN})
    elif r["media_type"] == "VIDEO":
        try:    # try as a Reel first, plain video post as fallback
            cid = container({"media_type": "REELS", "video_url": r["media_url"],
                             "caption": caption, "access_token": IG_TOKEN})
        except RuntimeError as e:
            print(e)
            cid = container({"media_type": "VIDEO", "video_url": r["media_url"],
                             "caption": caption, "access_token": IG_TOKEN})
    else:
        cid = container({"image_url": r["media_url"], "caption": caption,
                         "access_token": IG_TOKEN})

    for _ in range(60):                     # wait for processing (videos)
        s = requests.get(f"{GRAPH}/{cid}", params={"fields": "status_code",
                         "access_token": IG_TOKEN}, timeout=30).json()
        if s.get("status_code") == "FINISHED":
            break
        if s.get("status_code") == "ERROR":
            print("IG processing error")
            return False
        time.sleep(5)

    p = requests.post(f"{GRAPH}/{IG_USER_ID}/media_publish",
                      data={"creation_id": cid, "access_token": IG_TOKEN},
                      timeout=30).json()
    if "error" in p:
        print("IG publish error:", p["error"].get("message"))
        return False
    print("IG posted:", p["id"])
    return True


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
    state = load_json(STATE_FILE, {"x": 0, "ig": 0, "x_fail": 0, "ig_fail": 0})

    if X:
        try:
            queue = x_queue()
        except Exception as e:
            print("X backlog build failed:", e)
            queue = []
        run_platform("X", state, "x", "x_fail", queue, x_post)
    else:
        print("X credentials not set - skipping X")

    if IG_TOKEN and IG_USER_ID:
        igq = load_json(IG_QUEUE_FILE, None)
        if igq is None:
            try:
                igq = ig_queue()
                save_json(IG_QUEUE_FILE, igq)
            except Exception as e:
                print("IG backlog build failed, will retry next run:", e)
                igq = None
        if igq is not None:
            run_platform("IG", state, "ig", "ig_fail", igq,
                         lambda item: ig_repost(item["id"]))
    else:
        print("IG credentials not set - skipping Instagram")


if __name__ == "__main__":
    main()
