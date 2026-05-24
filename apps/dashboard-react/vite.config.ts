/// <reference types="vitest/config" />
import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
import path from "node:path";
import { configDefaults } from "vitest/config";

export default defineConfig({
  plugins: [react()],
  resolve: { alias: { "@": path.resolve(__dirname, "src") } },
  server: {
    proxy: {
      "/api": "http://localhost:8000",
      "/ws": { target: "ws://localhost:8000", ws: true },
    },
  },
  // Vitest runs unit/component tests only. Playwright owns `tests/e2e/**` (`*.spec.ts`),
  // which Vitest's default include would otherwise collect and choke on.
  test: {
    exclude: [...configDefaults.exclude, "tests/e2e/**"],
  },
});
