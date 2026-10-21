import re
import unittest
from unittest.mock import patch
import app as site

class SiteSmokeTests(unittest.TestCase):
    def setUp(self):
        site.app.testing=True
        self.client=site.app.test_client()

    def test_health(self):
        r=self.client.get("/health")
        self.assertEqual(r.status_code,200)

    def test_home(self):
        with patch.object(site,"read_query",return_value=[]):
            r=self.client.get("/")
        self.assertEqual(r.status_code,200)
        self.assertIn(b"XXX WORLD",r.data)

    def test_channel_directory_without_snapshot(self):
        r=self.client.get("/channels")
        self.assertEqual(r.status_code,200)
        self.assertIn(b"Discover channels",r.data)

    def test_robots(self):
        r=self.client.get("/robots.txt")
        self.assertEqual(r.status_code,200)
        self.assertIn(b"Sitemap:",r.data)

    def test_sitemap_index_and_shard(self):
        with patch.object(site,"read_query",side_effect=[
            [{"id":84000000}],
            [{"id":84000000}],
            [{"id":84000000,"img":"/abc/0/xv_2_t.jpg"}],
        ]):
            r=self.client.get("/sitemap.xml")
            self.assertEqual(r.status_code,200)
            self.assertIn(b"<sitemapindex",r.data)
            r=self.client.get("/sitemaps/videos-2100.xml")
            self.assertEqual(r.status_code,200)
            self.assertIn(b"<image:image>",r.data)

    def test_image_hosts(self):
        self.assertEqual(site.image_url("https://example.org/a.jpg"),"https://example.org/a.jpg")
        self.assertEqual(site.image_url("//example.org/a.jpg"),"https://example.org/a.jpg")
        self.assertTrue(site.image_url("/abc/0/img.jpg").endswith("/abc/0/img.jpg"))
        self.assertEqual(site.preview_url("/abc/0/img.jpg").split("/")[-1],"preview.mp4")

if __name__=="__main__":unittest.main()
