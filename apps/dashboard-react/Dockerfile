# syntax=docker/dockerfile:1
# Multi-stage build for the React dashboard. The build context is the REPO ROOT
# (docker-compose.yml `build.context: .`) because the dashboard imports the
# generated contracts package `@sdf/contracts` (packages/contracts/codegen/typescript)
# as a pnpm WORKSPACE dependency — it is TypeScript SOURCE with no build step, so
# Vite compiles it during the dashboard build (contract-first §2 / ADR-0028). A
# dashboard-scoped context could not see the workspace, so the whole pnpm workspace
# (root manifest + lockfile + workspace member manifests) must be present here.
# Stage 2 is a plain nginx static server; it carries only the built dist/, none of
# the Node/pnpm toolchain.

FROM node:22.13.0-alpine AS build
WORKDIR /app
# Install pnpm at the version the repo pins (root package.json `packageManager`),
# matching the single committed root pnpm-lock.yaml the frozen install resolves.
# Installed directly rather than via `corepack enable`: the corepack bundled in
# this Node image ships a stale signing key and fails to verify the pnpm download
# ("Cannot find matching keyid").
RUN npm install -g pnpm@9.12.0
# Manifests first, for a cacheable `--frozen-lockfile` install layer that only
# re-runs when a manifest or the lockfile changes (not on every source edit).
COPY pnpm-workspace.yaml package.json pnpm-lock.yaml /app/
COPY apps/dashboard-react/package.json /app/apps/dashboard-react/package.json
COPY packages/contracts/codegen/typescript/package.json /app/packages/contracts/codegen/typescript/package.json
RUN pnpm install --frozen-lockfile
# Sources: the dashboard app + the generated TypeScript contract artifacts it
# compiles in (`@sdf/contracts` exports zod/zod.gen.ts + sdf-openapi-client.ts).
COPY apps/dashboard-react/ /app/apps/dashboard-react/
COPY packages/contracts/codegen/typescript/ /app/packages/contracts/codegen/typescript/
RUN pnpm --filter @sdf/dashboard build

FROM nginx:1.27-alpine AS runtime
# The nginx master process runs as root to bind :80; worker processes drop to
# the unprivileged `nginx` user. This is standard nginx:alpine behaviour — the
# request-handling surface is non-root. A rootless variant (listen on an
# unprivileged port) is deferred until the Hetzner deployment adds a reverse
# proxy in front that handles TLS termination.
COPY --from=build /app/apps/dashboard-react/dist /usr/share/nginx/html
COPY apps/dashboard-react/nginx.conf /etc/nginx/conf.d/default.conf
EXPOSE 80
HEALTHCHECK --interval=30s --timeout=3s --retries=3 \
    CMD wget -qO- http://127.0.0.1/ >/dev/null 2>&1 || exit 1
