Auto-repost backlog (X + Instagram)
Reposts one old item to X and one to Instagram every 4 hours, replaying yourhistory from July 2025 backwards. Runs entirely on GitHub Actions free tier.

Files
File	Purpose
repost.py	The bot (X + Instagram logic)
.github/workflows/repost.yml	Scheduler - fires every 4 h, commits progress
requirements.txt	Python dependencies
data/tweets.js	Your tweet archive (from the X data download)
data/tweets_media/	Media files from the same download
state.json	Progress pointers (auto-created)
ig_queue.json	Cached Instagram backlog (auto-created)
Required secrets (Settings → Secrets and variables → Actions)
X_API_KEY, X_API_SECRET, X_ACCESS_TOKEN, X_ACCESS_TOKEN_SECRET, IG_TOKEN, IG_USER_ID

Tuning
How far back the backlog goes: CUTOFF at the top of repost.py
Posting frequency: the cron: line in the workflow (UTC)
Controls
Run now: Actions → repost → Run workflow (each run posts one real item)
Pause: Actions → repost → ⋯ → Disable workflow (progress is kept)
Resume: Enable workflow
What these files don't include (you add these)
1. The data/ folder — from your X archive download: create a folder named data, put only tweets.js and tweets_media/ inside (delete any single file over 100 MB — GitHub's hard limit).

2. The 6 secrets — from the credential walkthrough in my earlier message (Steps 1–3). Quick map:

Secret
Comes from
X_API_KEY, X_API_SECRET	developer.x.com → your app → Keys and tokens
X_ACCESS_TOKEN, X_ACCESS_TOKEN_SECRET	same page — generate after setting app permissions to Read and Write
IG_TOKEN	Graph API Explorer → long-lived token → me/accounts response → page access_token
IG_USER_ID	same me/accounts response → instagram_business_account.id

Deploy checklist
Create a private repo on GitHub.
Add file → Create new file, type .github/workflows/repost.yml (the slashes auto-create folders), paste File 2. Repeat for repost.py, requirements.txt, README.md.
Add file → Upload files, drag your data folder in. If it holds thousands of media files and the web upload chokes, push with git from the CLI instead.
Settings → Secrets and variables → Actions → New repository secret — add all six, exact names as above.
Actions tab → enable workflows if prompted → repost → Run workflow (branch: main). A healthy first run logs:
text

X backlog: 417 items, next: #1
X posted: 1749123456789012345
IG backlog: 88 items, next: #1
IG posted: 17981234567890123
followed by a green "Commit progress" step. Verify both posts appear live in the apps, media included.
Walk away. It fires every 4 hours at :13 UTC, forever, at $0.
Quick troubleshooting
X 401/403 → access token was generated before enabling Read+Write; regenerate it and update the two X_ACCESS_* secrets.
X 404 on media upload → flip UPLOAD_URL in repost.py to the alternative host noted in the comment next to it.
IG OAuth errors later on → redo the token exchange (earlier message, Step 3.4–3.5) and update IG_TOKEN; progress and backlog are untouched.
A skipped/late cron tick → harmless; the next tick posts the same next item. Nothing double-posts, because state only advances after a successful publish.
