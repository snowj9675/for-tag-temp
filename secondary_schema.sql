-- Secondary Neon database ONLY (DATABASE_URL_2).
-- No foreign key to catalog database: PostgreSQL cannot enforce cross-database FK.
-- Apply after checking the source category representation.
CREATE TABLE IF NOT EXISTS public.video_categories (
  video_id BIGINT PRIMARY KEY,
  categories TEXT[] NOT NULL DEFAULT '{}'
);

CREATE TABLE IF NOT EXISTS public.channel_profiles (
  channel_name TEXT PRIMARY KEY,
  description TEXT,
  banner_url TEXT,
  avatar_url TEXT
);
-- Do not create a separate categories GIN index until category query plans justify it.
-- Do not add user history tables until accounts/consent rules are finalized.
