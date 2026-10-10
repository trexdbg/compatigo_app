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

/** Labels never imply that a printer toner or ink cartridge is an air filter. */
export function partKindLabel(kind?: string | null): string {
  const labels: Record<string, string> = {
    filter: "Filtre",
    bag: "Sac aspirateur",
    ink: "Cartouche d’encre",
    toner: "Toner",
    drum: "Tambour",
  };
  return labels[kind ?? ""] ?? "Consommable";
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

export type PublishedPart = {
  brand: string;
  reference: string;
  name?: string | null;
  kind?: string;
  devices: Device[];
  proofs: Proof[];
};

export function partPath(brand: string, reference: string): string {
  return sitePath("pieces/" + slug(brand) + "/" + slug(reference) + "/");
}

// One verified manufacturer reference can fit several appliances. Group edges,
// retaining actual device links and the original manufacturer evidence.
export function publishedParts(): PublishedPart[] {
  const groups = new Map<string, PublishedPart>();
  for (const device of publishedDevices()) {
    for (const part of verifiedParts(device)) {
      const reference = part.manufacturer_part_number.trim().toUpperCase();
      const key = slug(device.brand) + ":" + reference;
      let group = groups.get(key);
      if (!group) {
        group = {
          brand: device.brand,
          reference,
          name: part.consumable_name,
          kind: part.consumable_type,
          devices: [],
          proofs: [],
        };
        groups.set(key, group);
      }
      if (!group.devices.some((d) => d.model === device.model)) {
        group.devices.push(device);
      }
      for (const proof of officialProofs(part)) {
        if (!group.proofs.some((existing) => existing.source_url === proof.source_url)) {
          group.proofs.push(proof);
        }
      }
    }
  }
  return [...groups.values()].sort((a, b) =>
    a.brand.localeCompare(b.brand, "fr") ||
    a.reference.localeCompare(b.reference, "fr", { numeric: true }),
  );
}
