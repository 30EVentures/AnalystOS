"""Slice 88 - the machine-readable surface of the site agrees with itself.

The audit of 2026-10-07 found a contradiction nothing tested: ``robots.txt`` said ``Disallow: /api/``
while the sitemap, llms.txt and the API catalog advertised ``/api/v1`` and ``/api/v1/openapi.json``.
This class of fault is checked here, from the files as served:

* what the site advertises (sitemap, llms.txt links, the api-catalog, the ``.well-known`` JSON, the
  homepage ``<link>`` tags, the links inside the served docs) is not disallowed by robots.txt for ``*``;
* every advertised same-site path is a file under ``site/``, a ``vercel.json`` rewrite or an ``api/``
  function, and every in-page anchor exists;
* every path in the OpenAPI document is routed;
* every markdown link in the served docs points at something that exists;
* ``vercel.json`` has a header rule (with a Content-Type) for every ``.well-known`` file.

Only GET-able things are held to robots.txt: ``POST <url>`` lines in llms.txt are an instruction to an
agent, not a link for a crawler to follow, and are checked for routing only.
"""

import json
import re
import unittest
import xml.etree.ElementTree as ET
from pathlib import Path
from urllib.parse import urlsplit

from api.analyze import app

ROOT = Path(__file__).resolve().parents[1]
SITE = ROOT / "site"
BASE = "https://analystos.dev"
VERCEL = json.loads((ROOT / "vercel.json").read_text(encoding="utf-8"))


# --- robots.txt, RFC 9309 semantics ------------------------------------------------------------------

def parse_robots(text, agent="*"):
    """The (allow, rule) pairs that apply to ``agent`` (the ``*`` group, or the group naming it)."""
    groups, current, last_was_agent = [], None, False
    for raw in text.splitlines():
        line = raw.split("#", 1)[0].strip()
        if ":" not in line:
            continue
        field, value = (part.strip() for part in line.split(":", 1))
        field = field.lower()
        if field == "user-agent":
            if not last_was_agent:
                current = {"agents": [], "rules": []}
                groups.append(current)
            current["agents"].append(value.lower())
            last_was_agent = True
            continue
        last_was_agent = False
        if field in ("allow", "disallow") and current is not None:
            current["rules"].append((field == "allow", value))
    named = [g for g in groups if agent.lower() in g["agents"]]
    chosen = named or [g for g in groups if "*" in g["agents"]]
    return [rule for g in chosen for rule in g["rules"]]


def _rule_regex(pattern):
    body = re.escape(pattern).replace(r"\*", ".*")
    return re.compile("^" + (body[:-2] + "$" if body.endswith(r"\$") else body))


def robots_allows(rules, path):
    """Longest matching rule wins; on a tie Allow wins; no match means allowed. An empty Disallow matches nothing."""
    best = None  # (length, allow)
    for allow, pattern in rules:
        if not pattern:
            continue
        if _rule_regex(pattern).match(path):
            candidate = (len(pattern), allow)
            if best is None or candidate[0] > best[0] or (candidate[0] == best[0] and allow):
                best = candidate
    return True if best is None else best[1]


# --- routing -----------------------------------------------------------------------------------------

def _source_regex(source):
    """A vercel.json ``source`` (path-to-regexp subset: ``:name`` and ``(.*)``) as a regex."""
    out, i = "", 0
    while i < len(source):
        if source.startswith("(.*)", i):
            out += ".*"
            i += 4
        elif source[i] == ":":
            j = i + 1
            while j < len(source) and (source[j].isalnum() or source[j] == "_"):
                j += 1
            out += "[^/]+"
            i = j
        else:
            out += re.escape(source[i])
            i += 1
    return re.compile("^" + out + "$")


def routed(path, _depth=0):
    """How ``path`` (no query, no fragment) is served: ``'file'``, ``'rewrite'``, ``'function'`` or ``None``."""
    if path == "/":
        return "file" if (SITE / "index.html").is_file() else None
    rel = path.strip("/")
    if (SITE / rel).is_file():
        return "file"
    if _depth < 3:
        for rule in VERCEL.get("rewrites", []):
            if _source_regex(rule["source"]).match(path):
                target = urlsplit(rule["destination"]).path
                if routed(target, _depth + 1):
                    return "rewrite"
    if rel.startswith("api/") and ((ROOT / f"{rel}.py").is_file() or (ROOT / rel / "index.py").is_file()):
        return "function"
    return None


