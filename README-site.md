# XXX World — Flask / Vercel

This repo contains both the **XXX World website** and the pre-existing keyword extraction workflows. Do not remove the Python keyword scripts or `.github/workflows/hourly-tags.yml`.

## Deploy to Vercel
Import `snowj9675/for-tag-temp` into Vercel, framework preset Other, root directory repository root. Set:
- `DATABASE_URL` — Neon PostgreSQL URL (prefer pooled connection for serverless website)
- `IMAGE_DOMAIN` — default CDN for database `img` paths without a host
- `SITE_URL` — actual canonical HTTPS site URL, e.g. `https://example.com`
- `SITE_NAME` — `XXX World`
- `PAGE_SIZE` — `36`

The website is read-only against `public.channel_videos` and uses the previously created primary-key, views, rating, channel and title-search indexes. There is **no new Neon storage or website table**. Do not add new indexes until you measure actual queries.

## Creator directory refresh
Run **Actions → Refresh public channel directory → Run workflow** once. It produces and commits `static/channels-index.json` (channel names and counts only), which is then served by Vercel. This is also scheduled weekly. It **does not** write to Neon. The one-time grouped scan can take time; never run it from a page request.

The directory is empty until the first successful snapshot. Existing `/channel/<name>` pages already work independently of the snapshot.

## SEO
- `/robots.txt`
- `/sitemap.xml` — shard index based on the maximum existing video ID; one cheap indexed query
- `/sitemaps/videos-N.xml` — bounded ID-range shards with one stored thumbnail per video as `image:image`
- `/sitemaps/channels.xml` — from static cached directory, no DB query
- `/sitemaps/pages.xml`
- Each video page has a canonical URL, Open Graph image, and honest WebPage JSON-LD.
- Search results are noindexed.
- Video-specific sitemap markup and VideoObject markup are intentionally omitted until a real player or content source and true upload dates are available. Do not invent them.
- Indexed URL count does not guarantee Google indexing. Google may choose not to index pages without unique useful playback content.

## Performance
Recent, popular, top-rated and creator video listings use keyset pagination, not OFFSET/COUNT. They can use indexes from the prior Neon migration. Home/page responses have surrogate-friendly cache headers. Channel directory search filters an in-process JSON snapshot, not Neon.

## Copyright/operations
Only publish content that you have permission to distribute. Validate external thumbnail and preview CDN access, third-party host policy, and domain verification for images in Search Console. The site has no actual video playback until you provide your player integration.


## V2: split database architecture and creator profiles

The website continues to query `DATABASE_URL` for indexed video browsing. An optional **Vercel** `DATABASE_URL_2` lets a creator page fetch one matching row from the secondary database's `public.channel_profiles` (description, banner, avatar). A failure in database 2 does not interrupt normal video browsing. Add the same second connection URL in Vercel's environment variables, not only in GitHub Actions.

### Prepare database 2

Run **Actions → Inspect both Neon databases (read-only)** first. It reports table structures and sizes from the GitHub `DATABASE_URL` and `DATABASE_URL_2` secrets without changing any records.

Then run **Actions → Initialize secondary Neon metadata schema** to create the following minimal tables **in database 2 only**:
- `video_categories(video_id BIGINT PRIMARY KEY, categories TEXT[])`
- `channel_profiles(channel_name TEXT PRIMARY KEY, description TEXT, banner_url TEXT, avatar_url TEXT)`

Neither database has foreign-key links across connection strings; `video_id` and `channel_name` are application-level join keys. Avoid deleting original category data until the exact primary-source schema is known, an idempotent migration completes, source/target totals and samples are compared, and a recoverable backup is available. There is NO destructive migration in this repository yet.

### V2 website

Video detail pages now use the same responsive hover-preview cards as the homepage for related videos, rather than tiny sidebar thumbnails. Channel pages optionally render descriptions and banners from the second database. No extra homepage SQL work is introduced.

### User history and privacy

Do **not** use IP addresses to track adult-content viewing history. IP addresses can be shared, change, and are sensitive in this context. First implement local, opt-in on-device history with a clear erase control; after accounts are designed, allow signed-in users to explicitly sync their favorites/history and provide deletion. Do not write watch activity to a global shared database by default.
