import js from "@eslint/js";
import tseslint from "typescript-eslint";
import boundaries from "eslint-plugin-boundaries";
import importPlugin from "eslint-plugin-import";
import eslintConfigPrettier from "eslint-config-prettier";

export default tseslint.config(
  // Ignore build artifacts and installed packages
  { ignores: ["dist", "node_modules"] },

  js.configs.recommended,

  // Type-checked rules scoped to source + test files only
  {
    files: ["src/**/*.{ts,tsx}", "tests/**/*.{ts,tsx}"],
    extends: [...tseslint.configs.strictTypeChecked],
    plugins: { boundaries, import: importPlugin },
    languageOptions: {
      parserOptions: {
        projectService: true,
        tsconfigRootDir: import.meta.dirname,
      },
    },
    settings: {
      // src/App.tsx and src/main.tsx are composition roots — intentionally NOT
      // registered as boundary elements; element-types leaves them unconstrained
      // so they can wire adapters → application → ui and own DI (§1).
      "boundaries/elements": [
        { type: "domain", pattern: "src/contexts/*/domain/**" },
        { type: "application", pattern: "src/contexts/*/application/**" },
        { type: "adapters", pattern: "src/contexts/*/adapters/**" },
        { type: "ports", pattern: "src/contexts/*/ports/**" },
        { type: "ui", pattern: "src/ui/**" },
        { type: "shared", pattern: "src/shared/**" },
      ],
      // Allow eslint-plugin-import to resolve the @/ alias via tsconfig paths
      "import/resolver": {
        typescript: {
          alwaysTryTypes: true,
          project: "./tsconfig.json",
        },
      },
    },
    rules: {
      // Layer-leak guard — dependency flow: ui → application → ports → domain
      // adapters implement ports (wired in app/), never imported by application or ui (§1/§11)
      "boundaries/element-types": [
        "error",
        {
          default: "allow",
          rules: [
            // domain is the bottom — must not import anything above it, including ports
            { from: "domain", disallow: ["adapters", "application", "ui", "ports"] },
            // ports define contracts over domain; must not depend upward (§1)
            { from: "ports", disallow: ["adapters", "application", "ui"] },
            // adapters implement ports/domain/shared; must not reach up into application or ui (§1)
            { from: "adapters", disallow: ["application", "ui"] },
            // shared = cross-cutting pure values; domain-purity applies (§2)
            { from: "shared", disallow: ["adapters", "application", "ui", "ports", "domain"] },
            // application must go through ports interfaces, never directly to adapters or ui (§1/§4)
            { from: "application", disallow: ["adapters", "ui"] },
            // ui must go through application hooks, never adapters directly (§1/§7)
            { from: "ui", disallow: ["adapters"] },
          ],
        },
      ],
      // NOTE: @sdf/contracts is adapters-only (§3, ADR-0028) but it is a *workspace* package that
      // resolves to local source, so eslint-plugin-boundaries treats it as internal — boundaries/
      // external is a no-op for it. The ban is enforced by specifier instead, via
      // @typescript-eslint/no-restricted-imports in each non-adapter layer block below.
      "@typescript-eslint/no-explicit-any": "error",
      "@typescript-eslint/no-floating-promises": "error",
      "@typescript-eslint/consistent-type-imports": "error",
      // Exhaustive discriminated-union switches — forces a new case when e.g. LineState grows (§6/§10)
      "@typescript-eslint/switch-exhaustiveness-check": [
        "error",
        {
          allowDefaultCaseForExhaustiveSwitch: false,
        },
      ],
      // Cyclomatic complexity — mirrors backend ruff C90 (mccabe) default threshold of 10
      complexity: ["error", 10],
      // Circular-dependency guard (boundaries does NOT detect cycles)
      "import/no-cycle": ["error", { maxDepth: Infinity, ignoreExternal: true }],
      "import/no-internal-modules": [
        "error",
        {
          allow: [
            // Architecture layer entry points (how external code enters a bounded context):
            // the BC barrel (`@/contexts/<bc>`) for hooks/providers, or `ports/*` for types.
            "@/contexts/*",
            "@/contexts/*/index.ts",
            "@/contexts/*/ports/*",
            // Intra-context cross-layer imports (e.g. adapters → ../ports, application →
            // ../domain, the BC barrel → ./adapters). This permits only the import *shape*;
            // dependency *direction* is still enforced by eslint-plugin-boundaries above.
            "**/domain/*",
            "**/ports/*",
            "**/application/*",
            "**/adapters/*",
            // UI layer components (imports resolved from src/ui/)
            "@/ui/**",
            // Internal testing helpers
            "**/testing/**",
            // Well-known package sub-paths
            "react-dom/client",
            "msw/browser",
            "msw/node",
            "@sdf/contracts/zod",
          ],
        },
      ],
    },
  },

  // Domain + shared purity guards — FE analog of backend AST A1/A2 + import bans (§2/§3)
  // No type info needed; TS parser inherited from the main block above.
  {
    files: ["src/contexts/*/domain/**/*.{ts,tsx}", "src/shared/**/*.{ts,tsx}"],
    rules: {
      "no-restricted-syntax": [
        "error",
        {
          selector: "CallExpression[callee.object.name='Date'][callee.property.name='now']",
          message: "Domain: inject ClockPort — no Date.now() (§2).",
        },
        {
          selector: "NewExpression[callee.name='Date'][arguments.length=0]",
          message: "Domain: inject ClockPort — no new Date() (§2).",
        },
        {
          selector: "CallExpression[callee.object.name='Math'][callee.property.name='random']",
          message: "Domain: inject RandomPort — no Math.random() (§2).",
        },
        {
          selector:
            "CallExpression[callee.object.name='crypto'][callee.property.name='randomUUID']",
          message: "Domain: inject UUIDPort — no crypto.randomUUID() (§2).",
        },
        {
          selector: "AwaitExpression",
          message: "Domain must be synchronous — no async/await (§2).",
        },
      ],
      "no-restricted-globals": [
        "error",
        { name: "fetch", message: "Domain: no browser IO — fetch belongs in adapters (§2)." },
        {
          name: "WebSocket",
          message: "Domain: no browser IO — WebSocket belongs in adapters (§2).",
        },
        { name: "localStorage", message: "Domain: no browser storage (§2)." },
        { name: "sessionStorage", message: "Domain: no browser storage (§2)." },
        { name: "window", message: "Domain: no browser globals (§2)." },
        { name: "document", message: "Domain: no browser globals (§2)." },
        { name: "navigator", message: "Domain: no browser globals (§2)." },
      ],
      // Turn off the plain rule so @typescript-eslint/no-restricted-imports governs TS files
      "no-restricted-imports": "off",
      "@typescript-eslint/no-restricted-imports": [
        "error",
        {
          paths: [
            { name: "zod", message: "Domain: Zod is boundary-only — stays in adapters (§3)." },
            { name: "react", message: "Domain: no React in domain (§2)." },
            { name: "react-dom", message: "Domain: no React in domain (§2)." },
            {
              name: "@tanstack/react-query",
              message: "Domain: TanStack Query belongs in application/ (§2).",
            },
            { name: "react-router-dom", message: "Domain: router belongs in app/ (§2)." },
            {
              name: "react-hook-form",
              message: "Domain: forms belong at the application/adapters boundary (§12).",
            },
            { name: "zustand", message: "Domain: store belongs in app/ shell (§12)." },
            { name: "@tanstack/react-router", message: "Domain: router belongs in app/ (§12)." },
          ],
          patterns: [
            {
              group: ["@sdf/contracts", "@sdf/contracts/*"],
              message:
                "Domain: generated contract schemas are boundary-only — @sdf/contracts is adapters-only (§3, ADR-0028).",
            },
          ],
        },
      ],
    },
  },

  // Application layer belt-and-suspenders: must not import adapters directly (§1/§4)
  {
    files: ["src/contexts/*/application/**/*.{ts,tsx}"],
    rules: {
      // Turn off the plain rule; the TS-aware rule below governs via pattern.regex
      "no-restricted-imports": "off",
      "@typescript-eslint/no-restricted-imports": [
        "error",
        {
          patterns: [
            {
              regex: ".*/adapters/.*",
              message: "application/ must not import adapters directly — wire via ports (§1, §4).",
            },
            {
              group: ["@sdf/contracts", "@sdf/contracts/*"],
              message:
                "application/ must not import generated contract schemas — @sdf/contracts is adapters-only (§3, ADR-0028).",
            },
          ],
        },
      ],
    },
  },

  // ports + ui complete the adapters-only ban on @sdf/contracts (§3, ADR-0028); neither has its
  // own no-restricted-imports block, so this adds one (domain/shared + application carry it inline).
  {
    files: ["src/contexts/*/ports/**/*.{ts,tsx}", "src/ui/**/*.{ts,tsx}"],
    rules: {
      "no-restricted-imports": "off",
      "@typescript-eslint/no-restricted-imports": [
        "error",
        {
          patterns: [
            {
              group: ["@sdf/contracts", "@sdf/contracts/*"],
              message:
                "Generated contract schemas are boundary-only — @sdf/contracts is adapters-only (§3, ADR-0028).",
            },
          ],
        },
      ],
    },
  },

  // Disable type-checked rules for plain JS files (e.g. this config file itself)
  {
    files: ["**/*.js"],
    extends: [tseslint.configs.disableTypeChecked],
  },

  // Must be LAST: turns off ESLint stylistic rules that would conflict with Prettier
  eslintConfigPrettier,
);
