import type { APIContext } from "astro";
import { brandPath, catalogDate, devicePath, partPath, publishedBrands, publishedDevices, publishedParts, sitePath } from "../lib/catalog";

// Generated at build time: the sitemap is never a list of guessed devices.
export const prerender = true;

function xmlEscape(value: string): string {
  return value.replace(/[&<>"']/g, (ch) => (
    { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&apos;" }[ch] || ch
  ));
}

export function GET({ site }: APIContext): Response {
  if (!site) throw new Error("The Astro site URL must be configured for a sitemap");
  const routes = [
    sitePath(),
    sitePath("appareils/"),
    sitePath("pieces/"),
    ...publishedBrands().map((brand) => brandPath(brand.name)),
    ...publishedDevices().map((device) => devicePath(device)),
    ...publishedParts().map((part) => partPath(part.brand, part.reference)),
  ];
  const unique = [...new Set(routes)];
  const entries = unique.map((path) => {
    const location = new URL(path, site).href;
    return "  <url><loc>" + xmlEscape(location) + "</loc>" +
      (catalogDate ? "<lastmod>" + xmlEscape(catalogDate) + "</lastmod>" : "") +
      "</url>";
  });
  const xml = '<?xml version="1.0" encoding="UTF-8"?>\n' +
    '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n' +
    entries.join("\n") + "\n</urlset>\n";
  return new Response(xml, {
    headers: { "Content-Type": "application/xml; charset=utf-8" },
  });
}
