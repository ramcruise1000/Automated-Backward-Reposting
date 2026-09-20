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
Pause: Actions → repost → ... (three dots) → Disable workflow (progress is kept)
Resume: Enable workflow
(The README is documentation only — the bot doesn't read it. If you ever want to skip it, the automation still works. But good to have.)
