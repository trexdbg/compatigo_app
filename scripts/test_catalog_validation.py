"""Quality gates for catalogs consumed by the static Github Pages site."""
import copy
import unittest

from scripts.download_catalog import validate_catalog


def good_catalog():
    return {
        "schema_version": 1,
        "status": "verified_catalog",
        "devices": [{
            "brand": "Rowenta", "model": "RO7649EA", "verified": True,
            "parts": [{
                "manufacturer_part_number": "ZR920101", "status": "verified",
                "evidence": [{
                    "source_url": "https://www.rowenta.fr/example",
                    "source_kind": "manufacturer_product_page",
                    "explicit_relation": True,
                }],
            }],
        }],
    }


class CatalogValidationTests(unittest.TestCase):
    def test_accepts_explicit_manufacturer_proof(self):
        self.assertEqual(len(validate_catalog(good_catalog())), 1)

    def test_rejects_false_model(self):
        for word in ("ROBOTS", "ROBINET", "MOUSSE", "ROWENTA", "MOTEUR"):
            with self.subTest(model=word):
                catalog = good_catalog()
                catalog["devices"][0]["model"] = word
                with self.assertRaisesRegex(ValueError, "Invalid Rowenta"):
                    validate_catalog(catalog)

    def test_rejects_missing_explicit_relation(self):
        catalog = good_catalog()
        catalog["devices"][0]["parts"][0]["evidence"][0]["explicit_relation"] = False
        with self.assertRaisesRegex(ValueError, "explicit official proof"):
            validate_catalog(catalog)

    def test_rejects_mismatched_verified_flag(self):
        catalog = good_catalog()
        catalog["devices"][0]["verified"] = False
        with self.assertRaisesRegex(ValueError, "Inconsistent verified"):
            validate_catalog(catalog)

    def test_rejects_ordinary_retailer_as_official(self):
        catalog = good_catalog()
        catalog["devices"][0]["parts"][0]["evidence"][0]["source_kind"] = "retailer"
        with self.assertRaisesRegex(ValueError, "explicit official proof"):
            validate_catalog(catalog)


if __name__ == "__main__":
    unittest.main()
