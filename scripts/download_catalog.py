"""Download a validated catalog artifact from the private Compatigo agent.

Requires COMPATIGO_AGENT_READ_TOKEN (fine-grained PAT with Actions:read on
trexdbg/compatigo_agent). Fail closed: never publish unverified data.
"""
from __future__ import annotations

import io
import json
import os
from pathlib import Path
from urllib.request import Request, urlopen
from zipfile import ZipFile

API = "https://api.github.com/repos/trexdbg/compatigo_agent"
TOKEN = os.environ["GH_TOKEN"]
HEADERS = {
    "Authorization": f"Bearer {TOKEN}",
    "Accept": "application/vnd.github+json",
    "X-GitHub-Api-Version": "2022-11-28",
    "User-Agent": "CompatigoCatalogSync/1.0",
}


def get_json(url: str) -> dict:
    with urlopen(Request(url, headers=HEADERS), timeout=30) as response:
        return json.load(response)


def main() -> None:
    runs = get_json(f"{API}/actions/workflows/poc.yml/runs?status=success&branch=main&per_page=20")
    for run in runs.get("workflow_runs", []):
        artifacts = get_json(f"{API}/actions/runs/{run['id']}/artifacts")
        for artifact in artifacts.get("artifacts", []):
            if artifact["name"] != "compatibility-poc-report" or artifact["expired"]:
                continue
            with urlopen(Request(artifact["archive_download_url"], headers=HEADERS), timeout=60) as response:
                data = response.read()
            with ZipFile(io.BytesIO(data)) as archive:
                if "catalog.json" not in archive.namelist():
                    continue
                catalog = json.loads(archive.read("catalog.json"))
            if catalog.get("schema_version") != 1 or catalog.get("status") != "verified_catalog":
                raise ValueError("Unexpected catalog schema/status")
            devices = catalog.get("devices")
            if not isinstance(devices, list) or not devices:
                raise ValueError("Empty catalog: refusing to overwrite public data")
            for device in devices:
                if not isinstance(device.get("parts"), list):
                    raise ValueError("Invalid device parts")
                for part in device["parts"]:
                    if part.get("status") != "verified" or not part.get("evidence"):
                        raise ValueError("Unverified part: refusing to publish")
                    for evidence in part["evidence"]:
                        url = evidence.get("source_url", "")
                        if not url.startswith("https://"):
                            raise ValueError("Invalid evidence URL")
            target = Path("public/data/catalog.json")
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(json.dumps(catalog, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
            print(f"Imported {len(devices)} devices, {sum(len(d['parts']) for d in devices)} verified relations")
            return
    raise RuntimeError("No successful agent artifact containing catalog.json found")


if __name__ == "__main__":
    main()
