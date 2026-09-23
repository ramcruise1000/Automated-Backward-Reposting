STANDARD OPERATING PROCEDURE
Zero-Cost Instagram Auto-Reposting System (GitHub Actions)
Document version	1.0
System cost	$0 — free tiers only, no payment method attached anywhere
Runtime location	GitHub's cloud servers (your computer is never involved)
Posting cadence	1 post every 4 hours (configurable)
Credential validity	Permanent token — no scheduled renewals
1. OVERVIEW
1.1 What this system does
Automatically re-publishes your own old Instagram feed posts as brand-new posts, working backwards from a cutoff date (newest old post first). Optionally cross-posts the same content to X/Twitter if a free X API allocation exists. Runs entirely on GitHub Actions' free tier.

1.2 Architecture
GitHub Actions cron (every 4 h, :13 UTC — free)        │        ▼  repost.py  (runs on GitHub's servers)        │        ├── ig_queue.json   backlog of old post IDs (built once, cached in repo)        ├── state.json      progress pointers (committed after every run)        │        ├── Instagram Graph API  ──►  re-publishes the next old post        └── X API (optional)     ──►  cross-posts it as a new tweet
1.3 Cost breakdown
Component	Cost	Usage vs. free limit
GitHub private repo + Actions	$0	~2–4 min/run × ~180 runs ≈ 700 of 2,000 free min/month
Instagram Graph API (own account)	$0	6 posts/day of 50 allowed per 24 h
Meta Business Manager + system-user token	$0	—
X API (optional)	$0 only if the account has a free posting allocation	see §8-E
1.4 Prerequisites
Instagram account (will be switched to a free professional account)
A working Facebook account
A GitHub account
Desktop browser for Meta/GitHub steps; the Instagram app for linking steps
Total setup time: ~1.5–2 hours
2. PART 1 — INSTAGRAM & FACEBOOK SETUP
2.1 Switch Instagram to a professional account
IG app → profile → ☰ → Settings and privacy → Account type and tools → Switch to professional account.
Choose Creator (or Business). Skip all optional prompts.
2.2 Create a Facebook Page (plumbing only)
Log in at facebook.com → Pages → Create New Page.
Name it anything. Nothing will ever be posted to it; it exists only because Instagram's publishing API requires a Page link. It can stay blank forever.
2.3 Link the Instagram account to the Page (critical step)
IG app → profile → ☰ → Settings and privacy → Business tools and controls → Page settings → Connect a Facebook Page (wording varies by app version; alternatively profile → Edit profile → Page).
Select the Page created in §2.2.
If a Page is already connected and you want to change it: disconnect first, then connect the new one. An IG account can hold only one Page link.
Verify which Facebook account IG is using for links: ☰ → Settings → Accounts Center → Accounts. This must be the same Facebook account you will use for everything else in this SOP. A mismatch here is the #1 cause of "invisible page" problems (see §8-B).
2.4 Get your IG_USER_ID
Desktop browser → Graph API Explorer at developers.facebook.com/tools/explorer. First visit may prompt developer registration — complete it (free, no card).
Click Generate Access Token and tick: pages_show_list, pages_read_engagement, instagram_basic (renamed variants such as instagram_business_basic are fine).
Consent, then set method GET and run:
me/accounts?fields=name,instagram_business_account{username}
Find the entry whose instagram_business_account.username matches your IG handle. Record:
instagram_business_account.id   →   your IG_USER_ID  (starts with 178...)
If no entry shows instagram_business_account → see §8-B.
3. PART 2 — PERMANENT ACCESS TOKEN (Meta Business Manager)
This produces a token that never expires and survives Facebook password changes. (Simpler alternative: a long-lived user token via the oauth exchange endpoint — but it expires every ~60 days and is not recommended.)

3.1 Create the Business
Go to business.facebook.com → create a Business (free) using the same Facebook account as §2.3.
3.2 Add the Instagram account as a Business asset
Business Settings (gear icon) → Accounts → Instagram accounts → Add → log in with your IG username/password.
3.3 Create a system user
Business Settings → Users → System users → Add.
Name: repostbot. Role: Admin.
3.4 Create an app inside the Business
Business Settings → Accounts → Apps → Add → Create a new app → name it anything, type Business.
Apps created inside a Business are automatically its assets. (Claiming an existing personal developer app instead is possible via "Add an app" + App ID, but creating fresh is more reliable — see §8-A6.)
3.5 Assign assets to the system user
Users → System users → repostbot → Assign Assets.
Apps tab → the new app → Full control → Save.
Instagram accounts tab → your IG account → Full control → Save.
3.6 Generate the never-expiring token
On the system user page → Generate Token.
Select app → the new app.
Set expiration → Never / no expiration. (This is the entire point of Part 2 — do not accept 60 days.)
Assign permissions → tick instagram_basic and instagram_content_publish (renamed variants fine).
Generate → copy the token immediately (shown once). Treat it like a password.
3.7 Test the token before using it
Graph API Explorer → paste the token into the Access Token box.
Method GET, run (substitute your IG_USER_ID):
178414xxxxxxxxxx/media?fields=id&limit=1
A response containing a post "id" = success. Any error → §8-A.
4. PART 3 — GITHUB REPOSITORY
4.1 Create the repository
GitHub → New repository → Private (important: the repo will contain access to your accounts) → name it anything (e.g. ig-repost).
4.2 Add the files
Create these files via Add file → Create new file (typing slashes creates folders):

File	Content
.github/workflows/repost.yml	Appendix B
repost.py	Appendix A
requirements.txt	Appendix C
README.md	Appendix D (optional)
SOP.md	this document
4.3 Add the secrets
Repo → Settings → Secrets and variables → Actions → New repository secret:

Secret name	Value
IG_TOKEN	the system-user token from §3.6
IG_USER_ID	the 178... ID from §2.4
Optional X/Twitter cross-posting — only if the X developer console shows a genuine free posting allocation for your account (check the Dashboard/Usage page; "Pay Per Use" with $0 credits = no free posting, do not proceed): add X_API_KEY, X_API_SECRET, X_ACCESS_TOKEN, X_ACCESS_TOKEN_SECRET from developer.x.com (app → User authentication set up: OAuth 1.0a, Read and write → then Keys and tokens → generate the OAuth 1.0a Access Token & Secret, confirming "Created with Read and Write permissions"). Without these secrets the script cleanly skips X.

5. PART 4 — FIRST RUN & VERIFICATION
5.1 Trigger
Actions tab → enable workflows if prompted → left sidebar repost → Run workflow → branch main.
Note: the schedule starts by itself the moment the workflow file lands on main — no button is required for the cron to be live. The button only triggers an extra run.
5.2 What the first runs look like
The backlog build (one-time) pages through your entire IG history and can be throttled by Instagram, so expect a sequence like this across the first few runs:

no banked backlog yet - building nowbacklog build: 5 pages read, 0 old posts so far     ← newer-than-cutoff posts being paged past...page too large for IG - retrying with limit 10      ← auto-recovery from throttling...IG backlog build interrupted, will resume next run  ← normal: progress is checkpointed
From the first run that has any banked items, posting begins:

X backlog: N items, next: #1                        ← only if X secrets existIG backlog: N items, next: #1IG posted: 17xxxxxxxxxxxxx
followed by a green Commit progress step. Subsequent runs print resuming backlog build from page N and keep deepening the queue until the log shows backlog COMPLETE: N old posts.

5.3 Verify
The re-published post appears in the IG app as a normal new post.
state.json and ig_queue.json exist in the repo and update every run.
A green run does not prove posting occurred — always read the "Post the next item" log step for the truth.
6. PART 5 — CHANGING THE BACKPOST START DATE ★
To restart the cycle from any date (e.g., begin replaying from Jan 2023 instead of Aug 2025), all three of these are required — editing the date alone does nothing, because the bot trusts its cache:

#	Action	Why
1	repost.py → edit the CUTOFF = datetime(2025, 8, 1, tzinfo=timezone.utc) line to the new date → Commit	The date posts must be older than
2	Delete ig_queue.json from the repo → Commit	Forces a fresh backlog build
3	Delete state.json from the repo → Commit	Resets posting progress to zero
Result: the next run rebuilds the backlog from the new date; the first repost becomes the newest post before the new cutoff.

Notes:

The rebuild may take several runs (Instagram throttling) but posting starts on the very first run from whatever has been collected.
The queue contains only posts older than CUTOFF — posts newer than the cutoff are automatically skipped and never reposted.
Since this is deliberate content replay, items already reposted in a previous cycle will be reposted again. Advanced skip (optional): when moving the cutoff to a more recent date, note the old log's IG backlog: N total and state.json's "ig" value; after the new build prints backlog COMPLETE: X items, create state.json with {"ig": (X − N) + old_ig, "x": 0, "ig_fail": 0, "x_fail": 0} to jump past the already-reposted stretch.
7. PART 6 — OPERATIONS & MAINTENANCE
Task	How
Pause	Actions → repost → ⋯ → Disable workflow (progress preserved)
Resume	Enable workflow — continues exactly where it stopped
Change frequency	Workflow file → edit the cron: line (UTC) → Commit. Common: every 4 h 13 */4 * * * · every 2 h 13 */2 * * * (12/day — max recommended; IG allows 50/24 h) · daily 13 9 * * *
Stop deepening the backlog	repost.py → set BUILD_BUDGET_MINUTES = 0 → the bot posts only the already-banked items
Check health	Visit the Actions tab occasionally; a healthy run shows IG posted:. Red run → read the last lines of the log step → §8
When the backlog runs out	Log shows backlog exhausted and posting stops. Restart via Part 5
Token security	Never paste tokens or API responses containing them anywhere public. If leaked: regenerate via §3.6 and update the IG_TOKEN secret (2 min)
Graph API retirement (years away)	If the log errors mention an invalid/retired API version, edit GRAPH = "https://graph.facebook.com/v26.0" in repost.py to the current version number
Repo dormancy	GitHub disables schedules after 60 days of no activity; the bot's own commits prevent this automatically
Never click "Enable auto-recharge" or similar prompts on any console in this stack — that is the only path to attaching a payment method.

8. PART 7 — TROUBLESHOOTING ENCYCLOPEDIA
8-A. Tokens & permissions (Meta)
#	Symptom	Cause	Fix
A1	Malformed access token ...token_type":"bearer"...	Copied the entire JSON response instead of just the token string	Copy only the characters between "access_token":" and the closing quote. Paste into Notepad first to verify: letters/numbers only, no " , { }
A2	Missing client_id parameter (code 101)	The token-exchange URL was pasted into the Graph API Explorer, which strips the query string	Paste the URL into a plain browser address bar, one line, no spaces
A3	Session has expired	A user token (~60-day life) is in use	Replace with the system-user token (§3), or regenerate
A4	me/accounts returns Pages but no access_token field	Token lacks Page permissions	Regenerate token with pages_show_list etc.
A5	me/accounts entries show no instagram_business_account	(a) Field not requested — it must be in ?fields=; (b) IG permissions missing → fields silently dropped; (c) IG not linked to any listed Page; (d) results paginated — click through all pages	Request the field explicitly; re-add permissions; fix link (§8-B); check every page of results
A6	Token wizard: "No permissions available"	System user has no role on the selected app	Business Settings → system user → Assign Assets → Apps → the app → Full control. If the app was created outside the Business, either claim it (Accounts → Apps → Add → by App ID) or create a fresh app inside the Business. If permissions appear but no instagram ones → add the Instagram product to the app (developers.facebook.com → app → Add Product)
A7	Token suddenly invalid after a Facebook password change	Personal-session tokens die on password resets	Re-generate; system-user tokens (§3) are immune — which is why they are the standard
8-B. Page linking
#	Symptom	Cause	Fix
B1	IG shows the Page as "connected" but the API never sees it	The link lives under a different Facebook identity than the token, or is a zombie link (e.g., after a password reset killed the session)	IG → Accounts Center → Accounts → remove the FB account, re-add with the current password → disconnect and reconnect the Page. Alternative: connect from the facebook.com side (Page → Settings → Instagram → Connect)
B2	Page picker in IG is empty or shows the wrong Pages	IG's Accounts Center is tied to the wrong FB account	Fix Accounts Center first (B1), then retry
B3	Newly created Page doesn't appear in API results	Created under a different FB identity, or propagation delay	Use any Page the token can see — the Page is invisible plumbing, any one works. If identities match, wait up to 1 h
8-C. GitHub Actions
#	Symptom	Cause	Fix
C1	No Run workflow button	It lives on the workflow's list page (Actions → repost), not inside an individual run	Navigate up one level. Note: Re-run re-executes the old commit's code; only Run workflow uses the latest
C2	Workflow ran by itself before any button press	Schedules activate as soon as the file is on main	Expected — add secrets only when ready for live posting
C3	Green ✅ run but nothing posted	Script exits cleanly when credentials are missing	Read the log step — look for credentials not set or errors; add secrets
C4	The operation was canceled	Job hit its timeout-minutes (or manual cancel) during the long first build	The build checkpoints every page; simply run again — it resumes. Timeout is set to 45 min in Appendix B
C5	Run took 10+ min, commit shows "1 file changed, NNNNN insertions"	Partial backlog build saved — by design	Normal. Next run resumes; posting begins from banked items
C6	Schedule silently disabled	60-day repo dormancy	The bot's own commits prevent this; if it ever happens, click Enable workflow
8-D. Backlog build & Instagram rate limits
#	Symptom	Cause	Fix
D1	Please reduce the amount of data you're asking for	Instagram throttling on large/fast paging — a rate limit in disguise; fresh runs get a new allowance	The script self-heals: auto-shrinks page size (25→10→5) and backs off (60/120/240 s). Let scheduled runs continue; the build finishes across runs. Posting is unaffected
D2	Build seems endless on a large account (thousands of posts)	Every page must be fetched once	Each run spends BUILD_BUDGET_MINUTES (default 20) extending the queue. Optionally set it to 0 and simply post the banked items
D3	Recent posts appear in the queue	They shouldn't — the builder skips anything newer than CUTOFF	If seen after a date change: the old ig_queue.json wasn't deleted — redo §6 completely
D4	Date changed but behavior unchanged	Cache not cleared	§6 requires all three steps: edit CUTOFF + delete ig_queue.json + delete state.json
8-E. X / Twitter (optional module)
#	Symptom	Cause	Fix
E1	credits depleted / console shows "Pay Per Use" with $0 balance	The account has no free API allocation	No code can fix an empty tank. Either accept IG-only (delete the four X_* secrets — runs then log X credentials not set - skipping X), or move X posting to a tool with its own free X access (e.g. Buffer's free plan, 10-post queue). Never enable auto-recharge
E2	X 401/403 on posting	Access token generated before Read+Write was enabled	Re-enable Read+Write, regenerate the Access Token & Secret, update secrets
E3	X 404 on media upload	Upload host changed	In repost.py, swap UPLOAD_URL between https://upload.x.com/... and https://api.x.com/...
E4	Two "Access Token" sections on the keys page	OAuth 1.0a vs OAuth 2.0	Use the OAuth 1.0a Access Token & Secret; ignore OAuth 2.0
E5	X queue pointer advanced while X was failing	Failure-skip logic (3 fails → skip) misfires on quota errors	Appendix A already contains the quota-pause patch (QuotaError pauses the platform without skipping). If using an older script: reset "x" in state.json to the true number of bot tweets and "x_fail": 0
APPENDIX A — repost.py (complete, production version)
#!/usr/bin/env python3"""Auto-repost for Instagram (single source), with optional X cross-posting.Every 4 hours (GitHub Actions cron) it takes the next old post from the IGbacklog (everything posted before CUTOFF, newest first) and:  - re-publishes it to Instagram as a new post  - optionally cross-posts it to X as a brand-new tweet (only if X_*    secrets are set and the X app has free API credits)POSTING ALWAYS RUNS FIRST from the banked backlog (ig_queue.json); anyremaining job time is spent extending the backlog. The build checkpointsafter every page, so interruptions never lose progress."""import jsonimport osimport shutilimport tempfileimport timefrom datetime import datetime, timezonefrom pathlib import Pathimport requestsfrom requests_oauthlib import OAuth1Session# ----------------------------------------------------------------- settingsCUTOFF = datetime(2025, 8, 1, tzinfo=timezone.utc)  # repost posts strictly OLDER# than this moment. Aug 1 2025 = "July 2025 and earlier".# >>> TO RESTART THE CYCLE FROM A NEW DATE: change this line, then delete# ig_queue.json and state.json from the repo (SOP Part 5). <<<MAX_TRIES = 3             # skip an item after this many consecutive failuresTWEET_MAX = 280           # X text limit; longer captions get truncatedX_STRIP_HASHTAGS = False  # True = remove #hashtags from the X version onlyBUILD_BUDGET_MINUTES = 20 # run time spent finishing the backlog build each runSTATE_FILE = Path("state.json")IG_QUEUE_FILE = Path("ig_queue.json")GRAPH = "https://graph.facebook.com/v26.0"   # if a future log says this# version was retired, change v26.0 to the current Graph version numberUPLOAD_URL = "https://upload.x.com/2/media/upload"  # if uploads 404, switch to# "https://api.x.com/2/media/upload"TWEET_URL = "https://api.x.com/2/tweets"# ----------------------------------------------------------------- clientsIG_TOKEN = os.environ.get("IG_TOKEN", "")IG_USER_ID = os.environ.get("IG_USER_ID", "")_x = [os.environ.get(k, "") for k in      ("X_API_KEY", "X_API_SECRET", "X_ACCESS_TOKEN", "X_ACCESS_TOKEN_SECRET")]X = OAuth1Session(*_x) if all(_x) else NoneS = requests.Session()     # reused connections - makes backlog paging much fasterS.headers.update({"User-Agent": "Mozilla/5.0 (repost-bot)"})class QuotaError(Exception):    """Raised when X reports that API credits are depleted."""    pass# ----------------------------------------------------------------- helpersdef load_json(path, default):    try:        return json.loads(Path(path).read_text(encoding="utf-8"))    except FileNotFoundError:        return defaultdef save_json(path, obj):    Path(path).write_text(json.dumps(obj, indent=1, ensure_ascii=False),                          encoding="utf-8")# ------------------------------------------------- backlog (Instagram feed)def ig_queue(budget_seconds=None):    """    All IG feed posts older than CUTOFF, newest first.    Resumes from the ig_queue.json checkpoint. Checkpoints after every page.    When Instagram throttles ("reduce the amount of data"), it waits out the    throttle with increasing backoffs instead of giving up, and shrinks the    page size as needed. Returns whatever is banked so far (partial is fine).    """    if budget_seconds is None:        budget_seconds = BUILD_BUDGET_MINUTES * 60    cache = load_json(IG_QUEUE_FILE, None)    if isinstance(cache, dict) and cache.get("done"):        return cache["items"]    if isinstance(cache, dict):        items = cache.get("items", [])        after = cache.get("after")        pages = cache.get("pages", 0)        limit = cache.get("limit", 25)    elif isinstance(cache, list):        items, after, pages, limit = cache, None, 0, 25    else:        items, after, pages, limit = [], None, 0, 25    if pages:        print(f"resuming backlog build from page {pages + 1} "              f"({len(items)} old posts collected so far)")    deadline = time.monotonic() + budget_seconds if budget_seconds > 0 else None    backoffs = 0    while True:        if deadline is not None and time.monotonic() > deadline:            print(f"build budget used up at page {pages} - continuing next run "                  f"({len(items)} old posts banked)")            save_json(IG_QUEUE_FILE, {"done": False, "after": after,                                      "pages": pages, "items": items,                                      "limit": limit})            return items        params = {"fields": "id,timestamp", "limit": limit,                  "access_token": IG_TOKEN}        if after:            params["after"] = after        r = S.get(f"{GRAPH}/{IG_USER_ID}/media", params=params,                  timeout=30).json()        if "error" in r:            msg = r["error"].get("message", "")            if "reduce the amount of data" in msg.lower():                if limit > 5:                    limit = 10 if limit > 10 else 5                    print(f"page too large for IG - retrying with limit {limit}")                    continue                if backoffs < 3:                    wait = 60 * (2 ** backoffs)                    backoffs += 1                    print(f"IG is throttling the build - waiting {wait}s "                          f"before retrying")                    time.sleep(wait)                    continue                print("IG still throttling - saving progress, continuing next run")                save_json(IG_QUEUE_FILE, {"done": False, "after": after,                                          "pages": pages, "items": items,                                          "limit": limit})                return items            raise RuntimeError("IG list error: " + msg)        backoffs = 0        for p in r.get("data", []):            ts = datetime.strptime(p["timestamp"], "%Y-%m-%dT%H:%M:%S%z")            if ts < CUTOFF:                items.append({"id": p["id"], "ts": p["timestamp"]})        after = r.get("paging", {}).get("cursors", {}).get("after")        if not r.get("data"):            after = None                        # empty page = end of feed        pages += 1        if pages % 5 == 0 or not after:            print(f"backlog build: {pages} pages read, "                  f"{len(items)} old posts so far")        save_json(IG_QUEUE_FILE, {"done": not after, "after": after,                                  "pages": pages, "items": items,                                  "limit": limit})        if not after:            items.sort(key=lambda i: i["ts"], reverse=True)            save_json(IG_QUEUE_FILE, {"done": True, "after": None,                                      "pages": pages, "items": items,                                      "limit": limit})            print(f"backlog COMPLETE: {len(items)} old posts")            return items        time.sleep(1.0)                         # gentle pacing between pagesdef fetch_post(item_id):    """Fresh details for one IG post (CDN media URLs are short-lived)."""    r = S.get(f"{GRAPH}/{item_id}", params={        "fields": "caption,media_type,media_url,children{media_type,media_url}",        "access_token": IG_TOKEN}, timeout=30).json()    if "error" in r:        raise RuntimeError("IG fetch error: " + r["error"].get("message", ""))    return r# ---------------------------------------------------- repost to Instagramdef ig_publish(post):    """Re-publish one IG post as a new post. True on success."""    caption = post.get("caption") or ""    def container(payload):        c = S.post(f"{GRAPH}/{IG_USER_ID}/media", data=payload,                   timeout=120).json()        if "error" in c:            raise RuntimeError("IG container error: " + c["error"].get("message", ""))        return c["id"]    def child(c):        d = {"is_carousel_item": "true", "access_token": IG_TOKEN}        if c["media_type"] == "VIDEO":            d |= {"media_type": "VIDEO", "video_url": c["media_url"]}        else:            d["image_url"] = c["media_url"]        return container(d)    if post["media_type"] == "CAROUSEL":        kids = [child(c) for c in post.get("children", {}).get("data", [])]        cid = container({"media_type": "CAROUSEL", "children": ",".join(kids),                         "caption": caption, "access_token": IG_TOKEN})    elif post["media_type"] == "VIDEO":        try:    # try as a Reel first, plain video post as fallback            cid = container({"media_type": "REELS", "video_url": post["media_url"],                             "caption": caption, "access_token": IG_TOKEN})        except RuntimeError as e:            print(e)            cid = container({"media_type": "VIDEO", "video_url": post["media_url"],                             "caption": caption, "access_token": IG_TOKEN})    else:        cid = container({"image_url": post["media_url"], "caption": caption,                         "access_token": IG_TOKEN})    for _ in range(60):                     # wait for processing (videos)        s = S.get(f"{GRAPH}/{cid}", params={"fields": "status_code",                 "access_token": IG_TOKEN}, timeout=30).json()        if s.get("status_code") == "FINISHED":            break        if s.get("status_code") == "ERROR":            print("IG processing error")            return False        time.sleep(5)    p = S.post(f"{GRAPH}/{IG_USER_ID}/media_publish",               data={"creation_id": cid, "access_token": IG_TOKEN},               timeout=30).json()    if "error" in p:        print("IG publish error:", p["error"].get("message"))        return False    print("IG posted:", p["id"])    return True# ---------------------------------------------------- cross-post to Xdef download_media(url, dest_dir):    """Download an IG CDN file. Returns local path or None."""    base = url.split("?")[0].split("/")[-1] or "media"    path = Path(dest_dir) / base    with S.get(url, stream=True, timeout=180) as r:        if not r.ok:            print(f"download failed {r.status_code}: {url[:100]}")            return None        ctype = r.headers.get("Content-Type", "")        if "video" in ctype and path.suffix.lower() not in (".mp4", ".mov"):            path = path.with_suffix(".mp4")        elif "image" in ctype and path.suffix.lower() not in (".jpg", ".jpeg",                                                              ".png", ".webp"):            path = path.with_suffix(".jpg")        with open(path, "wb") as f:            for chunk in r.iter_content(1024 * 1024):                f.write(chunk)    return str(path)def media_id(response):    if not response.ok:        if "credit" in response.text.lower():            raise QuotaError("X credits depleted (during media upload)")        print(f"X upload error {response.status_code}: {response.text[:200]}")        return None    body = response.json() if response.text.strip() else {}    return (body.get("data") or {}).get("id") or body.get("media_id_string")def upload_simple(path):    with open(path, "rb") as f:        r = X.post(UPLOAD_URL, data={"media_category": "tweet_image"},                   files={"media": f}, timeout=300)    return media_id(r)def upload_chunked(path, media_type, category):    init = {"command": "INIT", "media_type": media_type,            "media_category": category, "total_bytes": os.path.getsize(path)}    r = X.post(UPLOAD_URL, json=init, timeout=300)    if not r.ok:        r = X.post(UPLOAD_URL, data=init, timeout=300)    mid = media_id(r)    if not mid:        return None    with open(path, "rb") as f:        for seg, chunk in enumerate(iter(lambda: f.read(4 * 1024 * 1024), b"")):            r = X.post(UPLOAD_URL,                       data={"command": "APPEND", "media_id": mid,                             "segment_index": seg},                       files={"media": ("chunk", chunk)}, timeout=300)            if not r.ok:                if "credit" in r.text.lower():                    raise QuotaError("X credits depleted (during upload)")                print(f"X append error {r.status_code}: {r.text[:200]}")                return None    fin = {"command": "FINALIZE", "media_id": mid}    r = X.post(UPLOAD_URL, json=fin, timeout=300)    if not r.ok:        r = X.post(UPLOAD_URL, data=fin, timeout=300)    if not r.ok:        if "credit" in r.text.lower():            raise QuotaError("X credits depleted (during finalize)")        print(f"X finalize error {r.status_code}: {r.text[:200]}")        return None    body = r.json() if r.text.strip() else {}    info = (body.get("data") or {}).get("processing_info") or body.get("processing_info")    while info and info.get("state") not in ("succeeded", "FINISHED"):        if info.get("state") in ("failed", "ERROR"):            print("X media processing failed")            return None        time.sleep(min(info.get("check_after_secs", 5), 30))        r = X.get(UPLOAD_URL, params={"command": "STATUS", "media_id": mid},                  timeout=30)        body = r.json() if r.text.strip() else {}        info = ((body.get("data") or {}).get("processing_info")                or body.get("processing_info"))    return middef upload(path):    ext = Path(path).suffix.lower()    if ext in (".mp4", ".mov"):        return upload_chunked(path, "video/mp4" if ext == ".mp4" else "video/quicktime",                              "tweet_video")    if os.path.getsize(path) > 5 * 1024 * 1024:     # big image: chunked upload        return upload_chunked(path, "image/jpeg", "tweet_image")    return upload_simple(path)def x_post(post):    """Cross-post one IG item to X as a new tweet. True on success."""    tmp = tempfile.mkdtemp()    try:        # X allows one video OR up to four photos per tweet        if post["media_type"] == "CAROUSEL":            kids = post.get("children", {}).get("data", [])            vids = [c for c in kids if c["media_type"] == "VIDEO"]            picks = vids[:1] if vids else [c for c in kids                                            if c["media_type"] != "VIDEO"][:4]        elif post["media_type"] == "VIDEO":            picks = [post]        else:            picks = [post]        ids = []        for m in picks:            f = download_media(m["media_url"], tmp)            if f:                mid = upload(f)                if mid:                    ids.append(mid)        text = post.get("caption") or ""        if X_STRIP_HASHTAGS:            text = " ".join(w for w in text.split() if not w.startswith("#"))        payload = {}        if text:            payload["text"] = text[:TWEET_MAX]        if ids:            payload["media"] = {"media_ids": ids}        if not payload:            print("X item has no caption and no usable media - skipping")            return False        r = X.post(TWEET_URL, json=payload, timeout=60)        if r.ok:            print("X posted:", r.json()["data"]["id"])            return True        if "credit" in r.text.lower():            raise QuotaError("X credits depleted (while posting)")        print(f"X post error {r.status_code}: {r.text[:300]}")        return False    finally:        shutil.rmtree(tmp, ignore_errors=True)# -------------------------------------------------------------------- maindef run_platform(name, state, idx_key, fail_key, queue, post_fn):    """Post the next queue item; remember progress; skip after MAX_TRIES fails."""    idx, fails = state.get(idx_key, 0), state.get(fail_key, 0)    print(f"{name} backlog: {len(queue)} items, next: #{idx + 1}")    if idx >= len(queue):        print(f"{name}: backlog exhausted")        return    try:        ok = post_fn(queue[idx])    except QuotaError:        print(f"{name}: API credits exhausted - pausing this platform.")        print("Current item NOT skipped - it will retry when credits return.")        save_json(STATE_FILE, state)        return    except Exception as e:                  # never let one platform kill the run        print(f"{name} error: {e}")        ok = False    if ok:        state[idx_key] = idx + 1        state[fail_key] = 0    else:        state[fail_key] = fails + 1        if state[fail_key] >= MAX_TRIES:            print(f"{name}: giving up on item #{idx + 1}, skipping it")            state[idx_key] = idx + 1            state[fail_key] = 0    save_json(STATE_FILE, state)def main():    if not (IG_TOKEN and IG_USER_ID):        print("IG credentials missing - cannot build the backlog, nothing to do")        return    state = load_json(STATE_FILE, {"x": 0, "ig": 0, "x_fail": 0, "ig_fail": 0})    cache = load_json(IG_QUEUE_FILE, None)    if isinstance(cache, dict):        items = cache.get("items", [])    elif isinstance(cache, list):        items = cache    else:        items = []    # ---- 1) POST FIRST, from whatever is already banked ----    if not items:        print("no banked backlog yet - building now")        if BUILD_BUDGET_MINUTES > 0:            try:                items = ig_queue()            except Exception as e:                print("IG backlog build interrupted, will resume next run:", e)    if items:        if X:            run_platform("X", state, "x", "x_fail", items,                         lambda item: x_post(fetch_post(item["id"])))        else:            print("X credentials not set - skipping X")        run_platform("IG", state, "ig", "ig_fail", items,                     lambda item: ig_publish(fetch_post(item["id"])))    # ---- 2) EXTEND the backlog with the remaining time budget ----    if BUILD_BUDGET_MINUTES > 0:        fresh = load_json(IG_QUEUE_FILE, None)        if not (isinstance(fresh, dict) and fresh.get("done")):            try:                ig_queue()            except Exception as e:                print("backlog extension interrupted, will resume next run:", e)if __name__ == "__main__":    main()
APPENDIX B — .github/workflows/repost.yml
name: reposton:  schedule:    - cron: "13 */4 * * *"   # every 4 hours at :13 past (UTC). The off-zero                             # minute avoids GitHub's top-of-hour congestion.  workflow_dispatch:          # allows manual runs from the Actions tabpermissions:  contents: write             # needed to commit state.json backconcurrency:  group: repost               # never let two runs overlap  cancel-in-progress: falsejobs:  repost:    runs-on: ubuntu-latest    timeout-minutes: 45       # long enough for the one-time backlog build    steps:      - uses: actions/checkout@v4      - uses: actions/setup-python@v5        with:          python-version: "3.12"          cache: pip      - run: pip install -r requirements.txt      - name: Post the next item on each platform        env:          X_API_KEY: ${{ secrets.X_API_KEY }}          X_API_SECRET: ${{ secrets.X_API_SECRET }}          X_ACCESS_TOKEN: ${{ secrets.X_ACCESS_TOKEN }}          X_ACCESS_TOKEN_SECRET: ${{ secrets.X_ACCESS_TOKEN_SECRET }}          IG_TOKEN: ${{ secrets.IG_TOKEN }}          IG_USER_ID: ${{ secrets.IG_USER_ID }}        run: python repost.py      - name: Commit progress        if: always()        run: |          git config user.name "repost-bot"          git config user.email "actions@users.noreply.github.com"          git add state.json 2>/dev/null || true          git add ig_queue.json 2>/dev/null || true          git commit -m "progress" || echo "nothing to commit"          git push || echo "WARNING: push failed - state not saved this run"
APPENDIX C — requirements.txt
requests==2.32.3requests-oauthlib==2.0.0
APPENDIX D — README.md (repo documentation)
# Auto-repost backlog (Instagram)Reposts one old IG post every 4 hours, replaying history backwards from CUTOFF.Runs entirely on GitHub Actions free tier. Optional X cross-posting if X_*secrets are set.Files: repost.py (bot) · .github/workflows/repost.yml (scheduler) ·state.json / ig_queue.json (auto-created progress & backlog cache)Secrets: IG_TOKEN, IG_USER_ID (required) · X_* (optional)Restart the cycle from a new date: edit CUTOFF in repost.py, then deleteig_queue.json and state.json. Pause: Actions → repost → Disable workflow.
APPENDIX E — Glossary
Term	Meaning
CUTOFF	The date in repost.py; only posts older than it are replayed
IG_USER_ID	Instagram's internal account ID (starts 178...) — never changes
IG_TOKEN	Permanent system-user access token (Business Manager) — the key that authorizes posting
System user	A virtual account owned by a Meta Business, not a person — its tokens don't expire and survive password changes
ig_queue.json	Cached backlog of post IDs, built once with checkpoint/resume
state.json	Progress pointers: how many items each platform has posted
Checkpoint	Backlog-build progress saved after every page, so interrupted runs resume instead of restarting
Container	Instagram's two-step publishing flow: create a media container, wait for FINISHED, then publish
