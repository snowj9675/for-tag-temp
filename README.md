# Neon video keywords: smoke test

**This workflow is read-only.** It fetches up to 20 video URLs from `public.channel_videos` and extracts HTML `video:tag` and `keywords` metadata. It does **not** update Neon or run against the complete catalog.

## Setup
1. Repository **Settings → Secrets and variables → Actions → New repository secret**.
2. Create `DATABASE_URL` containing your Neon Postgres connection string (ideally a read-only role).
3. Open **Actions → Test video keyword extraction → Run workflow**, sample `5`, workers `3`.
4. Inspect the job logs for tag counts/sample values. Download the short-lived `keyword-test-results` artifact for complete records.

The script only queries `id, url` from `public.channel_videos` (the schema defined during your import). Relative URLs are restored using `https://www.xvideos.com`. It accepts a full URL or Markdown-formatted URL too.

A successful run requires at least one page to yield keywords. A failed run may mean HTTP blocking, missing meta tags, or site changes; inspect the status/errors before considering a full backfill.

For production: add a `tags TEXT[]` field or a normalized `video_tags` relation with appropriate GIN indexes, then implement bounded queues, durable checkpoints, upserts, and retries. Do not enable a 1.8M page crawl until this test and permitted access are verified.
