#!/usr/bin/env python3
"""Record daily Compatigo catalogue growth without inventing new references."""
import csv
import json
from datetime import datetime, timezone
from pathlib import Path

CATALOG = Path("public/data/catalog.json")
HISTORY = Path("public/data/catalog-growth.csv")
FIELDNAMES = ["date", "devices", "compatibilities", "new_devices", "removed_devices", "goal_devices", "remaining"]

def device_ids(payload):
    return {(str(d["brand"]).casefold(), str(d["model"]).casefold(), str(d["type"]).casefold())
            for d in payload["devices"]}

def main():
    catalog = json.loads(CATALOG.read_text(encoding="utf-8"))
    devices = catalog["devices"]
    identifiers = device_ids(catalog)
    if len(identifiers) != len(devices):
        raise SystemExit("Duplicate device references: growth report aborted")
    total_edges = sum(len(d.get("parts", [])) for d in devices)
    date = datetime.now(timezone.utc).date().isoformat()
    HISTORY.parent.mkdir(parents=True, exist_ok=True)
    rows = []
    if HISTORY.exists():
        with HISTORY.open(newline="", encoding="utf-8") as f:
            rows = list(csv.DictReader(f))
    # Counts are snapshots; differences are net changes, not inferred new identities.
    prior = rows[-1] if rows else None
    previous_count = int(prior["devices"]) if prior else 0
    diff = len(devices) - previous_count if prior else 0
    record = {"date": date, "devices": len(devices), "compatibilities": total_edges,
              "new_devices": max(diff, 0), "removed_devices": max(-diff, 0),
              "goal_devices": 500, "remaining": max(0, 500 - len(devices))}
    rows = [r for r in rows if r["date"] != date]
    rows.append(record)
    rows.sort(key=lambda r: r["date"])
    with HISTORY.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=FIELDNAMES)
        writer.writeheader()
        writer.writerows(rows)
    print(f"Compatigo: {len(devices)} devices, {total_edges} verified relationships; "
          f"{record['remaining']} to goal. Daily net change: {diff if prior else 'baseline'}.")

if __name__ == "__main__":
    main()
