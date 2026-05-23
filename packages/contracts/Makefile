.PHONY: python kotlin verify

PYTHON_OUT := codegen/python
KOTLIN_OUT := codegen/kotlin

python:
	mkdir -p $(PYTHON_OUT)
	protoc --proto_path=sparkplug --python_out=$(PYTHON_OUT) sparkplug/sparkplug_b.proto

kotlin:
	mkdir -p $(KOTLIN_OUT)
	protoc --proto_path=sparkplug --kotlin_out=$(KOTLIN_OUT) --java_out=$(KOTLIN_OUT) sparkplug/sparkplug_b.proto

verify:
	@git diff --exit-code codegen/ || (echo "ERROR: codegen drift detected — run 'make python kotlin' and commit" && exit 1)
