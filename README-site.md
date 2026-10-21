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
