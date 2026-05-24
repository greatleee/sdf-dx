// Hand-authored pipeline INPUT — `make all` never rewrites this file
// (same principle as the pyproject.toml scaffold in codegen/python/).
// ADR-0028: generated Zod schemas are the frontend's runtime validation
// boundary — the FE analog of the generated Pydantic boundary DTO.
// See contract-first.md §2 for generator selection rationale.

// Config schema (`input` / `output.path` / `plugins[].definitions`) verified
// against @hey-api/openapi-ts@0.97.2 — the version pinned in the Makefile's
// `openapi-zod` target. Re-verify these keys on any version bump (0.x renames
// config keys between minors).
/** @type {import('@hey-api/openapi-ts').UserConfig} */
export default {
  // SoT: packages/contracts/openapi/sdf-api.yaml (contract-first §1).
  // The './' prefix is required: without it, hey-api's input parser
  // misreads 'openapi/sdf-api.yaml' as an "org/project" Hey API shorthand.
  input: './openapi/sdf-api.yaml',
  output: {
    // Placed under codegen/typescript/zod/ to avoid colliding with the
    // existing openapi-typescript output (sdf-openapi-client.ts).
    // Both live under codegen/typescript/ and are covered by the same
    // drift gate (`git diff --exit-code codegen/`).
    path: 'codegen/typescript/zod',
  },
  plugins: [
    {
      name: 'zod',
      // Generate named schemas for all reusable component definitions
      // (ProductionLine, LineStateSnapshot, OeeReading) — these are what
      // the frontend adapters import for runtime boundary validation.
      definitions: true,
    },
  ],
};
