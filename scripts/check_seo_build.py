"""Fail the static build if verified pages or sitemap links are missing."""
from __future__ import annotations

import json
import re
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import urlparse
from xml.etree import ElementTree

ROOT = Path(__file__).resolve().parent.parent
DIST = ROOT / "dist"
BASE = "/compatigo_app/"
SITE = "https://trexdbg.github.io"
OFFICIAL = {"manufacturer_product_page", "manufacturer_manual", "manufacturer_support", "manufacturer_catalog"}


def slug(text: str) -> str:
    import unicodedata
    text = "".join(c for c in unicodedata.normalize("NFD", text) if not unicodedata.combining(c))
    return re.sub(r"(^-|-$)", "", re.sub(r"[^a-z0-9]+", "-", text.lower()))


def eligible(device: dict) -> bool:
    return bool(
        device.get("verified")
        and device.get("brand")
        and device.get("model")
        and any(
            part.get("status") == "verified"
            and any(
                evidence.get("explicit_relation") is True
                and evidence.get("source_kind") in OFFICIAL
                for evidence in part.get("evidence", [])
            )
            for part in device.get("parts", [])
        )
    )


class PageParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.canonicals = []
        self.scripts = []
        self.links = []
        self.h1s = 0
        self._in_json = False

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if tag == "link" and attrs.get("rel") == "canonical":
            self.canonicals.append(attrs.get("href"))
        if tag == "a" and attrs.get("href"):
            self.links.append(attrs["href"])
        if tag == "h1":
            self.h1s += 1
        if tag == "script" and attrs.get("type") == "application/ld+json":
            self._in_json = True

    def handle_data(self, data):
        if self._in_json and data.strip():
            self.scripts.append(json.loads(data))

    def handle_endtag(self, tag):
        if tag == "script":
            self._in_json = False


def main() -> None:
    catalog = json.loads((ROOT / "public/data/catalog.json").read_text(encoding="utf-8"))
    devices = [d for d in catalog["devices"] if eligible(d)]
    brands = sorted(set(d["brand"] for d in devices))
    expected_routes = [BASE, BASE + "appareils/"]
    expected_routes += [BASE + "marques/" + slug(brand) + "/" for brand in brands]
    expected_routes += [BASE + slug(d["brand"]) + "/" + slug(d["model"]) + "/" for d in devices]
    if len(expected_routes) != len(set(expected_routes)):
        raise AssertionError("Duplicate page routes")

    tree = ElementTree.parse(DIST / "sitemap.xml")
    locs = [e.text for e in tree.findall(".//{http://www.sitemaps.org/schemas/sitemap/0.9}loc")]
    expected_urls = {SITE + path for path in expected_routes}
    if set(locs) != expected_urls or len(locs) != len(expected_urls):
        missing, extra = expected_urls - set(locs), set(locs) - expected_urls
        raise AssertionError(f"Sitemap mismatch, missing={sorted(missing)[:4]}, extra={sorted(extra)[:4]}")

    for url in locs:
        parsed = urlparse(url)
        assert parsed.scheme == "https" and parsed.netloc == "trexdbg.github.io", url
        assert parsed.path.startswith(BASE), url
        relative = parsed.path.removeprefix(BASE).strip("/")
        html_path = DIST / relative / "index.html" if relative else DIST / "index.html"
        if not html_path.is_file():
            raise AssertionError(f"Missing static HTML for {url} at {html_path}")
        html = html_path.read_text(encoding="utf-8")
        parser = PageParser()
        parser.feed(html)
        if parser.canonicals != [url]:
            raise AssertionError(f"Wrong canonical for {url}: {parser.canonicals}")
        if parser.h1s != 1:
            raise AssertionError(f"Expected one H1 at {url}: {parser.h1s}")

        if relative and relative != "appareils" and not relative.startswith("marques/"):
            if not parser.scripts:
                raise AssertionError(f"Missing JSON-LD for device {url}")
            graph = parser.scripts[0].get("@graph", [])
            if not any(item.get("@type") == "WebPage" and
                       item.get("about", {}).get("@type") == "Product" for item in graph):
                raise AssertionError(f"Missing product structured data for {url}")
            if "Vérifier chez le fabricant" not in html:
                raise AssertionError(f"Missing visible manufacturer proof at {url}")

    robots = (DIST / "robots.txt").read_text(encoding="utf-8")
    if "Sitemap: " + SITE + BASE + "sitemap.xml" not in robots:
        raise AssertionError("robots.txt does not reference the production sitemap")

    print(f"SEO build validated: {len(devices)} device pages, {len(brands)} brand pages, {len(locs)} sitemap URLs")


if __name__ == "__main__":
    main()
