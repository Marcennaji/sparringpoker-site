from contextlib import redirect_stderr, redirect_stdout
from io import StringIO
import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import call, patch
from urllib.error import HTTPError, URLError

import indexnow


class IndexNowTests(unittest.TestCase):
    def setUp(self):
        temporary = TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.key = self.root / "example-key123.txt"
        self.key.write_text(self.key.stem, encoding="utf-8")

    def run_cli(self, *args):
        stdout, stderr = StringIO(), StringIO()
        with patch.object(indexnow, "ROOT", self.root), redirect_stdout(stdout), redirect_stderr(stderr):
            status = indexnow.main(list(args))
        return status, stdout.getvalue(), stderr.getvalue()

    def test_sitemap_parsing(self):
        (self.root / "sitemap.xml").write_text(
            '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">'
            '<url><loc>https://sparringpoker.com/</loc></url>'
            '<url><loc>https://sparringpoker.com/articles/offline.html</loc></url>'
            '</urlset>',
            encoding="utf-8",
        )
        self.assertEqual(indexnow.sitemap_urls(self.root), [
            "https://sparringpoker.com/", "https://sparringpoker.com/articles/offline.html",
        ])

    def test_key_detection(self):
        (self.root / "some-other.txt").write_bytes(b"unrelated\xff")
        self.assertEqual(indexnow.find_key(self.root), self.key)
        self.key.write_text("different key", encoding="utf-8")
        with self.assertRaisesRegex(ValueError, "found 0"):
            indexnow.find_key(self.root)

    def test_ambiguous_key_detection(self):
        (self.root / "second-key.txt").write_text("second-key\n", encoding="utf-8")
        with self.assertRaisesRegex(ValueError, "found 2"):
            indexnow.find_key(self.root)

    def test_paths_to_public_urls(self):
        for path, expected in {
            "index.html": "/",
            "articles/index.html": "/articles/",
            "articles/Pratique du pokér.html": "/articles/Pratique%20du%20pok%C3%A9r.html",
        }.items():
            with self.subTest(path=path):
                self.assertEqual(indexnow.page_url(path), f"https://sparringpoker.com{expected}")

    def test_committed_changes(self):
        revision = "a" * 40
        diff = (
            "A\0articles/new.html\0M\0index.html\0R100\0articles/old.html\0articles/renamed.html\0"
            "D\0removed.html\0M\0assets/site.css\0M\0assets/site.js\0M\0flag_en.png\0"
            "M\0docs/guide.html\0A\0scripts/example.html\0D\0app-doc/example.html\0"
            "M\0.github/example.html\0M\0sitemap.xml\0M\0robots.txt\0M\0assets/README.md\0"
        ).encode("utf-8")
        with patch.object(indexnow, "git", side_effect=[f"{revision}\n".encode("ascii"), diff]) as git:
            urls, assets = indexnow.changed_urls(self.root, "HEAD~1")
        self.assertEqual(git.call_args_list, [
            call(self.root, "rev-parse", "--verify", "--end-of-options", "HEAD~1^{commit}"),
            call(self.root, "diff", "--no-ext-diff", "--name-status", "-z", "--find-renames",
                 "--diff-filter=ADMRT", revision, "HEAD", "--"),
        ])
        self.assertEqual(urls, [
            "https://sparringpoker.com/", "https://sparringpoker.com/articles/new.html",
            "https://sparringpoker.com/articles/old.html", "https://sparringpoker.com/articles/renamed.html",
            "https://sparringpoker.com/removed.html",
        ])
        self.assertEqual(assets, ["assets/site.css", "assets/site.js", "flag_en.png"])

    def test_invalid_urls_are_rejected(self):
        for url in (
            "https://example.org/", "https://sparringpoker.com.example.org/", "https://www.sparringpoker.com/",
            "https://external.example@sparringpoker.com/", "https://sparringpoker.com:8443/",
            "https://sparringpoker.com/bad space.html", "https://sparringpoker.com/bad%ZZ.html",
            "https://sparringpoker.com/faq.html#section", "/faq.html",
        ):
            with self.subTest(url=url), patch.object(indexnow, "build_opener") as opener:
                status, _, stderr = self.run_cli("--url", url)
                self.assertNotEqual(status, 0)
                self.assertIn("Error", stderr)
                opener.assert_not_called()

    def test_no_change_and_asset_only_behavior(self):
        self.key.unlink()
        for assets in ([], ["assets/site.css"]):
            with self.subTest(assets=assets), patch.object(indexnow, "build_opener") as opener:
                with patch.object(indexnow, "changed_urls", return_value=([], assets)):
                    status, stdout, stderr = self.run_cli("--since", "HEAD")
                    self.assertEqual(status, 0)
                    self.assertIn("No relevant HTML changes", stdout)
                    if assets:
                        self.assertIn("assets/site.css", stderr)
                        self.assertIn("--all", stderr)
                    opener.assert_not_called()

    def test_no_arguments_shows_help(self):
        with patch.object(indexnow, "build_opener") as opener:
            status, stdout, _ = self.run_cli()
        self.assertEqual(status, 0)
        self.assertIn("usage:", stdout)
        opener.assert_not_called()

    def test_dry_run_and_deduplication(self):
        with patch.object(indexnow, "build_opener") as opener:
            status, stdout, _ = self.run_cli(
                "--url", "https://sparringpoker.com/faq.html", "https://sparringpoker.com/support.html",
                "--url", "https://SPARRINGPOKER.COM/faq.html", "--dry-run",
            )
        self.assertEqual(status, 0)
        opener.assert_not_called()
        self.assertIn("POST https://api.indexnow.org/indexnow", stdout)
        self.assertEqual(json.loads(stdout[stdout.index("{"):]), {
            "host": "sparringpoker.com",
            "key": self.key.stem,
            "keyLocation": f"https://sparringpoker.com/{self.key.name}",
            "urlList": ["https://sparringpoker.com/faq.html", "https://sparringpoker.com/support.html"],
        })

    def test_http_statuses_and_post_request(self):
        for http_status, status_code, message in (
            (200, 0, "Submission successful"), (202, 0, "Key validation is pending"),
            (400, 1, "Invalid request format"), (403, 1, "Key validation failed"),
            (422, 1, "do not belong to the host"), (429, 1, "Too many requests"),
            (302, 1, "Unexpected response"), (503, 1, "Unexpected response"),
        ):
            with self.subTest(http_status=http_status), patch.object(indexnow, "build_opener") as opener:
                send = opener.return_value.open
                if status_code:
                    send.side_effect = HTTPError(indexnow.ENDPOINT, http_status, "error", None, None)
                else:
                    send.return_value.__enter__.return_value.status = http_status
                status, stdout, stderr = self.run_cli("--url", "https://sparringpoker.com/faq.html")
                self.assertEqual(status, status_code)
                self.assertIn(f"HTTP {http_status}", stderr if status_code else stdout)
                self.assertIn(message, stderr if status_code else stdout)
                if not status_code:
                    self.assertIn("Indexing is not guaranteed", stdout)

                send.assert_called_once()
                request = send.call_args.args[0]
                self.assertEqual(send.call_args.kwargs, {"timeout": 15})
                self.assertIsNone(opener.call_args.args[0].redirect_request(None, None, 302, None, None, None))
                self.assertEqual(request.full_url, "https://api.indexnow.org/indexnow")
                self.assertEqual(request.get_method(), "POST")
                self.assertEqual(request.get_header("Content-type"), "application/json; charset=utf-8")
                self.assertEqual(json.loads(request.data)["urlList"], ["https://sparringpoker.com/faq.html"])

    def test_network_failure(self):
        with patch.object(indexnow, "build_opener") as opener:
            send = opener.return_value.open
            send.side_effect = URLError(TimeoutError("timed out"))
            status, _, stderr = self.run_cli("--url", "https://sparringpoker.com/faq.html")
        self.assertEqual(status, 1)
        self.assertIn("timed out", stderr)
        send.assert_called_once()


if __name__ == "__main__":
    unittest.main()
