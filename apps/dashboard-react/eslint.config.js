import js from "@eslint/js";
import tseslint from "typescript-eslint";
import boundaries from "eslint-plugin-boundaries";
import importPlugin from "eslint-plugin-import";

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
      "boundaries/elements": [
        { type: "domain",      pattern: "src/contexts/*/domain/**" },
        { type: "application", pattern: "src/contexts/*/application/**" },
        { type: "adapters",    pattern: "src/contexts/*/adapters/**" },
        { type: "ui",          pattern: "src/ui/**" },
        { type: "shared",      pattern: "src/shared/**" },
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
      "boundaries/element-types": ["error", {
        default: "allow",
        rules: [
          { from: "domain",      disallow: ["adapters", "application", "ui"] },
          { from: "application", disallow: ["adapters", "ui"] },
        ],
      }],
      "@typescript-eslint/no-explicit-any": "error",
      "@typescript-eslint/no-floating-promises": "error",
      "@typescript-eslint/consistent-type-imports": "error",
      "import/no-internal-modules": ["error", {
        allow: [
          // Architecture layer entry points
          "@/contexts/*/index.ts",
          "@/contexts/*/ports/*",
          // UI layer components (imports resolved from src/ui/)
          "@/ui/*",
          // Internal testing helpers
          "**/testing/**",
          // Well-known package sub-paths
          "react-dom/client",
          "msw/browser",
        ],
      }],
    },
  },

  // Disable type-checked rules for plain JS files (e.g. this config file itself)
  {
    files: ["**/*.js"],
    extends: [tseslint.configs.disableTypeChecked],
  },
);
