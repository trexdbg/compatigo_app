"""Build an OFFLINE merchant-offer preview from the verified Compatigo catalog.

Only explicit brand + manufacturer part number exact matches are accepted. Merchant
feeds can NEVER establish device compatibility. Outputs are kept outside public/.
No network access, external libraries, credentials or scraping are required.
"""
from __future__ import annotations

import argparse
import csv
from collections import Counter, defaultdict
from datetime import datetime, timedelta, timezone
from decimal import Decimal, InvalidOperation
import ipaddress
import json
from pathlib import Path
import re
import unicodedata
from urllib.parse import urlsplit

REQUIRED_FEED_FIELDS = (
    "network", "merchant", "brand", "manufacturer_part_number", "product_url"
)
PART_PATTERN = re.compile(r"[A-Z0-9]+(?:[._ -][A-Z0-9]+)*", re.I)
PRICE_PATTERN = re.compile(r"\d{1,6}(?:[.,]\d{1,2})?")


def brand_key(value: object) -> str:
    if not isinstance(value, str):
        return ""
    return "".join(ch for ch in unicodedata.normalize("NFKD", value).casefold() if ch.isalnum())


def part_key(value: object) -> str:
    """Normalize formatting ONLY, never match titles or partial references."""
    if not isinstance(value, str) or not PART_PATTERN.fullmatch(value.strip()):
        return ""
    key = re.sub(r"[._ -]", "", value.strip().upper())
    return key if len(key) >= 5 and any(ch.isdigit() for ch in key) else ""


def safe_https_url(value: object) -> bool:
    if not isinstance(value, str):
        return False
    try:
        parsed = urlsplit(value)
        if parsed.scheme != "https" or not parsed.hostname or parsed.username or parsed.password:
            return False
        host = parsed.hostname
        if host == "localhost" or host.endswith(".localhost") or host.endswith(".local"):
            return False
        if not re.fullmatch(r"[a-z0-9.-]+", host, re.I) or "." not in host:
            return False
        try:
            ip = ipaddress.ip_address(host)
        except ValueError:
            pass
        else:
            if not ip.is_global:
                return False
        return parsed.port in (None, 443)
    except (ValueError, TypeError):
        return False


def verified_catalog(path: Path) -> tuple[dict, dict, int]:
    data = json.loads(path.read_text(encoding="utf-8"))
    if data.get("status") != "verified_catalog" or data.get("schema_version") != 1:
        raise ValueError("A schema v1 verified catalog is required")
    devices = data.get("devices")
    if not isinstance(devices, list):
        raise ValueError("Missing devices list")
    parts = defaultdict(set)
    official_kinds = {
        "manufacturer_product_page", "manufacturer_manual",
        "manufacturer_support", "manufacturer_catalog",
    }
    for device in devices:
        if not isinstance(device, dict) or device.get("verified") is not True:
            continue
        brand = brand_key(device.get("brand"))
        model = device.get("model")
        if not brand or not isinstance(model, str) or not model.strip():
            continue
        for part in device.get("parts", []):
            if not isinstance(part, dict) or part.get("status") != "verified":
                continue
            evidence = part.get("evidence")
            if not isinstance(evidence, list) or not any(
                isinstance(ev, dict)
                and ev.get("explicit_relation") is True
                and ev.get("source_kind") in official_kinds
                and safe_https_url(ev.get("source_url"))
                for ev in evidence
            ):
                continue
            key = part_key(part.get("manufacturer_part_number"))
            if key:
                parts[(brand, key)].add((str(device["brand"]), model))
    return data, parts, len(devices)


def read_feed(path: Path):
    if path.suffix.lower() == ".csv":
        with path.open(encoding="utf-8-sig", newline="") as stream:
            reader = csv.DictReader(stream)
            if not reader.fieldnames or any(field not in reader.fieldnames for field in REQUIRED_FEED_FIELDS):
                raise ValueError(f"{path}: missing required CSV columns: {REQUIRED_FEED_FIELDS}")
            yield from reader
    elif path.suffix.lower() == ".json":
        payload = json.loads(path.read_text(encoding="utf-8"))
        rows = payload if isinstance(payload, list) else payload.get("offers") if isinstance(payload, dict) else None
        if not isinstance(rows, list):
            raise ValueError(f"{path}: expected a JSON list or {{'offers': [...]}}")
        yield from rows
    else:
        raise ValueError(f"Unsupported merchant feed: {path} (use .csv or .json)")


def parse_price(value: object) -> str | None:
    if value is None or str(value).strip() == "":
        return None
    raw = str(value).strip()
    if not PRICE_PATTERN.fullmatch(raw):
        raise ValueError("invalid_price")
    try:
        price = Decimal(raw.replace(",", "."))
    except InvalidOperation as exc:
        raise ValueError("invalid_price") from exc
    if not price.is_finite() or price <= 0:
        raise ValueError("invalid_price")
    return str(price.quantize(Decimal("0.01")))


