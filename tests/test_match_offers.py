"""Safety and matching regressions: python -m unittest discover -s tests -v."""
from datetime import datetime, timezone, timedelta
import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from match_offers import build, part_key, safe_https_url

NOW = datetime(2026, 10, 8, tzinfo=timezone.utc)


def row(**overrides):
    payload = {
        "network": "DemoNetwork", "merchant": "Demo Merchant", "brand": "Rowenta",
        "manufacturer_part_number": "ZR903701", "title": "Pièce technique ZR903701",
        "product_url": "https://merchant.example/products/903701",
        "affiliate_url": "https://tracker.example/track?id=123",
        "price_eur": "14,99", "currency": "EUR", "availability": "in_stock",
        "checked_at": NOW.isoformat(),
    }
    payload.update(overrides)
    return payload


class MatcherTests(unittest.TestCase):
    def setUp(self):
        self.temp = TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.catalog = self.root / "catalog.json"
        self.feed = self.root / "merchant.json"
        self.catalog.write_text(json.dumps({
            "schema_version": 1, "status": "verified_catalog", "devices": [
                {"brand": "Rowenta", "model": "RO7640EA", "verified": true, "parts": [{
                    "manufacturer_part_number": "ZR903701", "status": "verified",
                    "evidence": [{"source_url": "https://rowenta.fr/parts/903701", "source_kind": "manufacturer_product_page", "explicit_relation": true}]}
                ]},
                {"brand": "Other", "model": "X1", "verified": true, "parts": [{
                    "manufacturer_part_number": "ZR903701", "status": "verified",
                    "evidence": [{"source_url": "https://example.org/x1", "source_kind": "manufacturer_support", "explicit_relation": true}]}
                ]},
                {"brand": "Rowenta", "model": "RO2957EA", "verified": true, "parts": [{
                    "manufacturer_part_number": "ZR904301", "status": "unverified",
                    "evidence": [{"source_url": "https://rowenta.fr/part"}]}
                ]},
            ]
        }), encoding="utf-8")

    def run_match(self, offers):
        self.feed.write_text(json.dumps({"offers": offers}), encoding="utf-8")
        return build(self.catalog, [self.feed], NOW, 7)

    def test_exact_brand_part_match_only(self):
        preview, report = self.run_match([
            row(), row(brand="OTHER"), row(brand="Philips"),
            row(manufacturer_part_number="ZR904301"),
            row(manufacturer_part_number="ZR90370", title="ZR903701"),
        ])
        self.assertEqual(len(preview["offers"]), 2)
        self.assertEqual(report["rejected_by_reason"]["no_exact_catalog_match"], 3)
        self.assertEqual(report["matched_device_rows"], 2)
        self.assertFalse(report["public_links_enabled"])

    def test_normalization_and_duplicate(self):
        preview, report = self.run_match([row(manufacturer_part_number="zr-903701"), row()])
        self.assertEqual(len(preview["offers"]), 1)
        self.assertEqual(report["rejected_by_reason"]["duplicate_offer"], 1)
        self.assertEqual(part_key("ZR 903701"), "ZR903701")
        self.assertEqual(part_key("ZR9037/01"), "")
        self.assertEqual(part_key("MOUSSE"), "")

    def test_invalid_and_unsafe_urls_rejected(self):
        preview, report = self.run_match([
            row(product_url="http://merchant.example/p"),
            row(product_url="https://localhost/test"),
            row(affiliate_url="https://127.0.0.1/p"),
            row(affiliate_url="javascript:alert(1)"),
            row(product_url="https://user:pass@merchant.example/p"),
        ])
        self.assertEqual(preview["offers"], [])
        self.assertEqual(report["rejected_by_reason"]["unsafe_url"], 5)
        self.assertTrue(safe_https_url("https://merchant.example/p"))

    def test_prices_freshness_and_currency(self):
        preview, report = self.run_match([
            row(checked_at=(NOW - timedelta(days=8)).isoformat()),
            row(product_url="https://merchant.example/other", price_eur="NaN"),
            row(product_url="https://merchant.example/another", currency="USD"),
        ])
        self.assertEqual(len(preview["offers"]), 1)
        self.assertIsNone(preview["offers"][0]["price_eur"])
        self.assertEqual(preview["offers"][0]["availability"], "unknown")
        self.assertEqual(report["rejected_by_reason"]["invalid_price"], 1)
        self.assertEqual(report["rejected_by_reason"]["unsupported_currency"], 1)

    def test_zero_feed_keeps_public_disabled(self):
        preview, report = build(self.catalog, [], NOW, 7)
        self.assertEqual(preview["offers"], [])
        self.assertEqual(report["matched_offers"], 0)
        self.assertEqual(report["verified_distinct_parts"], 2)

    def test_requires_explicit_verified_manufacturer_proof(self):
        catalog = json.loads(self.catalog.read_text(encoding="utf-8"))
        catalog["devices"][0]["parts"][0]["evidence"][0]["explicit_relation"] = False
        catalog["devices"][1]["verified"] = False
        self.catalog.write_text(json.dumps(catalog), encoding="utf-8")
        preview, report = self.run_match([row()])
        self.assertEqual(preview["offers"], [])
        self.assertEqual(report["verified_distinct_parts"], 0)


if __name__ == "__main__":
    unittest.main()
