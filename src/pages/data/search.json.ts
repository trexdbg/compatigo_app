import type { APIRoute } from "astro";
import { officialProofs, publishedDevices, verifiedParts } from "../../lib/catalog";

// The browser and SEO pages must use the exact same verified, publishable set.
// The raw agent catalogue may contain candidates that must never enter search.
export const GET: APIRoute = () => {
  const devices = publishedDevices().map((device) => ({
    brand: device.brand,
    model: device.model,
    type: device.type,
    verified: true,
    parts: verifiedParts(device).map((part) => ({
      manufacturer_part_number: part.manufacturer_part_number,
      consumable_name: part.consumable_name,
      consumable_type: part.consumable_type,
      status: "verified",
      evidence: officialProofs(part).map((proof) => ({
        source_url: proof.source_url,
        source_kind: proof.source_kind,
        explicit_relation: true,
      })),
    })),
  }));

  return new Response(
    JSON.stringify({ schema_version: 1, status: "verified_catalog", devices }),
    {
      headers: {
        "Content-Type": "application/json; charset=utf-8",
        "Cache-Control": "public, max-age=3600",
      },
    },
  );
};