def freshness(date_value: object, now: datetime, max_age_days: int) -> tuple[bool, str | None]:
    if not isinstance(date_value, str) or not date_value.strip():
        return False, None
    try:
        dt = datetime.fromisoformat(date_value.strip().replace("Z", "+00:00"))
        if dt.tzinfo is None:
            return False, None
        dt = dt.astimezone(timezone.utc)
    except ValueError:
        return False, None
    return -timedelta(minutes=5) <= (now - dt) <= timedelta(days=max_age_days), dt.isoformat()


def prepare_offer(row: dict, eligible: dict, now: datetime, max_age_days: int):
    if not isinstance(row, dict):
        return None, "invalid_row"
    brand = brand_key(row.get("brand"))
    part = part_key(row.get("manufacturer_part_number"))
    if not brand or not part:
        return None, "invalid_reference"
    if (brand, part) not in eligible:
        return None, "no_exact_catalog_match"
    network = str(row.get("network") or "").strip()
    merchant = str(row.get("merchant") or "").strip()
    if not network or not merchant or len(network) > 80 or len(merchant) > 80:
        return None, "missing_merchant"
    product_url = row.get("product_url")
    affiliate_url = row.get("affiliate_url")
    if not safe_https_url(product_url) or (affiliate_url and not safe_https_url(affiliate_url)):
        return None, "unsafe_url"
    if row.get("currency") and str(row["currency"]).upper() != "EUR":
        return None, "unsupported_currency"
    try:
        price = parse_price(row.get("price_eur"))
    except ValueError:
        return None, "invalid_price"
    fresh, checked_at = freshness(row.get("checked_at"), now, max_age_days)
    raw_stock = str(row.get("availability") or "").strip().lower()
    available = raw_stock in ("in_stock", "available", "yes", "1")
    unavailable = raw_stock in ("out_of_stock", "unavailable", "no", "0")
    return {
        "network": network,
        "merchant": merchant,
        "brand": row["brand"].strip(),
        "manufacturer_part_number": part,
        "title": str(row.get("title") or "").strip()[:200],
        "product_url": product_url,
        "affiliate_url": affiliate_url if affiliate_url else None,
        "price_eur": price if fresh else None,
        "availability": ("in_stock" if available else "out_of_stock" if unavailable else "unknown") if fresh else "unknown",
        "checked_at": checked_at,
        "price_status": "fresh" if fresh else "stale_or_unknown",
    }, None


def build(catalog: Path, feeds: list[Path], now: datetime, max_age_days: int):
    raw_catalog, eligible, device_count = verified_catalog(catalog)
    results = []
    rejected = Counter()
    rows_total = 0
    seen = set()
    for path in feeds:
        for row in read_feed(path):
            rows_total += 1
            offer, error = prepare_offer(row, eligible, now, max_age_days)
            if error:
                rejected[error] += 1
                continue
            offer_id = (brand_key(offer["brand"]), offer["manufacturer_part_number"],
                        offer["network"].casefold(), offer["merchant"].casefold(), offer["product_url"])
            if offer_id in seen:
                rejected["duplicate_offer"] += 1
                continue
            seen.add(offer_id)
            results.append(offer)
    results.sort(key=lambda x: (brand_key(x["brand"]), x["manufacturer_part_number"],
                                x["merchant"].casefold(), x["product_url"]))
    matched_keys = {(brand_key(x["brand"]), x["manufacturer_part_number"]) for x in results}
    affected_devices = set()
    for key in matched_keys:
        affected_devices.update(eligible[key])
    report = {
        "catalog_updated_at": raw_catalog.get("updated_at"),
        "catalog_device_rows": device_count,
        "verified_distinct_parts": len(eligible),
        "feed_files": len(feeds),
        "feed_rows": rows_total,
        "matched_offers": len(results),
        "matched_distinct_parts": len(matched_keys),
        "matched_device_rows": len(affected_devices),
        "part_coverage_pct": round(100 * len(matched_keys) / len(eligible), 2) if eligible else 0,
        "rejected_by_reason": dict(sorted(rejected.items())),
        "public_links_enabled": False,
        "note": "Offline preview only. Catalog evidence is not independently audited by this matcher.",
    }
    preview = {"schema_version": 1, "status": "internal_preview_only", "offers": results}
    return preview, report


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--catalog", type=Path, default=Path("public/data/catalog.json"))
    parser.add_argument("--feed", type=Path, action="append", default=[], help="Normalized merchant CSV/JSON; repeatable")
    parser.add_argument("--output", type=Path, default=Path("build/offers-preview.json"))
    parser.add_argument("--report", type=Path, default=Path("build/offers-report.json"))
    parser.add_argument("--max-age-days", type=int, default=7)
    args = parser.parse_args()
    if args.max_age_days < 0:
        parser.error("--max-age-days must be >= 0")
    for target in (args.output, args.report):
        if target.resolve().is_relative_to(Path("public").resolve()):
            parser.error("Preview and reports must not be written inside public/")
    preview, report = build(args.catalog, args.feed, datetime.now(timezone.utc), args.max_age_days)
    for target, data in ((args.output, preview), (args.report, report)):
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
