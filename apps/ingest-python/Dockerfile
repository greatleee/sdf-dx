# syntax=docker/dockerfile:1
# Multi-stage build for the Kafka→TimescaleDB ingest service. Build context is the
# REPO ROOT (docker-compose.yml `build.context: .`) so the generated contracts
# package (`sdf_contracts`) installs alongside the app — the consumer validates
# against the generated DTO rather than a hand-written model (contract-first §2).

FROM python:3.12-slim AS build
RUN pip install --no-cache-dir uv
WORKDIR /app
COPY packages/contracts/codegen/python /app/packages/contracts/codegen/python
COPY apps/ingest-python/pyproject.toml /app/apps/ingest-python/pyproject.toml
COPY apps/ingest-python/src /app/apps/ingest-python/src
RUN uv pip install --system /app/packages/contracts/codegen/python \
 && uv pip install --system /app/apps/ingest-python

FROM python:3.12-slim AS runtime
WORKDIR /app
COPY --from=build /usr/local/lib/python3.12/site-packages /usr/local/lib/python3.12/site-packages
COPY --from=build /usr/local/bin /usr/local/bin
RUN useradd -r appuser
USER appuser
CMD ["python", "-m", "sdf_ingest.main"]
