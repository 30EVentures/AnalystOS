"""Slice 62 - the machine-facing files under site/ are generated from docs/,
current, internally consistent, and every URL they advertise resolves."""

import json
import re
import subprocess
import sys
import unittest
import xml.etree.ElementTree as ET
from pathlib import Path

from api.analyze import app

ROOT = Path(__file__).resolve().parents[1]
SITE = ROOT / "site"
BASE = "https://analystos.dev"
sys.path.insert(0, str(ROOT / "tools"))
import build_site_machine as build  # noqa: E402


def local_path(url):
    """Map a published URL to the file under site/ that serves it, or None
    for an API route."""
    assert url.startswith(BASE), url
    path = url[len(BASE):].split("#")[0] or "/"
    if path.startswith("/api/"):
        return None
    return SITE / ("index.html" if path == "/" else path.lstrip("/"))


class GeneratedFilesTest(unittest.TestCase):
    def test_every_generated_file_is_current(self):
        stale = [rel for rel, text in build.generated_files().items()
                 if not (SITE / rel).exists() or (SITE / rel).read_text(encoding="utf-8") != text]
        self.assertEqual(stale, [], "run: python3 tools/build_site_machine.py")

    def test_check_mode_runs_as_a_command_and_detects_staleness(self):
        ok = subprocess.run([sys.executable, "tools/build_site_machine.py", "--check"], cwd=ROOT, capture_output=True, text=True)
        self.assertEqual(ok.returncode, 0, ok.stdout)
        target = SITE / "docs" / "seal.md"
        original = target.read_text(encoding="utf-8")
        try:
            target.write_text(original + "\nedited\n", encoding="utf-8")
            stale = subprocess.run([sys.executable, "tools/build_site_machine.py", "--check"], cwd=ROOT, capture_output=True, text=True)
            self.assertEqual(stale.returncode, 1)
            self.assertIn("docs/seal.md", stale.stdout)
        finally:
            target.write_text(original, encoding="utf-8")

    def test_docs_are_copied_byte_for_byte(self):
        for name, _, _ in build.GUIDES:
            self.assertEqual((SITE / "docs" / name).read_bytes(), (ROOT / "docs" / name).read_bytes(), name)


class LlmsTxtTest(unittest.TestCase):
    TEXT = (SITE / "llms.txt").read_text(encoding="utf-8")

    def test_follows_the_llms_txt_shape(self):
        lines = self.TEXT.splitlines()
        self.assertEqual(lines[0], "# AnalystOS")
        self.assertTrue(lines[2].startswith("> "))
        self.assertEqual(sum(1 for l in lines if l.startswith("# ")), 1)
        self.assertGreaterEqual(sum(1 for l in lines if l.startswith("## ")), 4)

    def test_every_link_resolves_to_a_file_or_a_documented_route(self):
        urls = re.findall(r"\]\((https://analystos\.dev[^)]*)\)", self.TEXT)
        self.assertGreater(len(urls), 8)
        spec_paths = set(json.loads(app.test_client().get("/api/v1/openapi.json").get_data())["paths"])
        for url in urls:
            with self.subTest(url=url):
                path = local_path(url)
                if path is None:
                    self.assertIn(url[len(BASE):], spec_paths | {"/api/v1"})
                else:
                    self.assertTrue(path.exists(), f"{url} -> {path} is missing")

    def test_it_states_the_limits_and_the_confidentiality_line(self):
        self.assertIn("non-confidential", self.TEXT)
        self.assertIn("Limits, stated plainly", self.TEXT)

    def test_full_text_contains_every_guide(self):
        full = (SITE / "llms-full.txt").read_text(encoding="utf-8")
        for name, _, _ in build.GUIDES:
            self.assertIn(f"source: {BASE}/docs/{name}", full)
        self.assertIn("7093b80cc076808b59c1500f0cc425003408f757add4afad1963e40c8e044747", full)  # the seal test vector


class CatalogSitemapRobotsTest(unittest.TestCase):
    def test_api_catalog_is_a_valid_linkset_pointing_at_real_things(self):
        catalog = json.loads((SITE / ".well-known" / "api-catalog").read_text())
        (entry,) = catalog["linkset"]
        self.assertEqual(entry["anchor"], f"{BASE}/api/v1")
        self.assertEqual(entry["service-desc"][0]["href"], f"{BASE}/api/v1/openapi.json")
        self.assertTrue(local_path(entry["service-doc"][0]["href"]).exists())
        self.assertEqual(app.test_client().get("/api/v1/openapi.json").status_code, 200)

    def test_sitemap_is_well_formed_and_every_url_resolves(self):
        root = ET.parse(SITE / "sitemap.xml").getroot()
        urls = [e.text for e in root.iter("{http://www.sitemaps.org/schemas/sitemap/0.9}loc")]
        self.assertGreater(len(urls), 8)
        for url in urls:
            path = local_path(url)
            if path is not None:
                self.assertTrue(path.exists(), url)

    def test_robots_allows_crawlers_but_not_the_api(self):
        text = (SITE / "robots.txt").read_text()
        self.assertIn("Allow: /", text)
        self.assertIn("Disallow: /api/", text)
        self.assertIn(f"Sitemap: {BASE}/sitemap.xml", text)


class WiringTest(unittest.TestCase):
    def test_homepage_head_advertises_the_machine_entry_points(self):
        head = (SITE / "index.html").read_text(encoding="utf-8").split("</head>")[0]
        self.assertIn('rel="api-catalog" href="/.well-known/api-catalog"', head)
        self.assertIn('href="/llms.txt"', head)

    def test_vercel_serves_each_new_type_with_the_right_content_type(self):
        config = json.loads((ROOT / "vercel.json").read_text())
        types = {h["source"]: {x["key"]: x["value"] for x in h["headers"]}["Content-Type"] for h in config["headers"]}
        self.assertTrue(types["/.well-known/api-catalog"].startswith("application/linkset+json"))
        self.assertTrue(types["/docs/(.*)"].startswith("text/markdown"))
        self.assertTrue(types["/llms.txt"].startswith("text/plain"))

    def test_the_api_index_points_at_published_docs(self):
        index = app.test_client().get("/api/v1").get_json()
        for key in ("docs", "seal_spec"):
            self.assertTrue(local_path(index[key]).exists(), index[key])


class StaleDocsFixedTest(unittest.TestCase):
    def test_readme_and_architecture_no_longer_say_nothing_is_built(self):
        readme = (ROOT / "README.md").read_text()
        arch = (ROOT / "docs" / "architecture.md").read_text()
        self.assertNotIn("No third-party packages yet", readme)
        self.assertNotIn("Nothing built yet", arch)
        self.assertIn("requirements.txt", readme)
        for layer in ("L0", "L1", "L2", "L3", "L4", "L5", "L6"):
            self.assertIn(f"| {layer} ", arch)

    def test_roadmap_records_the_recent_slices(self):
        roadmap = (ROOT / "ROADMAP.md").read_text()
        for n in range(55, 63):
            self.assertIn(f"Slice {n}", roadmap)


if __name__ == "__main__":
    unittest.main()