def same_site(url):
    """The path (+ query) of a same-site absolute URL, or ``None`` for another host / not a URL."""
    parts = urlsplit(url)
    if parts.scheme in ("http", "https") and parts.netloc == "analystos.dev":
        return parts.path or "/", parts.query, parts.fragment
    return None


# --- what the site advertises ------------------------------------------------------------------------

def sitemap_urls():
    root = ET.parse(SITE / "sitemap.xml").getroot()
    return [e.text.strip() for e in root.iter("{http://www.sitemaps.org/schemas/sitemap/0.9}loc")]


def llms_links(name):
    """(url, is_get) for each markdown link, and for each ``METHOD url`` code span, in an llms file."""
    text = (SITE / name).read_text(encoding="utf-8")
    out = [(u, True) for u in re.findall(r"\]\((https?://[^)\s]+)\)", text)]
    out += [(u, False) for u in re.findall(r"`(?:POST|PUT|PATCH|DELETE) (https?://[^`\s]+)`", text)]
    return out


def json_urls(node):
    if isinstance(node, str):
        return [node] if node.startswith(("http://", "https://")) else []
    if isinstance(node, dict):
        return [u for v in node.values() for u in json_urls(v)]
    if isinstance(node, list):
        return [u for v in node for u in json_urls(v)]
    return []


def wellknown_json_files():
    return sorted([*(SITE / ".well-known").glob("*.json"), *(SITE / ".well-known").glob("api-catalog"), *SITE.glob("flashyos*.json")])


def homepage_link_urls():
    head = (SITE / "index.html").read_text(encoding="utf-8").split("</head>")[0]
    return [h if h.startswith("http") else BASE + h for h in re.findall(r'<link\b[^>]*\bhref="([^"]+)"', head) if not h.startswith("data:")
            and "fonts.g" not in h and not h.endswith((".css", ".ico", ".png", ".svg"))]


def doc_links():
    """(doc file, link target) for each markdown link in a served doc."""
    out = []
    for path in sorted((SITE / "docs").glob("*.md")):
        text = re.sub(r"```.*?```", "", path.read_text(encoding="utf-8"), flags=re.S)
        out += [(path.name, t.strip()) for t in re.findall(r"(?<!!)\[[^\]]*\]\(([^)\s]+)(?:\s+\"[^\"]*\")?\)", text)]
    return out


def advertised_get_urls():
    """{url: where it is advertised} for every absolute GET-able URL the site itself advertises."""
    found = {}
    for u in sitemap_urls():
        found.setdefault(u, "sitemap.xml")
    for name in ("llms.txt",):
        for u, is_get in llms_links(name):
            if is_get:
                found.setdefault(u, name)
    for path in wellknown_json_files():
        for u in json_urls(json.loads(path.read_text(encoding="utf-8"))):
            if same_site(u):
                found.setdefault(u, path.name)
    for u in homepage_link_urls():
        found.setdefault(u, "index.html <link>")
    for doc, target in doc_links():
        if target.startswith("http"):
            found.setdefault(target, f"docs/{doc}")
        elif not target.startswith(("#", "mailto:")):
            found.setdefault(BASE + "/docs/" + target.split("#")[0], f"docs/{doc}")
    return {u: where for u, where in found.items() if same_site(u)}


