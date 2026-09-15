# Daily AI Content — Setup

Two things happen every morning at 7:00am via `com.minmiller.aicontent.plist`:

1. **News pipeline (interactive, via Telegram)**: fetches from Reddit, Hacker News, arXiv, a curated list of newsletters/VC blogs/publications (RSS), your manual Twitter drop-in file, and (if configured) the X API — builds a short, curated digest of **3-6 topics total** (1-3 major, 1-3 niche), **each tagged with its source and split into two sections** (🔥 Major/Pressing — the biggest, most-covered stories; 🔍 Niche/Interesting — real but not mainstream), saves it to `~/content-log/digests/YYYY-MM-DD.md`, and **sends it to you on Telegram** along with your daily checklist. The 6-item cap is enforced in code, not just prompt instruction — backlog items count toward it too (they're kept in full, with remaining slots filled by the best fresh items, major-tier first) so an accumulating backlog can't silently balloon the total back up. Numbering stays continuous across both sections. Reply with one number to pick today's topic; reply with several (e.g. `3,5,7`) to pick the first as today's topic and save the rest to a persistent backlog that resurfaces at the top of every future digest until you pick or leave it. Once a topic's picked, reply with feedback to revise the script, or "approved" to finalize. The finished script lands at `~/content-log/scripts/YYYY-MM-DD-news.md`.
2. **Concept pipeline (automatic, no interaction needed)**: pulls the next topic from `concepts.md`'s queue and writes a script straight to `~/content-log/scripts/YYYY-MM-DD-concept.md`.

A second job (`com.minmiller.aicontent.telegrampoll.plist`) checks Telegram for your replies every 60 seconds (changed 2026-09-08 from 5 minutes — still real polling latency, just shorter) and drives the news-pipeline conversation forward. This same poller also drives the daily tweet thread's review flow (see `~/dev/learning-tweet/SETUP.md`) — one shared poller for both, so they don't race each other consuming the same bot's messages. As soon as it picks up a message meant for an active flow, it sends "Got it, working on it..." before doing the (sometimes 5-20+ second) claude call, so you're not left wondering if it saw your message.

**Voice message feedback**: you can reply with a Telegram voice note instead of typing — it's transcribed locally (via `mlx-whisper`, on-device, no API key or cost) and treated exactly like a typed reply. Works for both the news pipeline and the daily thread review.

**Required for the news pipeline to actually reach you: a Telegram bot (below).** Everything else — Hacker News, the concept pipeline — needs no setup and already works.

## 1. Create a dedicated Telegram bot

1. In Telegram, message **@BotFather** → `/newbot` → give it any name/username. It replies with a bot token (looks like `123456789:AAg...`) — copy it.
2. Send your new bot any message (e.g. "hi") from your own Telegram account, so it has a conversation to reply into. (Bots can't message you first until you've messaged them once.)
3. Find your chat ID by visiting this URL in a browser (replace `<TOKEN>`), right after sending step 2's message:
   ```
   https://api.telegram.org/bot<TOKEN>/getUpdates
   ```
   Look for `"chat":{"id":...}` in the response — that number is your chat ID.

## 2. Store credentials in Keychain

```
security add-generic-password -s ai-content-telegram -a bot_token -w 'YOUR_BOT_TOKEN' -U
security add-generic-password -s ai-content-telegram -a chat_id -w 'YOUR_CHAT_ID' -U
```

## 3. Test it

```
python3 -c "import sys; sys.path.insert(0,'/Users/minmiller/dev/ai-content'); import telegram_lib; telegram_lib.send_message('Test message from the AI content pipeline 🚀')"
```

You should get a message from your bot. Then test the full digest manually:

```
cd ~/dev/ai-content && python3 generate_digest.py
```

Check Telegram for the digest, reply with a topic number, then run the poller manually to see it respond:

```
python3 ~/dev/ai-content/handle_telegram_reply.py
```

Once that round-trip works, the 5-minute polling schedule (already loaded) handles it automatically.

## Optional: add Reddit as a news source

Reddit blocks unauthenticated scraping now (a plain `curl` to its public `.json` endpoints gets a 403 challenge page), so this needs a free "script" app:

1. Go to reddit.com/prefs/apps (logged into your Reddit account) → "create another app..."
2. Name it anything, select **script**, redirect URI can be `http://localhost:8080` (unused, but required by the form).
3. After creating it, note the client ID (the short string under the app name) and the secret.
4. Store them in Keychain:
   ```
   security add-generic-password -s ai-content-reddit -a client_id -w 'YOUR_CLIENT_ID' -U
   security add-generic-password -s ai-content-reddit -a client_secret -w 'YOUR_SECRET' -U
   ```
5. Test it: `python3 ~/dev/ai-content/fetch_reddit.py` — should print post listings instead of the "not configured" message.

Without this, the digest just runs on Hacker News alone — already produces a solid 6-10 item digest on its own.

## arXiv, newsletters, VC blogs, publications — already working, no setup needed

- `fetch_arxiv.py` pulls recent papers from cs.AI/cs.CL/cs.LG/cs.MA — arXiv's API needs no auth. It looks back 5 days (not 1-2) because arXiv has a real submission-to-listing lag, longer over weekends.
- `fetch_rss.py` pulls from a curated `FEEDS` list — currently Import AI, Ben's Bites (newsletters), Sequoia Capital, Benedict Evans (VC), and NYT Technology, The Verge (AI), Ars Technica (publications). All verified working as of setup. Edit the `FEEDS` list in that file to match what you actually read — add anything with an RSS feed (most Substack/Beehiiv newsletters and WordPress-based blogs have one, usually at `/feed` or `/feed/`).

## Twitter/X — manual drop-in (free, works now) + optional paid API

**Manual drop-in (already active, no setup):** paste tweet/thread links into `~/dev/ai-content/twitter_inbox.md` anytime you see something interesting. Each morning's digest reads whatever's there, folds it in tagged as "Twitter/X (manual)", then archives it to `twitter_inbox_archive.md` and clears the inbox.

**Paid API (optional, for automated coverage beyond what you manually drop in):**

1. Apply for X API access at developer.x.com and subscribe to a paid tier (Basic or above — pricing changes, expect roughly $100-200/month; the free tier does not include search/read access). This is a real recurring cost, not a one-time setup fee.
2. Generate a Bearer Token for the app.
3. Store it:
   ```
   security add-generic-password -s ai-content-twitter -a bearer_token -w 'YOUR_BEARER_TOKEN' -U
   ```
4. Test it: `python3 ~/dev/ai-content/fetch_twitter.py` — should print recent tweets instead of the "not configured" message.
5. Tune what it searches for by editing `QUERIES` in `fetch_twitter.py` — currently generic AI-launch keywords; you may prefer switching to specific accounts you follow via `from:username` queries.

Without this, Twitter coverage comes entirely from your manual drop-ins, which given how you actually use Twitter is likely to surface the highest-signal items anyway.

## The backlog

`state/backlog.json` holds topics you've flagged as interesting but aren't working on today. They automatically appear at the top of the next digest (numbered first, tagged `[from backlog]`), and stay there — resurfacing every morning — until you either pick one (removing it) or leave it indefinitely. No automatic expiry; it's a small list, prune it yourself if it gets stale.

## Day to day

- Reply to the morning digest on Telegram whenever you get to it — there's no time pressure, the poller just checks every 5 minutes.
- Drop interesting tweets into `twitter_inbox.md` anytime.
- Adjust which subreddits get checked: edit `SUBREDDITS` in `fetch_reddit.py`. Adjust RSS feeds: edit `FEEDS` in `fetch_rss.py`.
- Manage the concept queue directly in `concepts.md` — add new topics under `## Queued`, reorder as you like. Covered topics move to `## Covered` automatically and are never repeated.
- Run the morning step manually instead of waiting for 7am: `bash ~/dev/ai-content/run_morning.sh`
- Change run time: edit `Hour`/`Minute` in `~/Library/LaunchAgents/com.minmiller.aicontent.plist`, then `launchctl unload`/`launchctl load` it.
- Stop entirely: `launchctl unload ~/Library/LaunchAgents/com.minmiller.aicontent.plist` and `launchctl unload ~/Library/LaunchAgents/com.minmiller.aicontent.telegrampoll.plist`

## Known fix: claude -p tool access (2026-09-09)

Every `claude -p` call here (`generate_digest.py`, `handle_telegram_reply.py`, `research_concept.sh`) had unrestricted tool access, which is meant to be pure text-in/text-out. One prompt actually triggered a Write tool attempt, silently denied and then narrated in the output. `--allowedTools ""` is a no-op (doesn't restrict anything) — the correct fix is `--disallowedTools Write Edit Bash NotebookEdit Agent WebFetch WebSearch -- "$PROMPT"`, with `--` required or the variadic tool-list flag silently swallows the prompt argument. All call sites here already use the correct form.

## Fixed 2026-09-12: real feedback was being silently lost

`get_new_messages()` used to persist the new Telegram offset immediately after fetching a batch of messages, before anything in that batch was actually processed. Telegram's offset semantics mean passing `offset=N` in a request permanently confirms everything before N *from the server's side*, regardless of whether our own processing afterward succeeds — so a crash partway through handling a message (a network timeout mid-`getUpdates`, a subprocess failure, anything) meant that message was already gone for good, un-refetchable, with nothing ever actually done about it. This is exactly what happened to a real piece of voice feedback on 2026-09-12 — confirmed by fetching `getUpdates` with no offset filter at all and getting an empty result back, meaning Telegram itself had already dropped it.

Fixed: `get_new_messages()` now returns `(update_id, text)` pairs and does **not** advance the offset for anything actionable. `handle_telegram_reply.py`'s poller confirms one update_id at a time, only after that specific message's revision/post/reply has actually completed — via `telegram_lib.write_offset()`. A failure now stops the loop and leaves the offset where it was, so the next 60-second poll retries the same message instead of skipping it. (Batches with nothing actionable at all — wrong chat, empty content — still auto-skip immediately, since there's nothing there to lose.) The poller also no longer crashes uncaught on network errors during the fetch itself; those are caught and logged, with nothing confirmed, so they're naturally retried too.

**If a message you sent seems to have vanished without a reply, it may have been lost by this exact bug before this fix — just resend it.**

## Fixed 2026-09-13: digest generation could fail silently and nobody would know

Real incident: Dario Amodei's widely-covered AI-slowdown essay (all over NYT/The Verge that morning) never appeared in the digest at all — checked the raw fetched source data and it was right there, so this wasn't a fetch gap. The actual `claude -p` digest-generation call had failed to produce parseable output that morning (never determined the exact transient cause), and `generate_digest.py` had no error handling for that case: `fresh_topics` just silently stayed an empty list, `topics = backlog_topics + fresh_topics` still had *something* in it (2 stale items from a week-old backlog), so the whole run looked completely normal — sent a digest, logged success, no error anywhere — while actually reflecting nothing about that day's real news.

Fixed: if source material was substantial (≥20 chars) but zero topics parsed back out, that's now treated as an explicit failure — logged with the claude return code, stderr, and raw output for debugging, and the Telegram message itself gets a `⚠️` banner warning that it's backlog-only and not a real reflection of the day's news, so it's never silently mistaken for a normal quiet day.

## Added 2026-09-13: major/pressing vs niche/interesting split

Each digest item is now tagged with a tier as well as a source — `🔥 MAJOR / PRESSING` for the biggest, most-covered stories (multiple sources independently covering the same thing is an explicit signal for this), `🔍 NICHE / INTERESTING` for everything else worth knowing but not mainstream-huge. Numbering stays continuous across both sections so replying with a number still works unambiguously. Format is a single bracket group (`[major/news/Source Name]`) rather than three separate bracket pairs — an earlier attempt at 3 separate brackets (`[major] [news] [Source]`) caused claude to occasionally drop one under the added complexity, breaking the parser; consolidating to one slash-delimited bracket fixed it immediately and hasn't recurred since.

## Fixed 2026-09-13: numbering didn't match display order

Numbers were assigned in construction order (backlog topics first, then fresh), but displayed in tier order (major section first, then niche) — so a digest could show Major/Pressing as items 3-4 and Niche/Interesting as 1, 2, 5, 6, which reads as broken even though the underlying data was fine. Fixed by sorting into major-then-niche order *before* numbering, so numbers now always read straight down the message top to bottom.

## Added 2026-09-13: don't repeat a story already shown

`seen_topics.py` tracks every fresh topic's URL (and title as a fallback) ever shown in a digest, in `state/seen_topics.json`. Backlog items are recorded too (even ones that predate this feature) so a story sitting in the backlog can't also get independently re-proposed as "new" in the same digest. Two layers: the digest prompt gets an explicit "already shown, don't repeat" list of titles, with instructions to judge by the *underlying story/event*, not exact text — a follow-up article, a new URL, or a differently-worded headline about the same essay/incident still counts as a repeat; plus a code-level safety-net filter drops anything with an exact URL/title match regardless of what the model does. The semantic instruction is doing most of the real work here, since a story keeps getting new URLs and rephrased headlines as coverage continues — exact matching alone couldn't catch that. Verified: after Dario Amodei's essay and 3 other stories were shown once, a second run of the same day's fetch correctly produced 4 entirely different stories instead of re-surfacing the same ones under new headlines.

## Changed 2026-09-13: cut from 8-14 items down to a hard 3-6 cap

The first version of the major/niche split (8-12 fresh items, "2-4 major") produced a genuinely overwhelming digest once backlog items stacked on top — 14 topics one run. Cut the prompt target to 3-6 total (1-3 major, 1-3 niche), and — since prompt-requested counts aren't 100% reliable and backlog adds on top regardless — also enforce a hard `MAX_TOTAL = 6` cap in code after merging backlog + fresh: backlog items are kept in full (already a curated, persistent shortlist), remaining slots fill from fresh topics sorted major-first, then everything gets renumbered consecutively. Verified: a real run landed at exactly 3 major + 3 niche = 6.

## Voice feedback setup (already done, for reference)

Transcription needs `ffmpeg` on PATH (to decode Telegram's Ogg/Opus voice files) and `mlx-whisper` (Apple Silicon on-device speech-to-text). No Homebrew on this machine, so `ffmpeg` came from the pip-bundled `imageio-ffmpeg` package instead, symlinked into `~/.local/bin/ffmpeg`:

```
pip3 install imageio-ffmpeg mlx-whisper
ln -sf "$(python3 -c 'import imageio_ffmpeg; print(imageio_ffmpeg.get_ffmpeg_exe())')" ~/.local/bin/ffmpeg
```

`transcribe.py` uses the `mlx-community/whisper-base.en-mlx` model (downloads once on first use, ~74s, then cached). Test it directly: `python3 ~/dev/ai-content/transcribe.py /path/to/audio.oga`.

## How the state machine works (for reference)

`state/news_state.json` tracks one conversation at a time: `awaiting_topic_pick` → (you reply with a number) → `awaiting_review` → (you reply "approved" or give feedback, looping until approved) → `done`. Each morning's digest overwrites this with a fresh state, so an un-answered digest from a previous day is simply superseded — no need to clean anything up.

Both this state and the daily thread's `~/dev/learning-tweet/state/thread_state.json` expire after 20 hours of inactivity for routing purposes (though the file itself is untouched) — an abandoned digest or thread from a day ago won't hijack a reply meant for something else. If both happen to be genuinely active at once, the more recently updated one wins; found and fixed this exact bug 2026-09-08 when a voice-feedback transcript happened to contain numbers that matched a stale, day-old digest still sitting in `awaiting_topic_pick`.

## Scope, on purpose

This pipeline stops at a finished script. Filming, editing, posting, and resharing across TikTok/IG/YouTube all stay manual — those platforms' posting APIs are either restricted (TikTok, Instagram require app review for a personal account) or just not worth automating yet. If that ever changes, this is the natural place to add it.
