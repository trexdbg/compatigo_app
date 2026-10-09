"""Normalize an *authorized* Awin CSV feed for Compatigo's offline matcher.

This command never downloads feeds, creates tracking links, guesses a
manufacturer part number from a product name or publishes offers.
Usage:
  python scripts/normalize_awin.py --input private/awin.csv.gz --output build/awin-normalized.csv
  python scripts/match_offers.py --feed build/awin-normalized.csv
"""
from __future__ import annotations

import argparse
import csv
import gzip
from pathlib import Path

from match_offers import part_key, safe_https_url

FIELDS = (
    "network", "merchant", "brand", "manufacturer_part_number",
    "title", "product_url", "affiliate_url", "price_eur",
    "currency", "availability", "checked_at",
)


def stock_status(row: dict) -> str:
    status = str(row.get("stock_status") or "").strip().casefold().replace(" ", "_")
    if status in {"in_stock", "out_of_stock"}:
        return status
    value = str(row.get("in_stock") or "").strip().casefold()
    if value in {"1", "yes", "true"}:
        return "in_stock"
    if value in {"0", "no", "false"}:
        return "out_of_stock"
    return "unknown"


def normalize_row(row: dict, fallback_merchant: str = "") -> dict | None:
    """Require real Awin MPN and manufacturer brand; never infer from titles."""
    brand = str(row.get("brand_name") or "").strip()
    mpn = str(row.get("mpn") or "").strip()
    merchant = str(row.get("merchant_name") or fallback_merchant).strip()
    product = str(row.get("merchant_deep_link") or row.get("deep_link") or "").strip()
    affiliate = str(row.get("aw_deep_link") or "").strip()
    if not brand or not part_key(mpn) or not merchant or not safe_https_url(product):
        return None
    if affiliate and not safe_https_url(affiliate):
        return None

    currency = str(row.get("currency") or "").strip().upper()
    # Do not label an unspecified or non-EUR price as euros.
    price = (str(row.get("search_price") or row.get("store_price") or "").strip()
             if currency == "EUR" else "")
    return {
        "network": "awin",
        "merchant": merchant,
        "brand": brand,
        "manufacturer_part_number": mpn,
        "title": str(row.get("product_name") or "").strip()[:200],
        "product_url": product,
        "affiliate_url": affiliate,
        "price_eur": price,
        "currency": currency,
        "availability": stock_status(row),
        # A feed timestamp is not an ingestion timestamp. Missing/naive
        # timestamps produce masked price and unknown stock in the matcher.
        "checked_at": str(row.get("last_updated") or "").strip(),
    }


def normalize_file(source: Path, output: Path, fallback_merchant: str = "") -> tuple[int, int]:
    if not (source.name.lower().endswith(".csv") or
            source.name.lower().endswith(".csv.gz")):
        raise ValueError("Awin importer expects an authorized .csv or .csv.gz file")
    if output.resolve().is_relative_to(Path("public").resolve()):
        raise ValueError("Normalized partner feeds must stay outside public/")
    opener = gzip.open if source.name.lower().endswith(".gz") else open
    total = 0
    accepted = 0
    output.parent.mkdir(parents=True, exist_ok=True)
    with opener(source, "rt", encoding="utf-8-sig", newline="") as stream:
        reader = csv.DictReader(stream)
        required = {"brand_name", "mpn", "product_name"}
        if not reader.fieldnames or not required.issubset(reader.fieldnames):
            raise ValueError("Missing Awin CSV fields brand_name, mpn or product_name")
        with output.open("w", encoding="utf-8", newline="") as destination:
            writer = csv.DictWriter(destination, fieldnames=FIELDS)
            writer.writeheader()
            for row in reader:
                total += 1
                offer = normalize_row(row, fallback_merchant)
                if offer:
                    writer.writerow(offer)
                    accepted += 1
    return total, accepted


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--output", type=Path, default=Path("build/awin-normalized.csv"))
    parser.add_argument("--merchant", default="", help="Merchant name if omitted from an authorized feed")
    args = parser.parse_args()
    total, accepted = normalize_file(args.input, args.output, args.merchant)
    print(f"Awin: {accepted}/{total} offers normalized to {args.output} (private offline preview)")


if __name__ == "__main__":
    main()