class RobotsMatcherTest(unittest.TestCase):
    """The matcher the consistency checks rely on, against the RFC 9309 examples that matter here."""

    def rules(self, text):
        return parse_robots(text)

    def test_the_old_file_contradicts_what_it_advertised(self):
        rules = self.rules("User-agent: *\nAllow: /\nDisallow: /api/\n")
        self.assertFalse(robots_allows(rules, "/api/v1/openapi.json"))
        self.assertFalse(robots_allows(rules, "/api/v1"))
        self.assertTrue(robots_allows(rules, "/docs/api.md"))

    def test_longest_match_wins_and_allow_wins_a_tie(self):
        rules = self.rules("User-agent: *\nDisallow: /api/\nAllow: /api/v1/openapi.json\nAllow: /api/v1$\n")
        self.assertTrue(robots_allows(rules, "/api/v1/openapi.json"))
        self.assertTrue(robots_allows(rules, "/api/v1"))
        self.assertFalse(robots_allows(rules, "/api/v1/analyses"))
        tie = self.rules("User-agent: *\nDisallow: /x\nAllow: /x\n")
        self.assertTrue(robots_allows(tie, "/x"))

    def test_end_anchor_and_wildcard(self):
        rules = self.rules("User-agent: *\nDisallow: /*.json$\nDisallow: /private*/\n")
        self.assertFalse(robots_allows(rules, "/a/b.json"))
        self.assertTrue(robots_allows(rules, "/a/b.json?x=1"))
        self.assertFalse(robots_allows(rules, "/private-stuff/"))

    def test_a_named_group_overrides_star_and_an_empty_disallow_allows_all(self):
        text = "User-agent: *\nDisallow: /\n\nUser-agent: goodbot\nDisallow:\n"
        self.assertFalse(robots_allows(parse_robots(text, "other"), "/a"))
        self.assertTrue(robots_allows(parse_robots(text, "goodbot"), "/a"))

    def test_no_rules_means_allowed(self):
        self.assertTrue(robots_allows(parse_robots(""), "/anything"))


class RoutingHelperTest(unittest.TestCase):
    def test_known_routes_resolve_and_unknown_ones_do_not(self):
        self.assertEqual(routed("/"), "file")
        self.assertEqual(routed("/upload.html"), "file")
        self.assertEqual(routed("/.well-known/api-catalog"), "file")
        self.assertEqual(routed("/api/v1"), "function")
        self.assertEqual(routed("/api/v1/openapi.json"), "rewrite")
        self.assertEqual(routed("/api/v1/reports/abc"), "rewrite")
        self.assertIsNone(routed("/nope.html"))
        self.assertIsNone(routed("/api/v1/nope"))
        self.assertIsNone(routed("/docs/missing.md"))


class RobotsAgreesWithWhatTheSiteAdvertisesTest(unittest.TestCase):
    RULES = parse_robots((SITE / "robots.txt").read_text(encoding="utf-8"))

    def test_the_advertised_set_is_not_vacuous(self):
        advertised = advertised_get_urls()
        self.assertGreater(len(advertised), 12)
        self.assertIn(f"{BASE}/api/v1/openapi.json", advertised)
        self.assertIn(f"{BASE}/api/v1", advertised)
        self.assertGreater(len(self.RULES), 0, "robots.txt has no rules for *")

    def test_nothing_the_site_advertises_is_disallowed_by_its_own_robots_txt(self):
        blocked = []
        for url, where in sorted(advertised_get_urls().items()):
            path, query, _ = same_site(url)
            if not robots_allows(self.RULES, path + ("?" + query if query else "")):
                blocked.append(f"{url} (advertised in {where})")
        self.assertEqual(blocked, [], "robots.txt disallows what the site tells agents to fetch")

    def test_the_rest_of_the_api_stays_disallowed_for_crawlers(self):
        for path in ("/api/v1/analyses", "/api/v1/verify", "/api/analyze"):
            self.assertFalse(robots_allows(self.RULES, path), path)

    def test_the_sitemap_is_declared_and_robots_is_a_plain_ascii_file(self):
        text = (SITE / "robots.txt").read_text(encoding="utf-8")
        self.assertIn(f"Sitemap: {BASE}/sitemap.xml", text)
        text.encode("ascii")


class AdvertisedPathsExistTest(unittest.TestCase):
    def test_every_advertised_same_site_path_is_served_by_something(self):
        urls = dict(advertised_get_urls())
        for name in ("llms.txt",):
            for u, is_get in llms_links(name):
                if same_site(u):
                    urls.setdefault(u, name)
        missing = []
        for url, where in sorted(urls.items()):
            path, _, _ = same_site(url)
            if routed(path) is None:
                missing.append(f"{url} (advertised in {where})")
        self.assertEqual(missing, [])

    def test_every_in_page_anchor_exists(self):
        index = (SITE / "index.html").read_text(encoding="utf-8")
        checked = 0
        for url, where in advertised_get_urls().items():
            path, _, fragment = same_site(url)
            if fragment and path == "/":
                checked += 1
                self.assertRegex(index, rf'id="{re.escape(fragment)}"', f"{url} (advertised in {where})")
        self.assertGreater(checked, 0, "llms.txt links to /#trust; this check must see it")

    def test_the_sitemap_has_no_duplicates_and_only_this_host(self):
        urls = sitemap_urls()
        self.assertEqual(len(urls), len(set(urls)))
        for u in urls:
            self.assertTrue(u.startswith(BASE + "/"), u)

    def test_post_instructions_in_llms_txt_are_routed(self):
        posts = [u for u, is_get in llms_links("llms.txt") if not is_get]
        self.assertTrue(posts, "llms.txt names a POST endpoint")
        for u in posts:
            self.assertIsNotNone(routed(same_site(u)[0]), u)


