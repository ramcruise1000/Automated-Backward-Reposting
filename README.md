Auto-repost backlog (Instagram → Instagram + X)
Your Instagram feed is the single source: every 4 hours the next old post(before CUTOFF, newest first) is re-published to Instagram and cross-postedto X as a brand-new tweet (caption as text, media re-uploaded). Runsentirely on GitHub Actions free tier.

Files
File	Purpose
repost.py	The bot (backlog, IG repost, X cross-post)
.github/workflows/repost.yml	Scheduler - fires every 4 h, commits progress
requirements.txt	Python dependencies
state.json	Per-platform progress pointers (auto-created)
ig_queue.json	Cached Instagram backlog (auto-created on first run)
Required secrets (Settings → Secrets and variables → Actions)
X_API_KEY, X_API_SECRET, X_ACCESS_TOKEN, X_ACCESS_TOKEN_SECRET, IG_TOKEN, IG_USER_ID

Tuning
How far back the backlog goes: CUTOFF at the top of repost.py
Posting frequency: the cron: line in the workflow (UTC)
Remove hashtags from X captions only: set X_STRIP_HASHTAGS = True in repost.py
Controls
Run now: Actions → repost → Run workflow (each run posts one real item per platform)
Pause: Actions → repost → ... (three dots) → Disable workflow (progress is kept)
Resume: Enable workflow
