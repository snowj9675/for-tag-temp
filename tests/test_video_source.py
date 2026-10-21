import unittest
from video_source import normalize_path, upstream_page_url, extract_playback


class VideoSourceTests(unittest.TestCase):
    def test_legacy_path(self):
        value = "/prof-video-click/upload/cum-for-cover/hvtebdd/shy_misty_in"
        self.assertEqual(normalize_path(value), "/hvtebdd/shy_misty_in")
        self.assertEqual(upstream_page_url(value),
                         "https://www.xvideos.com/video.hvtebdd/shy_misty_in")

    def test_normalized_path(self):
        self.assertEqual(normalize_path("/hvtebdd/shy_misty_in"),
                         "/hvtebdd/shy_misty_in")
        self.assertEqual(normalize_path("/video.hvtebdd/shy_misty_in"),
                         "/hvtebdd/shy_misty_in")

    def test_reject_other_host(self):
        self.assertIsNone(normalize_path("https://example.org/video.abc/slug"))

    def test_hls_prioritized(self):
        page = """setVideoUrlHigh('https://cdn.example/a.mp4');
                  setVideoHLS('https://cdn.example/a.m3u8');"""
        self.assertEqual(extract_playback(page),
                         {"type": "hls", "url": "https://cdn.example/a.m3u8"})


if __name__ == "__main__":
    unittest.main()
