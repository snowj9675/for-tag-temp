-- Primary catalog DB only. Review preview before running UPDATE.
-- Converts ONLY known /prof-video-click/upload/.../<id>/<slug> paths.
-- Does not touch URLs of a different shape or already normalized paths.
-- Preview:
SELECT id, url AS old_url,
       regexp_replace(
           url,
           '^/prof-video-click/upload/(?:[^/]+/)*([A-Za-z0-9]+)/([A-Za-z0-9_-]+)/?$',
           '/\\1/\\2'
       ) AS new_url
FROM public.channel_videos
WHERE url ~ '^/prof-video-click/upload/(?:[^/]+/)*[A-Za-z0-9]+/[A-Za-z0-9_-]+/?$'
ORDER BY id DESC
LIMIT 50;

-- Recommended: take a Neon restore point / branch before this bulk update.
-- Run separately after reviewing preview, in a transaction:
-- BEGIN;
-- UPDATE public.channel_videos
-- SET url = regexp_replace(
--     url,
--     '^/prof-video-click/upload/(?:[^/]+/)*([A-Za-z0-9]+)/([A-Za-z0-9_-]+)/?$',
--     '/\\1/\\2'
-- )
-- WHERE url ~ '^/prof-video-click/upload/(?:[^/]+/)*[A-Za-z0-9]+/[A-Za-z0-9_-]+/?$';
-- COMMIT;
