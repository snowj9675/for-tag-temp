import { Pool } from "pg";
import { attachDatabasePool } from "@neon/functions";

const pool = new Pool({ connectionString: process.env.DATABASE_URL, max: 3 });
attachDatabasePool(pool);
const HOST = "https://www.xvideos.com";
const codePattern = /^[a-z0-9]+$/i;
const slugPattern = /^[a-z0-9_-]+$/i;

function watchUrl(raw: string): string | null {
  let path = raw.trim();
  if (/^https?:\/\//i.test(path)) {
    try {
      const u = new URL(path);
      if (!["xvideos.com", "www.xvideos.com"].includes(u.hostname)) return null;
      path = u.pathname;
    } catch { return null; }
  }
  path = path.split("?")[0].replace(/\/$/, "");
  if (path.startsWith("/prof-video-click/upload/")) {
    const p = path.split("/");
    path = "/" + p.slice(-2).join("/");
  }
  const match = path.match(/^\/(?:video\.)?([^/]+)\/([^/]+)$/);
  if (!match || !codePattern.test(match[1]) || !slugPattern.test(match[2])) return null;
  return `${HOST}/video.${match[1]}/${match[2]}`;
}
function decode(source: string): string | null {
  const value = source.replace(/\\\//g, "/").replace(/\\u0026/gi, "&").replace(/&amp;/g, "&");
  try {
    const url = new URL(value.startsWith("//") ? "https:" + value : value);
    return url.protocol === "https:" ? url.toString() : null;
  } catch { return null; }
}
function sourceFromHtml(html: string) {
  const candidates: Array<["hls" | "mp4", RegExp]> = [
    ["hls", /setVideoHLS\s*\(\s*["']([^"']+)["']/i],
    ["mp4", /setVideoUrlHigh\s*\(\s*["']([^"']+)["']/i],
    ["mp4", /setVideoUrlLow\s*\(\s*["']([^"']+)["']/i],
  ];
  for (const [type, regex] of candidates) {
    const match = html.match(regex);
    if (match) {
      const url = decode(match[1]);
      if (url) return { type, url };
    }
  }
  return null;
}
function json(value: unknown, status = 200) {
  return new Response(JSON.stringify(value), {
    status, headers: { "Content-Type": "application/json", "Cache-Control": "no-store" },
  });
}
export default {
  async fetch(req: Request): Promise<Response> {
    if (req.method !== "GET") return json({ error: "Method not allowed" }, 405);
    const secret = process.env.SOURCE_API_TOKEN;
    if (!secret || req.headers.get("Authorization") !== `Bearer ${secret}`) {
      return json({ error: "Unauthorized" }, 401);
    }
    const id = new URL(req.url).searchParams.get("id");
    if (!id || !/^\d{1,19}$/.test(id)) return json({ error: "Invalid video id" }, 400);
    try {
      const result = await pool.query("SELECT url FROM public.channel_videos WHERE id=$1 LIMIT 1", [id]);
      if (!result.rows.length) return json({ error: "Video not found" }, 404);
      const target = watchUrl(String(result.rows[0].url || ""));
      if (!target) return json({ error: "Invalid stored video path" }, 422);
      const controller = new AbortController();
      const timer = setTimeout(() => controller.abort(), 9000);
      let response: Response;
      try {
        response = await fetch(target, {
          redirect: "manual", signal: controller.signal,
          headers: { "User-Agent": "Mozilla/5.0" },
        });
      } finally { clearTimeout(timer); }
      if (!response.ok) return json({ error: "Upstream returned an error" }, 502);
      const content = await response.text();
      if (content.length > 3_000_000) return json({ error: "Unexpected upstream page size" }, 502);
      const source = sourceFromHtml(content);
      if (!source) return json({ error: "HLS / MP4 source not found" }, 404);
      return json(source);
    } catch {
      return json({ error: "Source resolution failed" }, 502);
    }
  },
};
