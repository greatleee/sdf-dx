# syntax=docker/dockerfile:1
# Multi-stage build for the FastAPI service. The build context is the REPO ROOT
# (see docker-compose.yml `build.context: .`) so the generated contracts package
# (packages/contracts/codegen/python = `sdf_contracts`) can be installed alongside
# the app — the app imports the generated DTOs rather than hand-writing them
# (contract-first §2). Stage 2 carries only site-packages — no build toolchain.

FROM python:3.12-slim AS build
RUN pip install --no-cache-dir uv==0.11.7
WORKDIR /app
COPY packages/contracts/codegen/python /app/packages/contracts/codegen/python
COPY apps/api-python/pyproject.toml /app/apps/api-python/pyproject.toml
COPY apps/api-python/src /app/apps/api-python/src
# Install the generated-contracts package first, then the app (non-editable, so
# the source is baked into site-packages and no /app/src is needed at runtime).
RUN uv pip install --system /app/packages/contracts/codegen/python \
 && uv pip install --system /app/apps/api-python

FROM python:3.12-slim AS runtime
WORKDIR /app
COPY --from=build /usr/local/lib/python3.12/site-packages /usr/local/lib/python3.12/site-packages
COPY --from=build /usr/local/bin /usr/local/bin
RUN useradd -r appuser
USER appuser
EXPOSE 8000
CMD ["uvicorn", "sdf_api.app:app", "--host", "0.0.0.0", "--port", "8000"]
