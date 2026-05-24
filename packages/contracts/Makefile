.PHONY: python kotlin openapi-python openapi-typescript openapi-zod kafka-python lint all verify

PYTHON_OUT := codegen/python
KOTLIN_OUT := codegen/kotlin
TS_OUT := codegen/typescript

# codegen/python is an installable package `sdf_contracts` (so consumers import
# the generated DTOs instead of hand-writing them — contract-first §2). Within it
# the modules stay grouped by contract family (mirrors the SoT folders sparkplug/
# openapi/ kafka-payloads/) so the three families never mix. The package scaffold
# (pyproject.toml, __init__.py, py.typed) is hand-authored and NOT generated, so
# `make all` never rewrites it and the drift gate stays green.
PY_PKG := $(PYTHON_OUT)/sdf_contracts
PY_SPARKPLUG := $(PY_PKG)/sparkplug
PY_OPENAPI := $(PY_PKG)/openapi
PY_KAFKA := $(PY_PKG)/kafka

python:
	mkdir -p $(PY_SPARKPLUG)
	protoc --proto_path=sparkplug --python_out=$(PY_SPARKPLUG) sparkplug/sparkplug_b.proto

kotlin:
	mkdir -p $(KOTLIN_OUT)
	protoc --proto_path=sparkplug --kotlin_out=$(KOTLIN_OUT) --java_out=$(KOTLIN_OUT) sparkplug/sparkplug_b.proto

openapi-python:
	mkdir -p $(PY_OPENAPI)
	uvx --from datamodel-code-generator==0.45.0 datamodel-codegen \
	  --input openapi/sdf-api.yaml --input-file-type openapi \
	  --output $(PY_OPENAPI)/sdf_openapi_models.py \
	  --output-model-type pydantic_v2.BaseModel \
	  --target-python-version 3.12 \
	  --use-standard-collections --use-union-operator \
	  --disable-timestamp

openapi-typescript:
	mkdir -p $(TS_OUT)
	pnpm dlx openapi-typescript@7.13.0 openapi/sdf-api.yaml \
	  -o $(TS_OUT)/sdf-openapi-client.ts

# ADR-0028: generate Zod v4 runtime schemas (the frontend's network-boundary
# validator — the FE analog of the generated Pydantic boundary DTO).
# Uses a hand-authored openapi-ts.config.ts (pipeline INPUT, never rewritten
# by make all) so the config is version-controlled alongside the schema.
# ESM-only tool; requires Node ≥ 22.13 (see .github/workflows/contracts.yml).
openapi-zod:
	mkdir -p $(TS_OUT)/zod
	pnpm dlx @hey-api/openapi-ts@0.97.2

# One module per payload schema. datamodel-codegen rejects a single-file
# --output for a directory input ("modular references require an output
# directory"), so each *.schema.json is generated independently into kafka/.
kafka-python:
	mkdir -p $(PY_KAFKA)
	uvx --from datamodel-code-generator==0.45.0 datamodel-codegen \
	  --input kafka-payloads/machine_telemetry.schema.json --input-file-type jsonschema \
	  --output $(PY_KAFKA)/machine_telemetry.py \
	  --output-model-type pydantic_v2.BaseModel \
	  --target-python-version 3.12 \
	  --use-standard-collections --use-union-operator \
	  --disable-timestamp
	uvx --from datamodel-code-generator==0.45.0 datamodel-codegen \
	  --input kafka-payloads/line_state.schema.json --input-file-type jsonschema \
	  --output $(PY_KAFKA)/line_state.py \
	  --output-model-type pydantic_v2.BaseModel \
	  --target-python-version 3.12 \
	  --use-standard-collections --use-union-operator \
	  --disable-timestamp

# Quality gate (ADR-0005 D-3 #1): lint the spec BEFORE any codegen runs.
lint:
	pnpm dlx @stoplight/spectral-cli@6.16.0 lint \
	  --ruleset openapi/.spectral.yaml \
	  openapi/sdf-api.yaml

all: python kotlin openapi-python openapi-typescript openapi-zod kafka-python

# Gates run in ADR-0005 order: quality (lint) -> regenerate -> drift.
verify:
	$(MAKE) lint
	$(MAKE) all
	@git diff --exit-code codegen/ || (echo "codegen drift — run 'make all' and commit" && exit 1)
