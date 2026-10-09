"""Awin importer regression tests; no account or network access needed."""
import csv
from datetime import datetime, timezone
import gzip
import json
from pathlib import Path
from tempfile import TemporaryDirectory
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from normalize_awin import normalize_file, normalize_row, stock_status
from match_offers import build


def awin_row(**changes):
    row = {
        "brand_name": "Rowenta",
        "mpn": "ZR903701",
        "merchant_name": "Test Store",
        "merchant_deep_link": "https://shop.example/item/123",
        "aw_deep_link": "https://tracking.example/redirect?id=123",
        "product_name": "Filtre officiel ZR903701",
        "search_price": "19.99",
        "currency": "EUR",
        "in_stock": "1",
        "last_updated": "2026-10-09T14:00:00+00:00",
    }
    row.update(changes)
    return row


class AwinImporterTests(unittest.TestCase):
    def setUp(self):
        self.temp = TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)

    def test_only_explicit_mpn_and_safe_links(self):
        self.assertEqual(normalize_row(awin_row())["manufacturer_part_number"], "ZR903701")
        self.assertIsNone(normalize_row(awin_row(mpn="", product_name="ZR903701")))
        self.assertIsNone(normalize_row(awin_row(merchant_deep_link="http://shop.example/p")))
        self.assertIsNone(normalize_row(awin_row(aw_deep_link="https://127.0.0.1/p")))
        self.assertEqual(stock_status(awin_row(in_stock="0")), "out_of_stock")

    def test_unknown_currency_does_not_invent_euro_price(self):
        row = normalize_row(awin_row(currency=""))
        self.assertEqual(row["price_eur"], "")
        self.assertEqual(row["currency"], "")
        self.assertEqual(normalize_row(awin_row(last_updated=""))["checked_at"], "")

    def test_csv_gzip_end_to_end_offline(self):
        feed = self.root / "awin.csv.gz"
        normalized = self.root / "normalized.csv"
        with gzip.open(feed, "wt", encoding="utf-8", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=list(awin_row()))
            writer.writeheader()
            writer.writerow(awin_row())
            writer.writerow(awin_row(mpn="", product_name="ZR903701"))
        total, accepted = normalize_file(feed, normalized)
        self.assertEqual((total, accepted), (2, 1))
        with normalized.open(encoding="utf-8", newline="") as handle:
            rows = list(csv.DictReader(handle))
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["availability"], "in_stock")

        catalog = self.root / "catalog.json"
        catalog.write_text(json.dumps({
            "schema_version": 1, "status": "verified_catalog", "devices": [{
                "brand": "Rowenta", "model": "RO7640EA", "verified": True,
                "parts": [{
                    "manufacturer_part_number": "ZR903701", "status": "verified",
                    "evidence": [{
                        "source_url": "https://www.rowenta.fr/filtre",
                        "source_kind": "manufacturer_product_page",
                        "explicit_relation": True,
                    }]
                }]
            }]
        }), encoding="utf-8")
        preview, report = build(catalog, [normalized],
                                datetime(2026, 10, 9, 15, tzinfo=timezone.utc), 7)
        self.assertEqual(report["matched_offers"], 1)
        self.assertFalse(report["public_links_enabled"])
        self.assertEqual(preview["offers"][0]["manufacturer_part_number"], "ZR903701")
        self.assertEqual(preview["offers"][0]["price_eur"], "19.99")


if __name__ == "__main__":
    unittest.main()
