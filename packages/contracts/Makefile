.PHONY: python kotlin openapi-python openapi-typescript lint all verify

PYTHON_OUT := codegen/python
KOTLIN_OUT := codegen/kotlin
TS_OUT := codegen/typescript

python:
	mkdir -p $(PYTHON_OUT)
	protoc --proto_path=sparkplug --python_out=$(PYTHON_OUT) sparkplug/sparkplug_b.proto

kotlin:
	mkdir -p $(KOTLIN_OUT)
	protoc --proto_path=sparkplug --kotlin_out=$(KOTLIN_OUT) --java_out=$(KOTLIN_OUT) sparkplug/sparkplug_b.proto

openapi-python:
	mkdir -p $(PYTHON_OUT)
	uvx --from datamodel-code-generator datamodel-codegen \
	  --input openapi/sdf-api.yaml --input-file-type openapi \
	  --output $(PYTHON_OUT)/sdf_openapi_models.py \
	  --output-model-type pydantic_v2.BaseModel \
	  --target-python-version 3.12 \
	  --use-standard-collections --use-union-operator \
	  --disable-timestamp

openapi-typescript:
	mkdir -p $(TS_OUT)
	pnpm dlx openapi-typescript openapi/sdf-api.yaml \
	  -o $(TS_OUT)/sdf-openapi-client.ts

# Quality gate (ADR-0005 D-3 #1): lint the spec BEFORE any codegen runs.
lint:
	pnpm dlx @stoplight/spectral-cli lint \
	  --ruleset openapi/.spectral.yaml \
	  openapi/sdf-api.yaml

all: python kotlin openapi-python openapi-typescript

# Gates run in ADR-0005 order: quality (lint) -> regenerate -> drift.
verify:
	$(MAKE) lint
	$(MAKE) all
	@git diff --exit-code codegen/ || (echo "codegen drift — run 'make all' and commit" && exit 1)
