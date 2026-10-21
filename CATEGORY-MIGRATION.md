# Category migration into secondary Neon

## What the audit confirms
Primary \`public.channel_videos\` contains 10 columns: id, url, title, img, rating, rating_percentage, views, duration, channel_name, tags. There is **no category field** in that table and no other primary user table was reported. Therefore 147,000 category assignments cannot be automatically copied from that database.

## Prepare database 2
1. GitHub Actions -> **Initialize secondary Neon metadata schema** -> Run workflow.
2. Inspect the workflow log for success. This creates \`video_categories\` and \`channel_profiles\` in DATABASE_URL_2 only; it does not touch DATABASE_URL.
3. Add \`DATABASE_URL_2\` to Vercel only if channel profiles should be displayed there.

## Bring the original category source
Use \`import_categories.py\` from Colab or a machine that can access your original category source. Supported formats:
- CSV: columns \`video_id,categories\` e.g. \`87499409,"Category A,Category B"\`
- JSONL: one object per line e.g. \`{"video_id":87499409,"categories":["Category A","Category B"]}\`
- JSON: array with the same objects. JSONL preferred for large sources.
- Column \`id\` is also accepted instead of \`video_id\`; \`category\` also accepted instead of \`categories\`.

Example Colab usage:
\`\`\`python
%pip -q install "psycopg[binary]>=3.2,<4"
import os
from getpass import getpass
os.environ["DATABASE_URL_2"]=getpass("Neon DB2 connection string: ")
!python import_categories.py --input /content/categories.jsonl --limit 1000
!python import_categories.py --input /content/categories.jsonl
\`\`\`

Importer does not read or modify primary Neon, streams CSV/JSONL, writes DB2 in committed batches, skips invalid/empty categories, deduplicates repeated category names, and is safe to rerun by \`video_id\` (upserts changed categories). A batch failing rolls back that batch only.

Validate with:
\`\`\`sql
SELECT COUNT(*) AS categorized_videos,
       SUM(cardinality(categories)) AS total_category_assignments
FROM public.video_categories;
SELECT * FROM public.video_categories ORDER BY video_id LIMIT 10;
\`\`\`

No deletion of original data is part of this workflow. Source cleanup should only be considered after the origin of those category assignments has been established, record counts and samples match, a backup is retained, and enough free database space exists for maintenance. On a nearly-full Postgres database, DELETE or large UPDATE can initially increase storage and WAL, and won't necessarily reduce billed size immediately.

For ongoing category extraction, direct new category outputs into DB2 by upserting \`(video_id, categories)\`. No cross-database foreign key exists. Database 1 keeps the existing \`channel_name\`; Database 2 holds optional channel profiles and future metadata.
