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
    for device in devices:
        if not isinstance(device, dict):
            raise ValueError("Invalid device")
        brand, model = device.get("brand"), device.get("model")
        if not isinstance(brand, str) or not isinstance(model, str) or not model.strip():
            raise ValueError("Missing device brand/model")
        if brand.casefold() == "rowenta" and ROWENTA_MODEL_RE.fullmatch(model) is None:
            raise ValueError(f"Invalid Rowenta device: {model}")

        parts = device.get("parts")
        if not isinstance(parts, list):
            raise ValueError("Invalid device parts")
        if device.get("verified") is not bool(parts):
            raise ValueError(f"Inconsistent verified flag for {brand} {model}")
        for part in parts:
            if not isinstance(part, dict) or part.get("status") != "verified":
                raise ValueError("Unverified part: refusing to publish")
            if not isinstance(part.get("manufacturer_part_number"), str) or not part["manufacturer_part_number"]:
                raise ValueError("Missing manufacturer part number")
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
    print(f"Imported {len(devices)} devices, {sum(len(d['parts']) for d in devices)} verified relations")


if __name__ == "__main__":
    main()
