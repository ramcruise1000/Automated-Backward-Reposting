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
        raise RuntimeError("IG fetch error: " + r["error
