"""Synchronize the latest quality-gated Compatigo agent catalog.

Refuse to publish stale or unproven compatibility relationships.
Requires COMPATIGO_AGENT_READ_TOKEN as GH_TOKEN, granting Actions:read.
"""
from __future__ import annotations

import io
import json
import os
import re
from pathlib import Path
from urllib.error import HTTPError
from urllib.parse import urlsplit
from urllib.request import Request, urlopen, build_opener, HTTPRedirectHandler
from zipfile import ZipFile

API = "https://api.github.com/repos/trexdbg/compatigo_agent"
TOKEN = os.environ.get("GH_TOKEN", "")
HEADERS = {
    "Authorization": f"Bearer {TOKEN}",
    "Accept": "application/vnd.github+json",
    "X-GitHub-Api-Version": "2022-11-28",
    "User-Agent": "CompatigoCatalogSync/1.1",
}
ROWENTA_MODEL_RE = re.compile(r"(?:RO|RH|RR|YY|IX|MO)[0-9][A-Z0-9]{3,7}", re.I)
OFFICIAL_EVIDENCE = {
    "manufacturer_product_page",
    "manufacturer_manual",
    "manufacturer_support",
    "manufacturer_catalog",
}


def get_json(url: str) -> dict:
    with urlopen(Request(url, headers=HEADERS), timeout=30) as response:
        return json.load(response)


def validate_catalog(catalog: dict) -> list[dict]:
    if catalog.get("schema_version") != 1 or catalog.get("status") != "verified_catalog":
        raise ValueError("Unexpected catalog schema/status")

    devices = catalog.get("devices")
    if not isinstance(devices, list) or not devices:
        raise ValueError("Empty catalog: refusing to overwrite public data")

    verified = 0
    seen_devices = set()
    for device in devices:
        if not isinstance(device, dict):
            raise ValueError("Invalid device")
        brand, model = device.get("brand"), device.get("model")
        if not isinstance(brand, str) or not isinstance(model, str) or not model.strip():
            raise ValueError("Missing device brand/model")
        device_key = (brand.strip().casefold(), model.strip().casefold())
        if device_key in seen_devices:
            raise ValueError(f"Duplicate device in source catalog: {brand} {model}")
        seen_devices.add(device_key)
        if brand.casefold() == "rowenta" and ROWENTA_MODEL_RE.fullmatch(model) is None:
            raise ValueError(f"Invalid Rowenta device: {model}")

        parts = device.get("parts")
        if not isinstance(parts, list):
            raise ValueError("Invalid device parts")
        if device.get("verified") is not bool(parts):
            raise ValueError(f"Inconsistent verified flag for {brand} {model}")
        seen_parts = set()
        for part in parts:
            if not isinstance(part, dict) or part.get("status") != "verified":
                raise ValueError("Unverified part: refusing to publish")
            if not isinstance(part.get("manufacturer_part_number"), str) or not part["manufacturer_part_number"]:
                raise ValueError("Missing manufacturer part number")
            part_key = part["manufacturer_part_number"].strip().upper()
            if not part_key or part_key in seen_parts:
                raise ValueError(f"Invalid or duplicate part on {brand} {model}")
            seen_parts.add(part_key)
            evidence = part.get("evidence")
            if not isinstance(evidence, list) or not evidence:
                raise ValueError("Missing compatibility evidence")
            if not any(
                isinstance(e, dict)
                and e.get("explicit_relation") is True
                and e.get("source_kind") in OFFICIAL_EVIDENCE
                and isinstance(e.get("source_url"), str)
                and e["source_url"].startswith("https://")
                for e in evidence
            ):
                raise ValueError("No explicit official proof for a verified part")
            for e in evidence:
                if not isinstance(e, dict) or not isinstance(e.get("source_url"), str) or not e["source_url"].startswith("https://"):
                    raise ValueError("Invalid evidence URL")
                # Printer proofs must point to the exact manufacturer's official
                # domain; a marketplace cannot masquerade as manufacturer evidence.
                if device.get("type") == "Imprimante":
                    printer_hosts = {
                        "canon": {"www.canon.fr"},
                        "brother": {"store.brother.fr"},
                    }
                    expected_hosts = printer_hosts.get(brand.strip().casefold())
                    if expected_hosts is None:
                        raise ValueError(f"Unknown printer manufacturer: {brand}")
                    if (e.get("source_kind") in OFFICIAL_EVIDENCE
                            and urlsplit(e["source_url"]).hostname not in expected_hosts):
                        raise ValueError(f"Non-manufacturer printer proof: {brand} {model}")
                # Coffee-machine parts are imported exclusively from the branded
                # manufacturer's official product or model-specific support domain.
                if device.get("type") == "Machine à café":
                    allowed_hosts = {
                        "philips": {"www.home-appliances.philips"},
                        "saeco": {"www.philips.fr"},
                        "de'longhi": {"www.delonghi.com"},
                    }
                    hostname = urlsplit(e["source_url"]).hostname
                    if hostname not in allowed_hosts.get(brand.strip().casefold(), set()):
                        raise ValueError(f"Invalid coffee manufacturer source: {brand} {model}")
            verified += 1

    if not verified:
        raise ValueError("No verified compatibility relationships")
    return devices


