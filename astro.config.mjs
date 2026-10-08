import { defineConfig } from "astro/config";

export default defineConfig({
  site: "https://trexdbg.github.io",
  base: "/compatigo_app",
  output: "static",
  trailingSlash: "always",
});