class OpenApiPathsAreRoutedTest(unittest.TestCase):
    def test_every_path_in_the_openapi_document_is_routed(self):
        spec = json.loads(app.test_client().get("/api/v1/openapi.json").get_data())
        paths = sorted(spec["paths"])
        self.assertGreater(len(paths), 5)
        unrouted = [p for p in paths if routed(re.sub(r"\{[^}]+\}", "x", p)) is None]
        self.assertEqual(unrouted, [])

    def test_the_openapi_server_is_this_site(self):
        spec = json.loads(app.test_client().get("/api/v1/openapi.json").get_data())
        for server in spec.get("servers", []):
            self.assertTrue(server["url"].startswith(BASE) or server["url"].startswith("/"), server)


class ServedDocsLinksTest(unittest.TestCase):
    def test_every_markdown_link_in_the_served_docs_resolves(self):
        links = doc_links()
        self.assertGreater(len(links), 3)
        broken = []
        for doc, target in links:
            if target.startswith(("http://", "https://")):
                site = same_site(target)
                if site and routed(site[0]) is None:
                    broken.append((doc, target))
            elif target.startswith(("mailto:",)):
                continue
            elif target.startswith("#"):
                text = (SITE / "docs" / doc).read_text(encoding="utf-8").lower()
                slug = target[1:].lower()
                headings = {re.sub(r"[^a-z0-9 -]", "", h.lower()).strip().replace(" ", "-") for h in re.findall(r"^#+\s+(.*)$", text, flags=re.M)}
                if slug not in headings:
                    broken.append((doc, target))
            else:
                path = (SITE / "docs" / target.split("#")[0]).resolve()
                if not path.is_file() or SITE.resolve() not in path.parents:
                    broken.append((doc, target))
        self.assertEqual(broken, [])

    def test_the_full_text_file_links_only_to_things_that_exist(self):
        text = (SITE / "llms-full.txt").read_text(encoding="utf-8")
        bad = [u for u in set(re.findall(r"\]\((https://analystos\.dev[^)\s]*)\)", text)) if routed(same_site(u)[0]) is None]
        self.assertEqual(bad, [])


class HeaderRulesCoverEveryWellKnownFileTest(unittest.TestCase):
    RULES = [(_source_regex(h["source"]), {x["key"].lower(): x["value"] for x in h["headers"]}) for h in VERCEL["headers"]]

    def headers_for(self, path):
        merged = {}
        for regex, headers in self.RULES:
            if regex.match(path):
                merged.update(headers)
        return merged

    def test_every_well_known_file_has_a_content_type_rule(self):
        files = sorted(p for p in (SITE / ".well-known").iterdir() if p.is_file())
        self.assertGreaterEqual(len(files), 3)
        for file in files:
            with self.subTest(file=file.name):
                headers = self.headers_for("/.well-known/" + file.name)
                self.assertIn("content-type", headers, f"vercel.json has no Content-Type rule for /.well-known/{file.name}")
                if file.suffix == ".json":
                    self.assertIn("json", headers["content-type"])
                self.assertEqual(headers.get("access-control-allow-origin"), "*", "agents fetch these cross-origin")

    def test_other_machine_files_are_covered_too(self):
        for path in ("/flashyos.roles.json", "/llms.txt", "/llms-full.txt", "/docs/api.md"):
            with self.subTest(path=path):
                self.assertIn("content-type", self.headers_for(path))

    def test_every_header_rule_names_a_file_that_exists_or_a_pattern(self):
        for header in VERCEL["headers"]:
            source = header["source"]
            if "(" in source or ":" in source:
                continue
            self.assertTrue((SITE / source.strip("/")).is_file() or "analystos-seal-key" in source,
                            f"{source} has header rules but no file (the seal key file is published later, Slice 86)")


if __name__ == "__main__":
    unittest.main()