class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def download_artifact(url: str) -> bytes:
    # Redirects point to a signed Azure storage URL. Do NOT forward the PAT.
    try:
        with build_opener(NoRedirect()).open(Request(url, headers=HEADERS), timeout=60) as response:
            return response.read()
    except HTTPError as exc:
        if exc.code not in (301, 302, 303, 307, 308):
            raise
        signed_url = exc.headers.get("Location")
        if not signed_url or not signed_url.startswith("https://"):
            raise ValueError("Missing secure artifact redirect URL") from exc
        with urlopen(Request(signed_url, headers={"User-Agent": "CompatigoCatalogSync/1.1"}), timeout=60) as response:
            return response.read()


def main() -> None:
    if not TOKEN:
        raise RuntimeError("Configure COMPATIGO_AGENT_READ_TOKEN")

    # Never silently fall back to an old successful artifact if the newest
    # pipeline failed: that would keep publishing untrusted/stale data.
    runs = get_json(f"{API}/actions/workflows/poc.yml/runs?branch=main&per_page=20")
    latest = next(iter(runs.get("workflow_runs", [])), None)
    if not latest or latest.get("status") != "completed" or latest.get("conclusion") != "success":
        raise RuntimeError("Latest compatibility-poc did not complete successfully")

    artifacts = get_json(f"{API}/actions/runs/{latest['id']}/artifacts")
    artifact = next(
        (a for a in artifacts.get("artifacts", [])
         if a.get("name") == "compatibility-poc-report" and not a.get("expired")),
        None,
    )
    if not artifact:
        raise RuntimeError("Latest successful POC has no usable catalog artifact")

    with ZipFile(io.BytesIO(download_artifact(artifact["archive_download_url"]))) as archive:
        if "catalog.json" not in archive.namelist():
            raise RuntimeError("Artifact has no catalog.json")
        catalog = json.loads(archive.read("catalog.json"))

    devices = validate_catalog(catalog)
    target = Path("public/data/catalog.json")
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(catalog, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    by_brand = {}
    by_type = {}
    for device in devices:
        brand = device["brand"]
        stats = by_brand.setdefault(brand, {"verified_devices": 0, "verified_relations": 0})
        if device["verified"]:
            stats["verified_devices"] += 1
            stats["verified_relations"] += len(device["parts"])
            kind = device.get("type") or "Non précisé"
            by_type[kind] = by_type.get(kind, 0) + 1
    unique_parts = {(device["brand"].casefold(), part["manufacturer_part_number"].strip().upper())
                    for device in devices for part in device["parts"]}
    print(f"Imported {len(devices)} candidate devices; "
          f"{sum(s['verified_devices'] for s in by_brand.values())} verified devices; "
          f"{sum(s['verified_relations'] for s in by_brand.values())} verified relations; "
          f"{len(unique_parts)} distinct manufacturer consumables.")
    print("Verified brand coverage: " + json.dumps(by_brand, ensure_ascii=False, sort_keys=True))
    print("Verified device categories: " + json.dumps(by_type, ensure_ascii=False, sort_keys=True))


if __name__ == "__main__":
    main()
