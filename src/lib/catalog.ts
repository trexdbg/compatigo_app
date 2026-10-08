import catalog from "../../public/data/catalog.json";

export type Proof = {
  source_url: string;
  source_kind: string;
  source_title?: string | null;
  retrieved_at?: string;
  explicit_relation?: boolean;
  excerpt?: string;
};
export type Consumable = {
  manufacturer_part_number: string;
  consumable_name?: string | null;
  consumable_type?: string;
  status: string;
  evidence: Proof[];
};
export type Device = {
  brand: string;
  model: string;
  type?: string;
  verified: boolean;
  parts: Consumable[];
};

const manufacturerKinds = new Set([
  "manufacturer_product_page",
  "manufacturer_manual",
  "manufacturer_support",
  "manufacturer_catalog",
]);
const rowentaPattern = /^(RO|RH|RR|YY|IX|MO)[0-9][A-Z0-9]{3,7}$/i;

export function officialProofs(part: Consumable): Proof[] {
  return (part.evidence ?? []).filter(
    (e) =>
      e.explicit_relation === true &&
      manufacturerKinds.has(e.source_kind) &&
      typeof e.source_url === "string" &&
      e.source_url.startsWith("https://"),
  );
}

export function verifiedParts(device: Device): Consumable[] {
  return (device.parts ?? []).filter(
    (part) =>
      part.status === "verified" &&
      !!part.manufacturer_part_number?.trim() &&
      officialProofs(part).length > 0,
  );
}

// A page is eligible only when backed by an explicit, trusted manufacturer
// relationship. The HTML and sitemap use the exact same list.
export function publishedDevices(): Device[] {
  return (catalog.devices as Device[])
    .filter(
      (d) =>
        d.verified === true &&
        !!d.brand?.trim() &&
        !!d.model?.trim() &&
        (d.brand.toLowerCase() !== "rowenta" || rowentaPattern.test(d.model)) &&
        verifiedParts(d).length > 0,
    )
    .sort((a, b) =>
      a.brand.localeCompare(b.brand, "fr") ||
      a.model.localeCompare(b.model, "fr", { numeric: true }),
    );
}

export function slug(value: string): string {
  return value
    .normalize("NFD")
    .replace(/[\u0300-\u036f]/g, "")
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, "-")
    .replace(/^-|-$/g, "");
}

export function sitePath(path = ""): string {
  return import.meta.env.BASE_URL.replace(/\/$/, "") + "/" + path.replace(/^\//, "");
}

export function devicePath(device: Device): string {
  return sitePath(slug(device.brand) + "/" + slug(device.model) + "/");
}

export function brandPath(brand: string): string {
  return sitePath("marques/" + slug(brand) + "/");
}

export function publishedBrands(): { name: string; count: number }[] {
  const counts = new Map<string, number>();
  for (const device of publishedDevices()) {
    counts.set(device.brand, (counts.get(device.brand) ?? 0) + 1);
  }
  return [...counts].map(([name, count]) => ({ name, count }));
}

export const catalogDate = typeof catalog.updated_at === "string"
  ? catalog.updated_at.slice(0, 10)
  : undefined;
