"""On-demand extraction from a known, fixed upstream host. No arbitrary URL fetching."""
import html
import re
from urllib.parse import urlsplit
import requests

UPSTREAM = "https://www.xvideos.com"
PATTERN = re.compile(r"^/(?:video\.)?([a-z0-9]+)/([A-Za-z0-9_-]+)$", re.I)
HLS_PATTERNS = [
    re.compile(r"setVideoHLS\s*\(\s*['\"]([^'\"]+)['\"]", re.I),
    re.compile(r'["\'](?:hls|hls_url|hlsUrl|videoHLS)["\']\s*:\s*["\']([^"\']+)', re.I),
]
MP4_PATTERNS = [
    re.compile(r"setVideoUrlHigh\s*\(\s*['\"]([^'\"]+)['\"]", re.I),
    re.compile(r"setVideoUrlLow\s*\(\s*['\"]([^'\"]+)['\"]", re.I),
]


def normalize_path(value):
    """Convert legacy /prof-video-click/upload/.../id/slug to /id/slug.

    Supports the already normalized /id/slug and /video.id/slug forms.
    """
    if not value:
        return None
    value = str(value).strip()
    if value.startswith(("http://", "https://")):
        parsed = urlsplit(value)
        if parsed.hostname not in ("xvideos.com", "www.xvideos.com"):
            return None
        value = parsed.path
    else:
        value = value.split("?", 1)[0].split("#", 1)[0]
    value = value.rstrip("/")
    if value.startswith("/prof-video-click/upload/"):
        pieces = value.split("/")
        if len(pieces) < 6:
            return None
        value = "/" + "/".join(pieces[-2:])
    match = PATTERN.fullmatch(value)
    if not match:
        return None
    return "/" + match.group(1) + "/" + match.group(2)


def upstream_page_url(value):
    path = normalize_path(value)
    if not path:
        return None
    return UPSTREAM + "/video." + path[1:]


def _clean(candidate):
    # URLs may be escaped in a JavaScript string or JSON-encoded page data.
    candidate = html.unescape(candidate).replace("\\/", "/").replace("\\u0026", "&")
    if candidate.startswith("//"):
        candidate = "https:" + candidate
    parsed = urlsplit(candidate)
    if parsed.scheme != "https" or not parsed.hostname:
        return None
    return candidate


def extract_playback(page):
    for patterns, label in ((HLS_PATTERNS, "hls"), (MP4_PATTERNS, "mp4")):
        for pattern in patterns:
            for match in pattern.finditer(page):
                url = _clean(match.group(1))
                if url:
                    return {"type": label, "url": url}
    return None


def resolve_playback(value):
    page_url = upstream_page_url(value)
    if not page_url:
        raise ValueError("Invalid stored video path")
    response = requests.get(
        page_url,
        headers={"User-Agent": "Mozilla/5.0 (compatible; SiteVideoResolver/1.0)"},
        timeout=(4, 9), allow_redirects=False,
    )
    response.raise_for_status()
    result = extract_playback(response.text)
    if not result:
        raise LookupError("No supported video source found in upstream HTML")
    return result
