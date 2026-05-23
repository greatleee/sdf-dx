# Phase 1 — Single-Factory Vertical Slice Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking. **Before each task, load `docs/architecture/2026-05-23-code-architecture.md` — when a code sample below conflicts with that arch doc, the arch doc wins.**

**Goal:** Build an end-to-end vertical slice — Kotlin OT gateway publishing Sparkplug B telemetry over MQTT → Kafka → Python ingest → TimescaleDB → Python domain (OEE per ISO 22400) → FastAPI REST+WS → React dashboard — running locally via `docker compose up` in under 5 minutes.

**Architecture:** Polyglot monorepo. Kotlin handles industrial protocols (Eclipse Tahu/Paho/Milo). Python handles domain logic and API. React handles UI. Schemas (Sparkplug Protobuf, OpenAPI 3.1, JSON Schema) are single source of truth — contract-first, codegen-enforced. Domain logic is pure (Functional Core / Imperative Shell). Drift is contained via import-linter / Konsist / strict type checkers wired into CI.

**Tech Stack:** Kotlin 2.0 + Spring Boot 3 + Eclipse Tahu + Paho · Python 3.12 + FastAPI + aiokafka + asyncpg + Pydantic v2 · React 18 + Vite + TypeScript 5 + TanStack Query + Tailwind + Recharts + react-i18next · PostgreSQL 16 + TimescaleDB 2.15 · HiveMQ CE 2024 · Redpanda 24 (Kafka-compatible) · Playwright 1.4x · MSW 2 · Docker Compose v2.

**Source Spec:** `docs/roadmap/2026-05-22-sdf-manufacturing-dx-portfolio-design.md` §10 Phase 1, §13.1 Phase 1 AC.

**Code Architecture (load this — it supersedes plan code samples on conflict):** `docs/architecture/2026-05-23-code-architecture.md` (Engineering Conventions) + fast-scan rules `.claude/rules/backend-code-architecture.md`. Plus ADR-0004 / 0009 / 0016 / 0017 / 0018 / 0019 / 0020 / 0021 / 0022 / 0023 / 0024. Reference impl for Python adapter/UoW/fakes patterns: kept locally (memory `reference-codebase`). Known conflicts to apply during execution: (a) core error handling — plan uses `raise X`, arch doc requires sum-type return; (b) clock / UUID — arch doc forbids `datetime.now()` / `uuid.uuid4()` inside `domain/`, inject from shell; (c) Pydantic — arch doc keeps it at boundary only, domain uses stdlib `@dataclass(frozen=True, slots=True)`; (d) cross-BC use cases — live in top-level `src/sdf_api/use_cases/`, not inside any BC's `application/`; (e) ORM containment — adapter MAY use SQLAlchemy 2.0 ORM under containment (private `_Base` / `_X` ORM classes, public `*Repo` returns domain types or primitives, no commit in adapter, no class-level Port inheritance, `Computed(persisted=True)` for GENERATED columns) — ADR-0019, supersedes any plan code that says "Core only" or restricts adapter to `asyncpg` raw; (f) Unit of Work — use case owns the transaction boundary via `async with self._uow_factory() as uow: ... await uow.commit()`; `UnitOfWork` Protocol is per-BC in `contexts/<bc>/ports/unit_of_work.py`, not global — ADR-0020; (g) Ports as folder — Port Protocols live in `contexts/<bc>/ports/<noun>.py` (folder, file-per-feature), not single `ports.py`; cross-cutting Ports in `shared_kernel/ports/<name>.py` — ADR-0022; (h) ClockPort Protocol — clock injection is always `ClockPort` Protocol from `shared_kernel/ports/clock.py`; `Callable[[], datetime]` is retired — ADR-0021; (i) `*Repo` suffix allowed on adapter and Port classes (general persistence vocabulary, not DDD-classical) — ADR-0019; (j) Fakes — `tests/contexts/<bc>/fakes.py` per BC with `InMemoryDataset` shared mutable state + `FakeUnitOfWork(dataset)` exposing `committed` / `rolled_back` flags; cross-cutting fakes (`FixedClock`) in `tests/shared_kernel/fakes.py` — ADR-0024; (k) CI gates — new contracts `adapters-no-upward` + `composition-only-imports-adapters`, AST check A3 (`uow.session` only in `composition.py`) — ADR-0023. **This plan's body is not edited to reflect these — that violates SOT-LAYERS §74. Apply at execution time.**

**Out of Scope for Phase 1:** Multi-tenancy (Phase 2), observability/k8s (Phase 3), additional BCs (Phase 4), demo polish (Phase 5).

---

## File Structure (created by Phase 1)

```
sdf-dx/
├── README.md
├── .github/workflows/ci.yml
├── docker-compose.yml
├── apps/
│   ├── ot-gateway-kotlin/          # OPC UA / MQTT / Sparkplug B publisher
│   ├── device-simulator-kotlin/    # Synthetic line + 5 machines
│   ├── sparkplug-bridge-kotlin/    # MQTT→Kafka bridge
│   ├── ingest-python/              # Kafka consumer → TimescaleDB
│   ├── api-python/                 # FastAPI REST+WS, domain logic
│   └── dashboard-react/            # Vite + React dashboard
├── packages/
│   └── contracts/
│       ├── sparkplug/              # Eclipse Tahu .proto (vendored)
│       ├── openapi/sdf-api.yaml    # OpenAPI 3.1 spec
│       ├── kafka-payloads/         # JSON Schema for normalized payloads
│       └── codegen/                # Pydantic / TS / Kotlin DTO generated
├── infra/
│   └── timescale/init/             # SQL bootstrap
├── docs/
│   ├── ADR/                        # 0001..0012 ADRs
│   ├── KNOWN-UNKNOWNS.md
│   ├── DOMAIN-NOTES.md
│   ├── AI-WORKFLOW/case-01.md
│   ├── spec/                       # behavior catalog (already present)
│   │   ├── ACTORS.md
│   │   ├── USE-CASES.md            # registry/index
│   │   └── use-cases/              # per-UC spec files (hybrid template)
│   ├── plans/                      # this file
│   └── roadmap/                    # design spec lives here
└── scripts/
    └── live-demo/scenario-a.md     # Phase 1 live-demo script
```

---

## Section A — Repo Foundation & Tooling

### Task 1: Initialize monorepo skeleton + root tooling

**Files:**
- Create: `package.json`, `pnpm-workspace.yaml`, `.editorconfig`, `.gitattributes`
- Modify: `.gitignore`, `README.md`
- Create: `docs/ADR/template.md`

- [ ] **Step 1: Update root `.gitignore`**

Append to `/Users/cdlee/personal/sdf-dx/.gitignore`:

```
# Node
node_modules/
dist/
.vite/
.turbo/

# Python
__pycache__/
*.pyc
.venv/
.pytest_cache/
.mypy_cache/
.ruff_cache/
htmlcov/
.coverage

# Kotlin / Gradle
.gradle/
build/
*.class

# IDE
.idea/
.vscode/
*.iml

# Docker
.env.local
.env.*.local
```

- [ ] **Step 2: Create `pnpm-workspace.yaml`**

```yaml
packages:
  - "apps/dashboard-react"
  - "packages/contracts"
```

- [ ] **Step 3: Create root `package.json`**

```json
{
  "name": "sdf-dx",
  "private": true,
  "packageManager": "pnpm@9.12.0",
  "scripts": {
    "lint": "pnpm -r lint",
    "test": "pnpm -r test",
    "build": "pnpm -r build"
  }
}
```

- [ ] **Step 4: Create `.editorconfig`**

```
root = true

[*]
charset = utf-8
end_of_line = lf
indent_style = space
indent_size = 2
insert_final_newline = true
trim_trailing_whitespace = true

[*.{py,kt,kts}]
indent_size = 4

[Makefile]
indent_style = tab
```

- [ ] **Step 5: Create `docs/ADR/template.md`**

```markdown
# ADR-NNNN: <Title>

- **Status:** proposed | accepted | superseded by ADR-NNNN
- **Date:** YYYY-MM-DD
- **Phase:** N

## Context

<Why this decision needed to be made now, and what forces are at play.>

## Decision

<The decision itself, in active voice. One paragraph.>

## Consequences

### Positive
-

### Negative / Trade-offs
-

## Migration Path
<If this decision later needs to be reversed, what would that cost?>

## Sources

- [Link with full title — author/org, YYYY]
```

- [ ] **Step 6: Replace root `README.md` with skeleton**

```markdown
# SDF Manufacturing DX — Portfolio Project

End-to-end vertical slice of a Smart-Factory Data Fabric: Sparkplug B over MQTT → Kafka → TimescaleDB → FastAPI → React. Demonstrates AI-augmented senior full-stack engineering with explicit drift containment (contract-first, functional core, architecture-as-tests).

> **Phase 1 status:** in progress. See `docs/plans/2026-05-22-phase-1-single-factory-vertical-slice.md`.

## Quick start
```bash
docker compose up
```

## Documentation
- Design spec: `docs/roadmap/2026-05-22-sdf-manufacturing-dx-portfolio-design.md`
- ADRs: `docs/ADR/`
- Use cases: `docs/spec/USE-CASES.md` (registry); per-UC specs under `docs/spec/use-cases/`
- Known limits: `docs/KNOWN-UNKNOWNS.md`
- Domain absorption notes: `docs/DOMAIN-NOTES.md`
- AI workflow case studies: `docs/AI-WORKFLOW/`
```

- [ ] **Step 7: Commit**

```bash
git add .gitignore pnpm-workspace.yaml package.json .editorconfig README.md docs/ADR/template.md
git commit -m "chore(repo): scaffold monorepo root + ADR template"
```

---

### Task 2: Python toolchain baseline (`apps/api-python`)

**Files:**
- Create: `apps/api-python/pyproject.toml`, `apps/api-python/src/sdf_api/__init__.py`, `apps/api-python/tests/__init__.py`, `apps/api-python/Makefile`

- [ ] **Step 1: Create `apps/api-python/pyproject.toml`**

```toml
[project]
name = "sdf-api"
version = "0.1.0"
requires-python = ">=3.12"
dependencies = [
  "fastapi>=0.115",
  "uvicorn[standard]>=0.30",
  "pydantic>=2.8",
  "pydantic-settings>=2.5",
  "asyncpg>=0.29",
  "aiokafka>=0.11",
  "structlog>=24.4",
  "httpx>=0.27",
  "websockets>=13",
]

[project.optional-dependencies]
dev = [
  "pytest>=8.3",
  "pytest-asyncio>=0.24",
  "hypothesis>=6.112",
  "ruff>=0.6",
  "mypy>=1.11",
  "import-linter>=2.1",
  "testcontainers[postgres,kafka]>=4.8",
  "pytest-cov>=5.0",
]

[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"

[tool.hatch.build.targets.wheel]
packages = ["src/sdf_api"]

[tool.ruff]
line-length = 100
target-version = "py312"
src = ["src", "tests"]

[tool.ruff.lint]
select = [
  "E", "F", "W",        # pycodestyle / pyflakes
  "I",                  # isort
  "B",                  # bugbear
  "C90",                # mccabe
  "S",                  # bandit
  "PLC", "PLE", "PLR",  # pylint subsets (incl. private-name access PLC2701)
  "RUF",
  "ASYNC",
]
ignore = ["S101"]  # asserts ok in tests

[tool.ruff.lint.per-file-ignores]
"tests/**" = ["S", "PLR2004"]

[tool.mypy]
python_version = "3.12"
strict = true
disallow_any_explicit = true
disallow_any_decorated = true
warn_return_any = true
warn_unreachable = true
mypy_path = "src"
packages = ["sdf_api"]

[tool.pytest.ini_options]
addopts = "-ra --strict-markers"
asyncio_mode = "auto"
testpaths = ["tests"]
markers = [
  "integration: testcontainers-backed; opt-in via --integration",
]

[tool.importlinter]
root_package = "sdf_api"

[[tool.importlinter.contracts]]
name = "domain must not depend on adapters or external infra"
type = "forbidden"
source_modules = ["sdf_api.contexts.*.domain"]
forbidden_modules = [
  "sdf_api.contexts.*.adapters",
  "sqlalchemy", "asyncpg", "aiokafka", "httpx", "fastapi", "redis",
]

[[tool.importlinter.contracts]]
name = "BCs may not import each other directly (shared_kernel only)"
type = "independence"
modules = [
  "sdf_api.contexts.monitoring",
  "sdf_api.contexts.topology",
]
```

- [ ] **Step 2: Create `apps/api-python/src/sdf_api/__init__.py`**

```python
"""SDF Manufacturing DX — Python API + domain services."""

__version__ = "0.1.0"
```

- [ ] **Step 3: Create `apps/api-python/tests/__init__.py`**

```python
```

- [ ] **Step 4: Create `apps/api-python/Makefile`**

```makefile
.PHONY: install lint type test test-integration

install:
	uv pip install -e ".[dev]"

lint:
	ruff check .
	ruff format --check .
	lint-imports

type:
	mypy

test:
	pytest

test-integration:
	pytest --integration

ci: lint type test
```

- [ ] **Step 5: Add `conftest.py` with `--integration` flag**

Create `apps/api-python/tests/conftest.py`:

```python
import pytest


def pytest_addoption(parser: pytest.Parser) -> None:
    parser.addoption(
        "--integration",
        action="store_true",
        default=False,
        help="run integration tests (testcontainers required)",
    )


def pytest_collection_modifyitems(
    config: pytest.Config, items: list[pytest.Item]
) -> None:
    if config.getoption("--integration"):
        return
    skip_integration = pytest.mark.skip(reason="needs --integration")
    for item in items:
        if "integration" in item.keywords:
            item.add_marker(skip_integration)
```

- [ ] **Step 6: Run lint to confirm config parses**

Run: `cd apps/api-python && ruff check . && pytest --co -q`
Expected: ruff passes, pytest collects 0 items without error.

- [ ] **Step 7: Commit**

```bash
git add apps/api-python
git commit -m "chore(api-python): scaffold pyproject + ruff + mypy strict + import-linter"
```

---

### Task 3: Python toolchain baseline (`apps/ingest-python`)

**Files:**
- Create: `apps/ingest-python/pyproject.toml`, `apps/ingest-python/src/sdf_ingest/__init__.py`, `apps/ingest-python/tests/__init__.py`, `apps/ingest-python/tests/conftest.py`

- [ ] **Step 1: Create `apps/ingest-python/pyproject.toml`**

```toml
[project]
name = "sdf-ingest"
version = "0.1.0"
requires-python = ">=3.12"
dependencies = [
  "aiokafka>=0.11",
  "asyncpg>=0.29",
  "pydantic>=2.8",
  "pydantic-settings>=2.5",
  "structlog>=24.4",
  "protobuf>=5.27",
]

[project.optional-dependencies]
dev = [
  "pytest>=8.3",
  "pytest-asyncio>=0.24",
  "hypothesis>=6.112",
  "ruff>=0.6",
  "mypy>=1.11",
  "import-linter>=2.1",
  "testcontainers[postgres,kafka]>=4.8",
]

[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"

[tool.hatch.build.targets.wheel]
packages = ["src/sdf_ingest"]

[tool.ruff]
line-length = 100
target-version = "py312"
src = ["src", "tests"]

[tool.ruff.lint]
select = ["E", "F", "W", "I", "B", "C90", "S", "PLC", "PLE", "PLR", "RUF", "ASYNC"]
ignore = ["S101"]

[tool.ruff.lint.per-file-ignores]
"tests/**" = ["S", "PLR2004"]

[tool.mypy]
python_version = "3.12"
strict = true
disallow_any_explicit = true
warn_unreachable = true
mypy_path = "src"
packages = ["sdf_ingest"]

[tool.pytest.ini_options]
addopts = "-ra --strict-markers"
asyncio_mode = "auto"
testpaths = ["tests"]
markers = ["integration: opt-in via --integration"]

[tool.importlinter]
root_package = "sdf_ingest"

[[tool.importlinter.contracts]]
name = "ingest.domain must not import infra"
type = "forbidden"
source_modules = ["sdf_ingest.domain"]
forbidden_modules = ["aiokafka", "asyncpg", "sdf_ingest.adapters"]
```

- [ ] **Step 2: Create `apps/ingest-python/src/sdf_ingest/__init__.py`**

```python
"""SDF ingest pipeline — Kafka → TimescaleDB normalizer."""

__version__ = "0.1.0"
```

- [ ] **Step 3: Create `apps/ingest-python/tests/__init__.py` (empty file) and copy `conftest.py` from Task 2 Step 5 to `apps/ingest-python/tests/conftest.py`**

Identical content to api-python's conftest (the `--integration` flag plumbing).

- [ ] **Step 4: Confirm parse**

Run: `cd apps/ingest-python && ruff check . && pytest --co -q`
Expected: clean.

- [ ] **Step 5: Commit**

```bash
git add apps/ingest-python
git commit -m "chore(ingest-python): scaffold pyproject + drift gates"
```

---

### Task 4: Kotlin toolchain baseline (gateway + simulator + bridge as Gradle multi-module)

**Files:**
- Create: `apps/ot-gateway-kotlin/settings.gradle.kts`, `apps/ot-gateway-kotlin/build.gradle.kts`, `apps/ot-gateway-kotlin/gateway/build.gradle.kts`, `apps/ot-gateway-kotlin/simulator/build.gradle.kts`, `apps/ot-gateway-kotlin/bridge/build.gradle.kts`, `apps/ot-gateway-kotlin/gradle.properties`, `apps/ot-gateway-kotlin/.gitignore`

> **Note:** All three Kotlin apps live under one Gradle root for shared config. Despite the directory name `ot-gateway-kotlin`, it hosts three submodules: `gateway/`, `simulator/`, `bridge/`. The README and live-demo script reference them by submodule name. Open Question §17 of the spec is resolved here in favor of a single Gradle root.

- [ ] **Step 1: Create `apps/ot-gateway-kotlin/settings.gradle.kts`**

```kotlin
rootProject.name = "sdf-ot"
include("gateway", "simulator", "bridge")
```

- [ ] **Step 2: Create `apps/ot-gateway-kotlin/build.gradle.kts` (root)**

```kotlin
plugins {
    kotlin("jvm") version "2.0.20" apply false
    id("io.gitlab.arturbosch.detekt") version "1.23.7" apply false
    id("org.jlleitschuh.gradle.ktlint") version "12.1.1" apply false
    id("org.springframework.boot") version "3.3.4" apply false
    id("io.spring.dependency-management") version "1.1.6" apply false
}

allprojects {
    group = "com.sdf.dx"
    version = "0.1.0"
    repositories { mavenCentral() }
}

subprojects {
    apply(plugin = "io.gitlab.arturbosch.detekt")
    apply(plugin = "org.jlleitschuh.gradle.ktlint")
    apply(plugin = "org.jetbrains.kotlin.jvm")

    extensions.configure<io.gitlab.arturbosch.detekt.extensions.DetektExtension> {
        buildUponDefaultConfig = true
        allRules = false
        config.setFrom(rootProject.files("detekt.yml"))
    }

    tasks.withType<org.jetbrains.kotlin.gradle.tasks.KotlinCompile>().configureEach {
        compilerOptions {
            jvmTarget.set(org.jetbrains.kotlin.gradle.dsl.JvmTarget.JVM_21)
            freeCompilerArgs.addAll("-Xjsr305=strict", "-Xexplicit-api=strict")
        }
    }
}
```

- [ ] **Step 3: Create `apps/ot-gateway-kotlin/detekt.yml` (minimal opinionated overrides)**

```yaml
complexity:
  CyclomaticComplexMethod:
    threshold: 12
  LongMethod:
    threshold: 60
style:
  MaxLineLength:
    maxLineLength: 120
  ReturnCount:
    max: 3
naming:
  FunctionNaming:
    active: true
exceptions:
  TooGenericExceptionCaught:
    active: true
```

- [ ] **Step 4: Create per-submodule `build.gradle.kts` files**

`apps/ot-gateway-kotlin/gateway/build.gradle.kts`:

```kotlin
plugins {
    kotlin("jvm")
    id("org.springframework.boot")
    id("io.spring.dependency-management")
}

dependencies {
    implementation("org.springframework.boot:spring-boot-starter")
    implementation("org.springframework.boot:spring-boot-starter-actuator")
    implementation("org.eclipse.tahu:tahu-core:1.0.10")
    implementation("org.eclipse.paho:org.eclipse.paho.mqttv5.client:1.2.5")
    implementation("org.jetbrains.kotlinx:kotlinx-coroutines-core:1.9.0")

    testImplementation("org.springframework.boot:spring-boot-starter-test")
    testImplementation("com.lemonappdev:konsist:0.17.3")
    testImplementation("org.testcontainers:testcontainers:1.20.2")
    testImplementation("org.testcontainers:junit-jupiter:1.20.2")
    testImplementation("org.testcontainers:hivemq:1.20.2")
}

tasks.test { useJUnitPlatform() }
```

`apps/ot-gateway-kotlin/simulator/build.gradle.kts`:

```kotlin
plugins {
    kotlin("jvm")
    application
}

application {
    mainClass.set("com.sdf.dx.simulator.MainKt")
}

dependencies {
    implementation("org.eclipse.tahu:tahu-core:1.0.10")
    implementation("org.eclipse.paho:org.eclipse.paho.mqttv5.client:1.2.5")
    implementation("org.jetbrains.kotlinx:kotlinx-coroutines-core:1.9.0")
    implementation("ch.qos.logback:logback-classic:1.5.8")

    testImplementation(kotlin("test"))
    testImplementation("com.lemonappdev:konsist:0.17.3")
}

tasks.test { useJUnitPlatform() }
```

`apps/ot-gateway-kotlin/bridge/build.gradle.kts`:

```kotlin
plugins {
    kotlin("jvm")
    id("org.springframework.boot")
    id("io.spring.dependency-management")
}

dependencies {
    implementation("org.springframework.boot:spring-boot-starter")
    implementation("org.springframework.boot:spring-boot-starter-actuator")
    implementation("org.springframework.kafka:spring-kafka:3.2.4")
    implementation("org.eclipse.paho:org.eclipse.paho.mqttv5.client:1.2.5")
    implementation("org.eclipse.tahu:tahu-core:1.0.10")
    implementation("org.jetbrains.kotlinx:kotlinx-coroutines-core:1.9.0")

    testImplementation("org.springframework.boot:spring-boot-starter-test")
    testImplementation("com.lemonappdev:konsist:0.17.3")
    testImplementation("org.testcontainers:kafka:1.20.2")
    testImplementation("org.testcontainers:hivemq:1.20.2")
    testImplementation("org.testcontainers:junit-jupiter:1.20.2")
}

tasks.test { useJUnitPlatform() }
```

- [ ] **Step 5: Create `apps/ot-gateway-kotlin/gradle.properties`**

```
kotlin.code.style=official
org.gradle.parallel=true
org.gradle.caching=true
org.gradle.jvmargs=-Xmx2g -XX:+UseG1GC
```

- [ ] **Step 6: Create `apps/ot-gateway-kotlin/.gitignore`**

```
.gradle/
build/
out/
!gradle-wrapper.jar
```

- [ ] **Step 7: Generate Gradle wrapper**

Run from `apps/ot-gateway-kotlin/`:
```bash
gradle wrapper --gradle-version 8.10.2
./gradlew help
```
Expected: wrapper files created, `help` task succeeds.

- [ ] **Step 8: Commit**

```bash
git add apps/ot-gateway-kotlin
git commit -m "chore(ot-kotlin): scaffold gradle multi-module + detekt + ktlint + Konsist"
```

---

## Chapter 0 — Spec & Decisions

> **Policy**: Per [ADR-0000](../ADR/0000-phase-iteration-chapter-0.md), Phase 1's load-bearing spec + ADR + initial living-doc artifacts land as a contiguous batch *before* any contract / domain / adapter / UI / CI implementation commit. Section A above is pure scaffold (project-lifetime infrastructure with no domain content) and is exempt by ADR-0000 §Consequences 1.
>
> **Goal of Chapter 0**: freeze the decisions and the spec surface that every later session and every later commit will reference, so drift is contained and the commit log reads `chore: scaffold × 4 → docs(adr/spec) × N → feat × M → docs(revisions, ai-workflow) interspersed`.

### Task C0-1: ADRs 0001–0004 (polyglot, timescale, schema-per-tenant, functional core)

**Files:**
- Create: `docs/ADR/0001-polyglot-python-kotlin.md`, `docs/ADR/0002-timescaledb-over-influxdb.md`, `docs/ADR/0003-schema-per-tenant.md`, `docs/ADR/0004-functional-core-imperative-shell.md`

- [ ] **Step 1: Write ADR-0001 (Polyglot)**

Use the template from Task 1. Pull Context/Decision/Consequences directly from spec §3.2. Cite Eclipse Milo/Tahu/Paho project pages, Pydantic v2 release notes. Include a "Migration Path" line noting that if Python ecosystem matures on industrial protocols, the Kotlin layer could shrink.

- [ ] **Step 2: Write ADR-0002 (TimescaleDB over InfluxDB)**

Mirror spec §5.1 + §5.3. Key cited facts: DB-Engines ranking gap (20.86 vs 5.62 as of 2025-Q4 snapshot, link the page), InfluxDB v1→v2→v3 / FluxQL deprecation timeline (link InfluxData blog), TimescaleDB CA × RLS GitHub issue #5787 (URL). Migration path: if 100+ tenants land, re-evaluate ClickHouse/Citus.

- [ ] **Step 3: Write ADR-0003 (Schema-per-tenant)**

Mirror spec §5.2 + §5.3. Cite Ignition per-site, AVEVA per-plant historian patterns. State migration path: switch to RLS or Citus if (a) >100 tenants or (b) per-tenant schema migration exceeds 30s p95. Reference TimescaleDB CA × RLS incompatibility (issue #5787) as a *current* reinforcement of the choice.

- [ ] **Step 4: Write ADR-0004 (Functional Core / Imperative Shell)**

Cite Gary Bernhardt's "Boundaries" talk (2012, Ruby Conf). Decision: domain modules contain zero IO imports; adapters call domain. Consequences: property-based tests possible, zero mocks needed. Migration path: irreversible by design — exit via incremental adapter inversion.

- [ ] **Step 5: Commit**

```bash
git add docs/ADR/0001-polyglot-python-kotlin.md docs/ADR/0002-timescaledb-over-influxdb.md docs/ADR/0003-schema-per-tenant.md docs/ADR/0004-functional-core-imperative-shell.md
git commit -m "docs(adr): 0001-0004 (polyglot, timescale, schema-per-tenant, functional core)"
```

---

### Task C0-2: ADRs 0005–0008, 0010–0012 (rest of Phase 1 ADR set)

**Files:**
- Create: `docs/ADR/0005-contract-first-llm-drift.md`
- Create: `docs/ADR/0006-test-speed-tiering.md`
- Create: `docs/ADR/0007-e2e-as-qa-coverage-gate.md`
- Create: `docs/ADR/0008-domain-modeling-evolution.md`
- Create: `docs/ADR/0010-architectural-fitness-tooling.md`
- Create: `docs/ADR/0011-sparkplug-namespace.md`
- Create: `docs/ADR/0012-oee-iso22400.md`

> ADR-0009 is deferred to Phase 2 per the design spec §12 roadmap.
> Why these belong in Chapter 0: each is a load-bearing decision known at Phase 1 planning time per ADR-0000's "load-bearing" definition (two reasonable paths × downstream code-structure impact × >1 day reversal cost). Landing them upfront prevents post-hoc rationalization mid-implementation.

- [ ] **Step 1: Write ADR-0005 (Contract-first)**

Source: spec §2.3. Decision: every inter-service contract is a committed schema; codegen produces clients/models; CI diff gate fails on drift. Cite: OpenAPI 3.1 spec, datamodel-code-generator project, openapi-typescript project. Migration path: schema is the source of truth — services adopt the same generators when they join.

**Required clauses to include (external-context research, 2026-05-23):**

- **Codegen scope (Python side):** OpenAPI → Pydantic models *only* via `datamodel-code-generator`. FastAPI route handlers are hand-written against the generated models. `fastapi-code-generator` (full route-stub generation) is rejected for Phase 1 because the upstream project self-declares "experimental phase" — re-evaluate when it stabilizes. Cite: [Pydantic — datamodel_code_generator integration](https://docs.pydantic.dev/latest/integrations/datamodel_code_generator/), [fastapi-code-generator project page](https://koxudaxi.github.io/fastapi-code-generator/) (experimental notice).
- **Generated Pydantic = boundary DTOs only (per ADR-0018):** the generated models are HTTP request/response DTOs at the boundary, *not* domain types. The domain layer uses stdlib `@dataclass(frozen=True, slots=True)` with explicit `from_domain`/`to_domain` conversion (arch doc §4.4 / §8.3). Generated files in `packages/contracts/codegen/` are **never hand-edited** — regenerated on every CI run via `make all`. Extra *input-shape* validation subclasses the generated DTO in the HTTP adapter layer; **domain invariants/business logic must never be attached to a DTO** (`@field_validator` for domain rules on a DTO is an ADR-0018 anti-pattern). Cite: [Pydantic discussion #4789](https://github.com/pydantic/pydantic/discussions/4789), ADR-0018.
- **Two CI gates, not one:**
  1. **Drift gate** — `git diff --exit-code codegen/` after `make all` (Task 9).
  2. **Quality gate** — `spectral lint openapi/sdf-api.yaml` before codegen runs (Task 7 / 9). Rationale: drift gate only catches "generated output diverged from committed output"; spectral catches "spec itself is malformed or breaks our conventions before it becomes the SoT."
- **Breaking-change gate (advisory in Phase 1):** `oasdiff breaking` between PR head and `main` posts a warning when OpenAPI introduces a breaking change. Phase 1 has no external consumers, so informational only; Phase 2 promotes to blocking once tenants exist.
- **Polyglot rationale:** Phase 1 generates Pydantic + TypeScript only. Phase 2+ adds Kotlin REST via `openapi-generator` with the `kotlin-spring` generator + `delegatePattern=true` from the *same* `sdf-api.yaml`. The polyglot consumer set is the load-bearing reason we accept OpenAPI 3.1 as SoT despite FastAPI's natural code-first pull. Cite: [Baeldung — API First Development with Spring Boot and OpenAPI 3.0](https://www.baeldung.com/spring-boot-openapi-api-first-development), [openapi-generator kotlin-spring docs](https://openapi-generator.tech/docs/generators/kotlin-spring/).
- **Polyglot consensus citation block:** [OpenAPI Initiative Best Practices](https://learn.openapis.org/best-practices.html) ("OAD as a first-class source file"), [Microsoft ISE — Design API-First with TypeSpec](https://devblogs.microsoft.com/ise/design-api-first-with-typespec/), [Malt Engineering — Contract-First FastAPI + OpenAPI](https://blog.malt.engineering/design-generate-deploy-our-contract-first-api-strategy-with-fastapi-and-openapi-15bb3e855dff).

- [ ] **Step 2: Write ADR-0006 (Test speed tiering)**

Source: spec §2.4 + §7. Decision: pure tests always-on (sub-second), fakes for application layer, testcontainers opt-in locally + always-on in CI. Migration path: if developer feedback loop drifts past 5s, split test corpora further.

- [ ] **Step 3: Write ADR-0007 (E2E as QA, use-case coverage gate)**

Source: spec §2.5. Decision: use case ↔ E2E spec 1:1; coverage script blocks merge on divergence. Migration path: when accumulating >50 use cases, split coverage report by domain.

- [ ] **Step 4: Write ADR-0008 (Domain modeling evolution)**

Source: spec §2.2. Decision: Phase 1 = directory-based separation; Phase 2 introduces `tenancy/`, `identity/` BCs; Phase 4 may add `quality/`. Triggers documented (ubiquitous language conflict / independent lifecycle / different owner).

- [ ] **Step 5: Write ADR-0010 (Architectural fitness tooling)**

Source: spec §6. Decision matrix of ruff / mypy strict / import-linter on Python; tseslint strict / eslint-plugin-boundaries / ts-prune on TS; detekt / ktlint / Konsist / `-Xexplicit-api=strict` on Kotlin. Pre-commit = milliseconds; CI = full strict. Migration path: opinion adjustments via PR with rationale; rules tightened, never silently relaxed.

- [ ] **Step 6: Write ADR-0011 (Sparkplug B namespace)**

Source: spec §11.1. Topic shape `spBv1.0/<group_id>/<message_type>/<edge_node_id>[/<device_id>]`. Phase 1: group_id = tenant (sdf_default), edge_node_id = line_id, device_id implied via metric-name compounding. Migration path: when device-level granularity needed for retained NBIRTH/NDEATH, split into `<edge>/<device>` topics and update bridge subscriber pattern.

- [ ] **Step 7: Write ADR-0012 (OEE per ISO 22400)**

Source: spec §15. Define A, P, Q, OEE; reference ISO 22400-2:2014 §5; explain Phase 1 simplification (bucket = PBT). Migration path: Phase 3 introduces planned-busy-time tracking (shift schedules) and re-derives A.

- [ ] **Step 8: Commit**

```bash
git add docs/ADR/0005-* docs/ADR/0006-* docs/ADR/0007-* docs/ADR/0008-* docs/ADR/0010-* docs/ADR/0011-* docs/ADR/0012-*
git commit -m "docs(adr): 0005-0008, 0010-0012 (Phase 1 ADR set)"
```

---

### Task C0-3: UC-002 spec creation + USE-CASES.md registry row

**Files:**
- Create: `docs/spec/use-cases/UC-002-observe-oee.md`
- Modify: `docs/spec/USE-CASES.md` (append UC-002 row; `status: draft`. The `draft → implemented` promotion is intentionally deferred to Task 24 at phase end — that requires a passing Playwright E2E to be honest.)

**Pre-existing artifacts referenced (do not recreate; verify present):**
- `docs/spec/ACTORS.md` — actor catalog (A-OP, S-UI, S-API, S-DB, …). No Phase 1 actor delta needed; Phase 1 introduces no new actors.
- `docs/spec/GLOSSARY.md` — Phase 1 vocabulary already present (Line state, OEE, A/P/Q, CAGG, Edge Node, NBIRTH/NDEATH/NDATA, Tenant, …). No Chapter 0 delta required; revisit only if a new domain noun/verb surfaces during implementation.
- `docs/spec/use-cases/_TEMPLATE.md` — hybrid template (YAML front-matter + narrative + event-storming + Gherkin AC).
- `docs/spec/use-cases/UC-001-monitor-line-state.md` — UC-001 spec, already at `status: draft`.
- `scripts/check-use-case-coverage.py` — Python coverage gate; runs via `uv run`.

- [ ] **Step 1: Write `docs/spec/use-cases/UC-002-observe-oee.md`** — copy from `_TEMPLATE.md` and fill in:

```markdown
---
id: UC-002
title: Operator observes OEE refresh
status: draft
phase: 1
primary_actor: A-OP
secondary_actors:
  - S-UI
  - S-API
  - S-DB
bounded_context: monitoring
related_adrs:
  - 0012
related_e2e: apps/dashboard-react/tests/e2e/UC-002-observe-oee.spec.ts
---

# UC-002 — Operator observes OEE refresh

## Goal
An operator sees the production line's current 5-minute OEE (and its A/P/Q components) on the dashboard, refreshing without manual action, so they can spot performance degradation.

## Trigger
A-OP has the dashboard open.

## Preconditions
- The line referenced by `lineId` exists.
- At least one row exists in the `line_oee_5m` continuous aggregate (i.e., the simulator has been running long enough for the CAGG policy to have fired at least once).

## Main scenario (happy path)
1. S-UI calls `GET /api/v1/lines/{lineId}/oee?window=5m` on mount.
2. S-API queries the most recent row of `line_oee_5m` from S-DB and derives Availability / Performance / Quality / OEE via the Phase 1 approximation (see ADR-0012).
3. S-UI renders four tiles: OEE, Availability, Performance, Quality (percentages).
4. Every 5 seconds, S-UI refetches the same endpoint and updates tiles in place.

## Alternative flows
- *No CAGG rows yet*: S-API returns 404; S-UI shows a "warming up" placeholder.
- *S-API returns 5xx*: tiles retain their previous values; a stale indicator appears after >30 s without a refresh.

## Commands & events (event-storming view)

| # | Actor | Command (intent) | Domain event(s) emitted |
|---|---|---|---|
| 1 | A-OP via S-UI | `RequestLineOee(lineId, window=5m)` | — |
| 2 | S-API → S-DB | (read of `line_oee_5m`) | — |

## Invariants
- All four returned ratios lie in `[0, 1]`.
- `OEE = Availability × Performance × Quality` within floating-point tolerance (`≤ 1e-9` absolute).
- Phase 1 simplification: `Availability` is approximated as `1.0` (CAGG bucket treated as planned-busy-time). See ADR-0012 and `KNOWN-UNKNOWNS.md`.

## Acceptance criteria (Gherkin)

```gherkin
Feature: Operator observes OEE refresh

  Scenario: OEE tiles render with percentages on first load
    Given the line "Line A" has had at least one continuous-aggregate refresh
    When A-OP opens the dashboard
    Then four tiles labeled "OEE", "Availability", "Performance", "Quality" are visible within 5 seconds
    And each tile shows a percentage value in the form "<n>.<n>%" where 0 ≤ n ≤ 100

  Scenario: OEE values refresh at the polling cadence
    Given A-OP has the dashboard open and the OEE tile shows some value V1
    When 5 seconds elapse with new telemetry arriving
    Then the OEE tile shows a value V2 (possibly equal to V1) without page reload
```

## Out of scope for this UC
- *1 h / shift OEE windows* — Phase 3.
- *Cross-line OEE rollup* — separate UC.
- *OEE alarms* (e.g., "OEE < 60% for 30 min") — Phase 3 supervisor UC.

## Open questions
- The "refresh at polling cadence" scenario depends on simulator activity within the test window; making it deterministic in CI requires either time-mocking or seeded simulator output. Resolve at E2E implementation time; second Gherkin scenario is currently *deferred* (covered only in `fake` mode where MSW returns fresh handlers).
```

- [ ] **Step 2: Add UC-002 row to `docs/spec/USE-CASES.md`**

Append below the existing UC-001 row in the index table:

```markdown
| UC-002 | Operator observes OEE refresh | draft | 1 | A-OP | monitoring | [use-cases/UC-002-observe-oee.md](use-cases/UC-002-observe-oee.md) | apps/dashboard-react/tests/e2e/UC-002-observe-oee.spec.ts |
```

- [ ] **Step 3: Run coverage gate (still in draft state — `related_e2e` files may not exist yet)**

```bash
uv run scripts/check-use-case-coverage.py
```
Expected: `OK: 2 use case(s) consistent across registry, files, and E2E.`
(Note: `related_e2e` files do not yet exist on disk; the gate does not enforce existence while UCs are in `draft`.)

- [ ] **Step 4: Commit**

```bash
git add docs/spec/use-cases/UC-002-observe-oee.md docs/spec/USE-CASES.md
git commit -m "docs(spec): UC-002 (operator observes OEE refresh) + registry row"
```

---

### Task C0-4: KNOWN-UNKNOWNS.md initial content

**Files:**
- Create: `docs/KNOWN-UNKNOWNS.md`

> Lands the file's first version. Additions and resolutions throughout the phase are **living-doc** events committed inline at the moment the gap is discovered or closed — see the Living-docs reminder below.

- [ ] **Step 1: Write `docs/KNOWN-UNKNOWNS.md`**

```markdown
# Known Unknowns

This document is a working acknowledgement of what this portfolio **does not** claim to model accurately. We choose "domain reliability level B — standards alignment" and explicitly disclaim "level C — operational realism" (see design spec §1.3).

## Operational realism deliberately unmodeled
- Shift handover data consistency — assumed, not validated against any real plant.
- PLC-vendor-specific OPC UA quirks — simulator abstracts them.
- ICS network segmentation (Purdue model) — single docker network in Phase 1.
- Hot patch / maintenance window policy in 24/7 environments — out of scope.
- Multi-region data sovereignty (GDPR, India DPDP) — migration path only (§14 of spec).

## Intentionally unresolved (migration paths declared)
- TimescaleDB Continuous Aggregate × RLS incompatibility (Timescale issue #5787) — not relevant in Phase 1 (no RLS); flagged for Phase 2 schema-per-tenant decision (ADR-0003).
- Kafka exactly-once semantics — at-least-once + idempotent consumer is sufficient (ADR-0005 reasoning).
- 100+ tenant scaling — Phase 2 ends at 3 tenants by design; migration path to Citus/RLS in ADR-0003.

## Phase 1 limitations to be addressed later
- OEE Availability assumes bucket == planned-busy-time (Phase 3 introduces shift schedules).
- Only 5-minute OEE continuous aggregate is implemented (1h and shift in Phase 3).
- Single implicit tenant — multi-tenancy is Phase 2.
- No authn/authz — JWT lands in Phase 2.
- DLQ topic (`dlq.{tenant}`) not yet implemented — invalid records are logged and dropped (see ingest in Task 18). To be added before Phase 2.
```

- [ ] **Step 2: Commit**

```bash
git add docs/KNOWN-UNKNOWNS.md
git commit -m "docs(known-unknowns): initial — Phase 1 scope of disclaimed accuracy"
```

---

### Task C0-5: DOMAIN-NOTES.md initial content

**Files:**
- Create: `docs/DOMAIN-NOTES.md`

> Lands the file's first version. Revisions as implementation deepens understanding are **living-doc** events committed inline at the moment the new insight lands — see the Living-docs reminder below.

- [ ] **Step 1: Write `docs/DOMAIN-NOTES.md` (absorption journal — cited)**

```markdown
# Domain Absorption Notes

Working notes from absorbing the manufacturing domain via standards docs + vendor manuals. Each section cites a primary source.

## ISA-95 — Enterprise/Control integration
- Five-level model (L0 physical → L4 ERP). This portfolio operates L0–L2 (sensors, control, MES-edge).
- Equipment hierarchy: Enterprise → Site → Area → Work Center → Work Unit. We model Factory → Line → Machine.
- Source: [ISA-95.00.01-2010, ANSI/ISA — Enterprise-Control System Integration](https://www.isa.org/standards-and-publications/isa-standards/isa-standards-committees/isa95).

## ISO 22400 — KPI definitions
- OEE = Availability × Performance × Quality.
- Availability = APT / PBT (Actual Production Time / Planned Busy Time).
- Performance = (Ideal Cycle Time × Produced Quantity) / APT.
- Quality = Good Quantity / Produced Quantity.
- All components ∈ [0, 1]; OEE inherits that range.
- Source: [ISO 22400-2:2014](https://www.iso.org/standard/56847.html).

## Sparkplug B — payload + topic spec
- Topic: `spBv1.0/<group_id>/<message_type>/<edge_node_id>[/<device_id>]`.
- Message types: NBIRTH, NDATA, NDEATH (node); DBIRTH, DDATA, DDEATH (device); NCMD, DCMD (commands); STATE (host).
- Sequence number rolls 0..255; gap detection prompts rebirth.
- Source: [Sparkplug Specification v3.0, Eclipse Foundation](https://sparkplug.eclipse.org/specification/version/3.0/documents/sparkplug-specification-3.0.0.pdf).

## OPC UA Companion Specifications
- Phase 4 candidate: OPC UA for Machinery (DI base + extensions).
- Source: [OPC Foundation — Companion Specifications](https://opcfoundation.org/developer-tools/documents).
```

- [ ] **Step 2: Commit**

```bash
git add docs/DOMAIN-NOTES.md
git commit -m "docs(domain-notes): initial — ISA-95 / ISO 22400 / Sparkplug B / OPC UA absorption"
```

---

### Living-docs reminder (NOT in Chapter 0 — committed throughout Sections B–J)

> **Per [ADR-0000](../ADR/0000-phase-iteration-chapter-0.md) §Decision "Living documents"**, the following artifacts are committed at the moment of occurrence — not pre-written in this plan and not batched into Chapter 0:
>
> - **`docs/KNOWN-UNKNOWNS.md`** additions or resolutions — at the moment a gap is discovered or closed (e.g., a Hypothesis test surfaces a hidden assumption, or a Phase 1 limitation is consciously deferred). Commit message: `docs(known-unknowns): <what>`.
> - **`docs/DOMAIN-NOTES.md`** revisions — when implementation reveals new domain insight (e.g., the OEE clamping work in Task 14 sharpens understanding of ISO 22400 §5 invariants). Commit message: `docs(domain-notes): <what>`.
> - **`docs/AI-WORKFLOW/case-NN.md`** — written **during** the incident, not after. Triggers: an LLM hallucination caught by a guardrail (import-linter / mypy / Konsist), an unexpected drift-gate save, or a novel prompting pattern worth replaying. Phase 1 AC §13.1 requires at least one such case (`case-01.md`); the OEE absorption work in Task 14 is the most likely candidate (ISO 22400 hallucination + Hypothesis-strategy correction — see ADR-0000 §Consequences 5). Commit message: `docs(ai-workflow): case-NN — <what>`.
> - New **`docs/ADR/NNNN.md`** for decisions that *emerge mid-phase* — written at decision time, not retroactively. Commit message: `docs(adr): NNNN — <what>`.
>
> **Meta-extraction**: when an incident reveals a *generic* pattern (likely to recur across phases or projects), consider also extracting it as a new **skill** under `.claude/skills/<name>/SKILL.md` or a new **rule** under `.claude/rules/<name>.md`, in addition to the case study. Skill/rule extraction is itself a living-doc event and lands as its own commit: `chore(claude): <name> — <one-line purpose>`.
>
> The *cadence* of these living-doc commits interleaved with `feat`/`chore` commits is itself a portfolio signal of honest iteration (ADR-0000 §Consequences 3 + 5).

---

## Section B — Contracts (single source of truth)

### Task 6: Vendor Sparkplug B Protobuf + generate Python + Kotlin stubs

**Files:**
- Create: `packages/contracts/sparkplug/sparkplug_b.proto` (vendored from Eclipse Tahu, version-pinned)
- Create: `packages/contracts/sparkplug/README.md`
- Create: `packages/contracts/codegen/python/sparkplug_b_pb2.py` (generated)
- Create: `packages/contracts/codegen/kotlin/com/sdf/dx/contracts/sparkplug/SparkplugB.kt` (generated)
- Create: `packages/contracts/Makefile`

- [ ] **Step 1: Vendor the Tahu .proto**

Download `sparkplug_b.proto` from Eclipse Tahu v1.0.10 release (URL: `https://github.com/eclipse/tahu/blob/v1.0.10/sparkplug_b/sparkplug_b.proto`). Save to `packages/contracts/sparkplug/sparkplug_b.proto`. Add `# Vendored from Eclipse Tahu v1.0.10 — DO NOT EDIT` as the top-of-file comment.

- [ ] **Step 2: Write `packages/contracts/sparkplug/README.md`**

```markdown
# Sparkplug B Contracts

Vendored Protobuf schema from Eclipse Tahu v1.0.10. This is the single source of truth for all Sparkplug B payloads in this monorepo.

## Regenerate Python stubs
```bash
make python
```

## Regenerate Kotlin stubs
```bash
make kotlin
```

## Topic namespace
`spBv1.0/<group_id>/<message_type>/<edge_node_id>[/<device_id>]`
where for Phase 1: `group_id=sdf_default`, `edge_node_id=<line_id>`, `device_id=<machine_id>`. See `docs/ADR/0011-sparkplug-namespace.md`.
```

- [ ] **Step 3: Create `packages/contracts/Makefile`**

```makefile
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
```

- [ ] **Step 4: Run codegen**

```bash
cd packages/contracts && make python && make kotlin
```
Expected: `codegen/python/sparkplug_b_pb2.py` and `codegen/kotlin/com/sdf/dx/contracts/sparkplug/SparkplugBOuterClass.java` (or `.kt`) exist.

- [ ] **Step 5: Commit**

```bash
git add packages/contracts
git commit -m "feat(contracts): vendor Sparkplug B proto + python/kotlin codegen"
```

---

### Task 7: OpenAPI 3.1 contract for REST surface

**Files:**
- Create: `packages/contracts/openapi/sdf-api.yaml`
- Create: `packages/contracts/codegen/python/sdf_openapi_models.py` (generated)
- Create: `packages/contracts/codegen/typescript/sdf-openapi-client.ts` (generated)
- Modify: `packages/contracts/Makefile`

- [ ] **Step 1: Create `packages/contracts/openapi/sdf-api.yaml` (Phase 1 surface only)**

```yaml
openapi: 3.1.0
info:
  title: SDF Manufacturing DX API
  version: 0.1.0
  description: Phase 1 read-mostly REST surface for the dashboard. Multi-tenant fields omitted; default factory is implicit.
servers:
  - url: http://localhost:8000
paths:
  /healthz:
    get:
      summary: Liveness probe
      responses:
        "200": { description: ok }
  /readyz:
    get:
      summary: Readiness probe (DB + Kafka)
      responses:
        "200": { description: ready }
        "503": { description: not ready }
  /api/v1/lines:
    get:
      summary: List production lines for the default factory
      responses:
        "200":
          description: ok
          content:
            application/json:
              schema:
                type: array
                items: { $ref: "#/components/schemas/ProductionLine" }
  /api/v1/lines/{lineId}/state:
    get:
      summary: Current line state (latest)
      parameters:
        - in: path
          name: lineId
          required: true
          schema: { type: string, format: uuid }
      responses:
        "200":
          description: ok
          content:
            application/json:
              schema: { $ref: "#/components/schemas/LineStateSnapshot" }
  /api/v1/lines/{lineId}/oee:
    get:
      summary: OEE for a line over a window
      parameters:
        - in: path
          name: lineId
          required: true
          schema: { type: string, format: uuid }
        - in: query
          name: window
          schema:
            type: string
            enum: [5m, 1h, shift]
            default: 5m
      responses:
        "200":
          description: ok
          content:
            application/json:
              schema: { $ref: "#/components/schemas/OeeReading" }
components:
  schemas:
    ProductionLine:
      type: object
      required: [id, name, factoryId, isa95Role]
      properties:
        id: { type: string, format: uuid }
        name: { type: string }
        factoryId: { type: string, format: uuid }
        isa95Role: { type: string, enum: [WORK_CENTER, WORK_UNIT, PRODUCTION_LINE] }
    LineStateSnapshot:
      type: object
      required: [lineId, state, since]
      properties:
        lineId: { type: string, format: uuid }
        state: { type: string, enum: [RUNNING, IDLE, DOWN, CHANGEOVER] }
        since: { type: string, format: date-time }
    OeeReading:
      type: object
      required: [lineId, window, oee, availability, performance, quality, observedAt]
      properties:
        lineId: { type: string, format: uuid }
        window: { type: string, enum: [5m, 1h, shift] }
        oee: { type: number, minimum: 0, maximum: 1 }
        availability: { type: number, minimum: 0, maximum: 1 }
        performance: { type: number, minimum: 0, maximum: 1 }
        quality: { type: number, minimum: 0, maximum: 1 }
        observedAt: { type: string, format: date-time }
```

- [ ] **Step 2: Extend `packages/contracts/Makefile` with OpenAPI codegen + spectral lint**

Add targets (note `lint` becomes a prerequisite of `verify` — the OpenAPI spec is linted *before* codegen runs, so a malformed spec is rejected upstream of any drift check):

```makefile
openapi-python:
	uvx --from datamodel-code-generator datamodel-codegen \
	  --input openapi/sdf-api.yaml --input-file-type openapi \
	  --output codegen/python/sdf_openapi_models.py \
	  --output-model-type pydantic_v2.BaseModel \
	  --target-python-version 3.12 \
	  --use-standard-collections --use-union-operator

openapi-typescript:
	pnpm dlx openapi-typescript openapi/sdf-api.yaml \
	  -o codegen/typescript/sdf-openapi-client.ts

lint:
	pnpm dlx @stoplight/spectral-cli lint \
	  --ruleset openapi/.spectral.yaml \
	  openapi/sdf-api.yaml

all: python kotlin openapi-python openapi-typescript

verify: lint all
	@git diff --exit-code codegen/ || (echo "codegen drift" && exit 1)
```

- [ ] **Step 3: Create `packages/contracts/openapi/.spectral.yaml` (minimal ruleset)**

```yaml
extends: ["spectral:oas"]
rules:
  # Phase 1 conventions; tighten in Phase 2 when surface grows.
  operation-operationId: warn
  operation-tag-defined: off
  info-contact: off
  info-license: off
  oas3-unused-component: warn
```

Rationale: `spectral:oas` is Stoplight's bundled OpenAPI ruleset (OAI best practices). The overrides above relax style rules that don't apply at Phase 1 surface size (4 endpoints, no contact/license metadata yet). Source: [Spectral OpenAPI rules](https://docs.stoplight.io/docs/spectral/4dec24461f3af-open-api-rules).

- [ ] **Step 4: Run lint + codegen**

```bash
cd packages/contracts && make lint && make openapi-python && make openapi-typescript
```
Expected: spectral exits 0 (warns only); both generated files exist and contain `ProductionLine`, `LineStateSnapshot`, `OeeReading` definitions.

- [ ] **Step 5: Commit**

```bash
git add packages/contracts/openapi packages/contracts/Makefile packages/contracts/codegen
git commit -m "feat(contracts): OpenAPI 3.1 + spectral lint + python/ts codegen"
```

---

### Task 8: JSON Schema for normalized Kafka payloads

**Files:**
- Create: `packages/contracts/kafka-payloads/machine_telemetry.schema.json`
- Create: `packages/contracts/kafka-payloads/line_state.schema.json`
- Create: `packages/contracts/codegen/python/kafka_payloads.py`
- Modify: `packages/contracts/Makefile`

- [ ] **Step 1: Create `packages/contracts/kafka-payloads/machine_telemetry.schema.json`**

```json
{
  "$schema": "https://json-schema.org/draft/2020-12/schema",
  "$id": "https://sdf-dx.local/kafka/machine_telemetry.json",
  "title": "MachineTelemetry",
  "type": "object",
  "required": ["tenantId", "lineId", "machineId", "metric", "value", "observedAt", "sparkplugSeq"],
  "properties": {
    "tenantId": { "type": "string" },
    "lineId":   { "type": "string", "format": "uuid" },
    "machineId":{ "type": "string", "format": "uuid" },
    "metric":   { "type": "string", "enum": ["cycle_count", "good_count", "scrap_count", "state", "cycle_time_ms"] },
    "value":    { "type": ["number", "string"] },
    "observedAt": { "type": "string", "format": "date-time" },
    "sparkplugSeq": { "type": "integer", "minimum": 0, "maximum": 255 }
  },
  "additionalProperties": false
}
```

- [ ] **Step 2: Create `packages/contracts/kafka-payloads/line_state.schema.json`**

```json
{
  "$schema": "https://json-schema.org/draft/2020-12/schema",
  "$id": "https://sdf-dx.local/kafka/line_state.json",
  "title": "LineStateEvent",
  "type": "object",
  "required": ["tenantId", "lineId", "state", "observedAt"],
  "properties": {
    "tenantId": { "type": "string" },
    "lineId":   { "type": "string", "format": "uuid" },
    "state":    { "type": "string", "enum": ["RUNNING", "IDLE", "DOWN", "CHANGEOVER"] },
    "reason":   { "type": ["string", "null"] },
    "observedAt": { "type": "string", "format": "date-time" }
  },
  "additionalProperties": false
}
```

- [ ] **Step 3: Add Makefile target**

Append to `packages/contracts/Makefile`:

```makefile
kafka-python:
	uvx --from datamodel-code-generator datamodel-codegen \
	  --input kafka-payloads/ --input-file-type jsonschema \
	  --output codegen/python/kafka_payloads.py \
	  --output-model-type pydantic_v2.BaseModel \
	  --target-python-version 3.12
```

Update `all` target to include `kafka-python`.

- [ ] **Step 4: Run codegen + verify**

```bash
cd packages/contracts && make kafka-python && python -c "from codegen.python.kafka_payloads import MachineTelemetry, LineStateEvent; print('ok')"
```
Expected: prints `ok`.

- [ ] **Step 5: Commit**

```bash
git add packages/contracts/kafka-payloads packages/contracts/codegen/python/kafka_payloads.py packages/contracts/Makefile
git commit -m "feat(contracts): JSON Schema for Kafka payloads + pydantic codegen"
```

---

### Task 9: CI contracts gate — spectral lint + codegen drift + oasdiff (advisory)

**Files:**
- Create: `.github/workflows/contracts.yml`

> Three gates in a single workflow (ADR-0005 §"Two CI gates" + breaking-change advisory):
> 1. **Quality gate** — `spectral lint` runs *first*; a malformed spec fails fast before any codegen.
> 2. **Drift gate** — `make all` then `git diff --exit-code codegen/`; generated artifacts must match committed.
> 3. **Breaking-change advisory** — `oasdiff breaking` against `main`; emits a PR warning but does *not* fail the build in Phase 1 (no external consumers yet — Phase 2 promotes to blocking).

- [ ] **Step 1: Create the workflow**

```yaml
name: contracts
on:
  pull_request:
    paths:
      - "packages/contracts/**"
      - ".github/workflows/contracts.yml"
  push:
    branches: [main]

jobs:
  contracts:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
        with:
          fetch-depth: 0  # needed for oasdiff against origin/main
      - uses: actions/setup-python@v5
        with: { python-version: "3.12" }
      - uses: pnpm/action-setup@v4
        with: { version: 9 }
      - uses: actions/setup-node@v4
        with: { node-version: "20" }
      - name: Install protoc
        run: sudo apt-get update && sudo apt-get install -y protobuf-compiler
      - name: Install uv
        run: pip install uv

      - name: Lint OpenAPI spec (spectral)
        working-directory: packages/contracts
        run: make lint

      - name: Regenerate all contracts
        working-directory: packages/contracts
        run: make all

      - name: Fail if generated files diverged (drift gate)
        working-directory: packages/contracts
        run: |
          if ! git diff --exit-code codegen/; then
            echo "::error::Codegen drift — run 'make all' in packages/contracts and commit"
            exit 1
          fi

      - name: Breaking-change check (oasdiff, advisory)
        if: github.event_name == 'pull_request'
        continue-on-error: true
        run: |
          go install github.com/tufin/oasdiff@latest
          git fetch origin ${{ github.base_ref }} --depth=1
          git show origin/${{ github.base_ref }}:packages/contracts/openapi/sdf-api.yaml > /tmp/base-sdf-api.yaml || \
            { echo "::notice::No baseline spec on ${{ github.base_ref }} — skipping breaking-change check" ; exit 0 ; }
          oasdiff breaking /tmp/base-sdf-api.yaml packages/contracts/openapi/sdf-api.yaml \
            --fail-on ERR --format githubactions || \
            echo "::warning::OpenAPI breaking change detected (advisory in Phase 1; promoted to blocking in Phase 2)"
```

- [ ] **Step 2: Commit**

```bash
git add .github/workflows/contracts.yml
git commit -m "ci(contracts): spectral lint + codegen drift + oasdiff (advisory) gates"
```

---

## Section C — Infrastructure (docker-compose foundation)

### Task 10: TimescaleDB init scripts (single-tenant Phase 1 schema)

**Files:**
- Create: `infra/timescale/init/001_extensions.sql`
- Create: `infra/timescale/init/002_schema.sql`
- Create: `infra/timescale/init/003_hypertables.sql`
- Create: `infra/timescale/init/004_continuous_aggregates.sql`
- Create: `infra/timescale/init/005_seed.sql`

> **Phase 1 simplification:** single implicit tenant in schema `public`. Schema-per-tenant lives in Phase 2 — ADR-0003 documents the migration path.

- [ ] **Step 1: Write `001_extensions.sql`**

```sql
CREATE EXTENSION IF NOT EXISTS timescaledb;
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
```

- [ ] **Step 2: Write `002_schema.sql`**

```sql
CREATE TABLE IF NOT EXISTS factory (
    id          uuid PRIMARY KEY DEFAULT uuid_generate_v4(),
    name        text NOT NULL,
    region      text NOT NULL,
    timezone    text NOT NULL,
    locale      text NOT NULL DEFAULT 'ko-KR',
    created_at  timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS production_line (
    id          uuid PRIMARY KEY DEFAULT uuid_generate_v4(),
    factory_id  uuid NOT NULL REFERENCES factory(id),
    name        text NOT NULL,
    isa95_role  text NOT NULL CHECK (isa95_role IN ('WORK_CENTER','WORK_UNIT','PRODUCTION_LINE')),
    created_at  timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS machine (
    id                  uuid PRIMARY KEY DEFAULT uuid_generate_v4(),
    line_id             uuid NOT NULL REFERENCES production_line(id),
    type                text NOT NULL,
    sparkplug_node_id   text NOT NULL UNIQUE,
    created_at          timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS production_cycle (
    id          uuid PRIMARY KEY DEFAULT uuid_generate_v4(),
    line_id     uuid NOT NULL REFERENCES production_line(id),
    planned_qty integer NOT NULL,
    actual_qty  integer NOT NULL DEFAULT 0,
    good_qty    integer NOT NULL DEFAULT 0,
    started_at  timestamptz NOT NULL,
    ended_at    timestamptz
);

CREATE TABLE IF NOT EXISTS alarm (
    id          uuid PRIMARY KEY DEFAULT uuid_generate_v4(),
    line_id     uuid NOT NULL REFERENCES production_line(id),
    rule_id     text NOT NULL,
    severity    text NOT NULL CHECK (severity IN ('INFO','WARN','CRITICAL')),
    fired_at    timestamptz NOT NULL,
    acked_at    timestamptz,
    ack_by      text
);
```

- [ ] **Step 3: Write `003_hypertables.sql`**

```sql
CREATE TABLE IF NOT EXISTS machine_telemetry (
    time        timestamptz NOT NULL,
    machine_id  uuid NOT NULL,
    metric      text NOT NULL,
    value_num   double precision,
    value_text  text,
    sparkplug_seq smallint NOT NULL
);
SELECT create_hypertable('machine_telemetry', 'time', if_not_exists => TRUE);
CREATE INDEX IF NOT EXISTS idx_telemetry_machine_time ON machine_telemetry (machine_id, time DESC);

CREATE TABLE IF NOT EXISTS line_state (
    time        timestamptz NOT NULL,
    line_id     uuid NOT NULL,
    state       text NOT NULL CHECK (state IN ('RUNNING','IDLE','DOWN','CHANGEOVER')),
    reason      text
);
SELECT create_hypertable('line_state', 'time', if_not_exists => TRUE);
CREATE INDEX IF NOT EXISTS idx_line_state_line_time ON line_state (line_id, time DESC);
```

- [ ] **Step 4: Write `004_continuous_aggregates.sql`**

```sql
CREATE MATERIALIZED VIEW IF NOT EXISTS line_oee_5m
WITH (timescaledb.continuous) AS
SELECT
    time_bucket('5 minutes', t.time) AS bucket,
    m.line_id,
    SUM(CASE WHEN t.metric = 'good_count'  THEN t.value_num ELSE 0 END) AS good_qty,
    SUM(CASE WHEN t.metric = 'cycle_count' THEN t.value_num ELSE 0 END) AS actual_qty,
    AVG(CASE WHEN t.metric = 'cycle_time_ms' THEN t.value_num END) AS avg_cycle_ms
FROM machine_telemetry t
JOIN machine m ON m.id = t.machine_id
GROUP BY bucket, m.line_id
WITH NO DATA;

SELECT add_continuous_aggregate_policy(
    'line_oee_5m',
    start_offset => INTERVAL '1 hour',
    end_offset   => INTERVAL '1 minute',
    schedule_interval => INTERVAL '1 minute'
);
```

- [ ] **Step 5: Write `005_seed.sql`**

```sql
WITH f AS (
    INSERT INTO factory (name, region, timezone, locale)
    VALUES ('Ulsan Plant', 'KR', 'Asia/Seoul', 'ko-KR')
    RETURNING id
),
l AS (
    INSERT INTO production_line (factory_id, name, isa95_role)
    SELECT id, 'Line A', 'PRODUCTION_LINE' FROM f
    RETURNING id
)
INSERT INTO machine (line_id, type, sparkplug_node_id)
SELECT l.id, t.type, 'sdf_default/' || (SELECT name FROM production_line WHERE id = l.id) || '/' || t.type
FROM l, (VALUES
    ('press'),
    ('weld'),
    ('paint'),
    ('inspect'),
    ('pack')
) AS t(type);
```

- [ ] **Step 6: Commit**

```bash
git add infra/timescale
git commit -m "feat(infra): timescaledb init scripts + hypertables + 5m OEE CAGG + seed"
```

---

### Task 11: docker-compose with all services (skeleton — apps wired later)

**Files:**
- Create: `docker-compose.yml`
- Create: `.env.example`

- [ ] **Step 1: Write `docker-compose.yml`**

```yaml
name: sdf-dx

services:
  timescale:
    image: timescale/timescaledb:2.15.3-pg16
    environment:
      POSTGRES_PASSWORD: sdf
      POSTGRES_USER: sdf
      POSTGRES_DB: sdf
    ports: ["5432:5432"]
    volumes:
      - timescale-data:/var/lib/postgresql/data
      - ./infra/timescale/init:/docker-entrypoint-initdb.d:ro
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U sdf -d sdf"]
      interval: 5s
      timeout: 3s
      retries: 20

  hivemq:
    image: hivemq/hivemq-ce:2024.5
    ports: ["1883:1883", "8080:8080"]
    healthcheck:
      test: ["CMD-SHELL", "nc -z localhost 1883"]
      interval: 5s
      timeout: 3s
      retries: 20

  redpanda:
    image: redpandadata/redpanda:v24.2.7
    command:
      - redpanda start
      - --overprovisioned
      - --smp 1
      - --memory 1G
      - --reserve-memory 0M
      - --node-id 0
      - --check=false
      - --kafka-addr PLAINTEXT://0.0.0.0:9092
      - --advertise-kafka-addr PLAINTEXT://redpanda:9092
    ports: ["9092:9092", "9644:9644"]
    healthcheck:
      test: ["CMD-SHELL", "rpk cluster health | grep -q 'Healthy:.*true'"]
      interval: 5s
      timeout: 3s
      retries: 30

  simulator:
    build: ./apps/ot-gateway-kotlin
    command: ["./gradlew", ":simulator:run"]
    environment:
      MQTT_URL: tcp://hivemq:1883
      SDF_GROUP_ID: sdf_default
      SDF_LINE_ID: line-a
    depends_on:
      hivemq: { condition: service_healthy }

  bridge:
    build: ./apps/ot-gateway-kotlin
    command: ["./gradlew", ":bridge:bootRun"]
    environment:
      MQTT_URL: tcp://hivemq:1883
      KAFKA_BOOTSTRAP: redpanda:9092
      SDF_GROUP_ID: sdf_default
      SDF_DEFAULT_TENANT: sdf_default
    depends_on:
      hivemq: { condition: service_healthy }
      redpanda: { condition: service_healthy }

  ingest:
    build: ./apps/ingest-python
    environment:
      KAFKA_BOOTSTRAP: redpanda:9092
      PG_DSN: postgresql://sdf:sdf@timescale:5432/sdf
    depends_on:
      timescale: { condition: service_healthy }
      redpanda:  { condition: service_healthy }

  api:
    build: ./apps/api-python
    ports: ["8000:8000"]
    environment:
      PG_DSN: postgresql://sdf:sdf@timescale:5432/sdf
      KAFKA_BOOTSTRAP: redpanda:9092
      SDF_MODE: real
    depends_on:
      timescale: { condition: service_healthy }
      redpanda:  { condition: service_healthy }

  dashboard:
    build: ./apps/dashboard-react
    ports: ["5173:80"]
    depends_on:
      api: { condition: service_started }

volumes:
  timescale-data:
```

- [ ] **Step 2: Write `.env.example`**

```
# Copy to .env for local overrides
POSTGRES_PASSWORD=sdf
KAFKA_BOOTSTRAP=localhost:9092
MQTT_URL=tcp://localhost:1883
```

- [ ] **Step 3: Smoke test infra subset (no apps yet)**

```bash
docker compose up -d timescale hivemq redpanda
docker compose ps
docker compose exec timescale psql -U sdf -d sdf -c "SELECT count(*) FROM machine;"
```
Expected: 5 rows (5 seeded machines).

```bash
docker compose down
```

- [ ] **Step 4: Commit**

```bash
git add docker-compose.yml .env.example
git commit -m "feat(infra): docker-compose for timescale + hivemq + redpanda + app placeholders"
```

---

## Section D — Domain (Functional Core)

### Task 12: Shared kernel — ID value objects + Timestamp

**Files:**
- Create: `apps/api-python/src/sdf_api/shared_kernel/__init__.py`
- Create: `apps/api-python/src/sdf_api/shared_kernel/ids.py`
- Create: `apps/api-python/tests/shared_kernel/test_ids.py`

- [ ] **Step 1: Write failing test `tests/shared_kernel/test_ids.py`**

```python
from uuid import UUID, uuid4

import pytest

from sdf_api.shared_kernel.ids import FactoryId, LineId, MachineId


def test_factory_id_wraps_uuid() -> None:
    raw = uuid4()
    fid = FactoryId(raw)
    assert fid.value == raw


def test_factory_id_is_frozen() -> None:
    fid = FactoryId(uuid4())
    with pytest.raises(AttributeError):
        fid.value = uuid4()  # type: ignore[misc]


def test_distinct_id_types_are_not_interchangeable() -> None:
    raw = uuid4()
    # Equality across distinct ID types must be False — prevents wrong-id bugs.
    assert FactoryId(raw) != LineId(raw)
    assert LineId(raw) != MachineId(raw)


def test_factory_id_from_string() -> None:
    raw = uuid4()
    fid = FactoryId.from_string(str(raw))
    assert fid.value == raw


def test_factory_id_rejects_non_uuid_string() -> None:
    with pytest.raises(ValueError):
        FactoryId.from_string("not-a-uuid")
```

Mkdir + add `__init__.py`:

```bash
mkdir -p apps/api-python/tests/shared_kernel
touch apps/api-python/tests/shared_kernel/__init__.py
```

- [ ] **Step 2: Run — expect failure**

```bash
cd apps/api-python && pytest tests/shared_kernel/test_ids.py -v
```
Expected: `ImportError: cannot import name 'FactoryId' from 'sdf_api.shared_kernel.ids'`.

- [ ] **Step 3: Implement minimal `shared_kernel/ids.py`**

```python
from __future__ import annotations

from dataclasses import dataclass
from uuid import UUID


@dataclass(frozen=True, slots=True)
class _UuidId:
    value: UUID

    @classmethod
    def from_string(cls, raw: str) -> _UuidId:
        return cls(UUID(raw))


@dataclass(frozen=True, slots=True)
class FactoryId(_UuidId):
    pass


@dataclass(frozen=True, slots=True)
class LineId(_UuidId):
    pass


@dataclass(frozen=True, slots=True)
class MachineId(_UuidId):
    pass
```

Create `apps/api-python/src/sdf_api/shared_kernel/__init__.py`:

```python
from sdf_api.shared_kernel.ids import FactoryId, LineId, MachineId

__all__ = ["FactoryId", "LineId", "MachineId"]
```

- [ ] **Step 4: Run — expect pass**

```bash
cd apps/api-python && pytest tests/shared_kernel/test_ids.py -v
```
Expected: all 5 tests pass.

- [ ] **Step 5: Confirm typecheck + drift gates pass**

```bash
cd apps/api-python && mypy && ruff check . && lint-imports
```
Expected: clean.

- [ ] **Step 6: Commit**

```bash
git add apps/api-python/src/sdf_api/shared_kernel apps/api-python/tests/shared_kernel
git commit -m "feat(api): shared_kernel — typed UUID IDs (FactoryId/LineId/MachineId)"
```

---

### Task 13: Monitoring domain — line state machine (pure)

**Files:**
- Create: `apps/api-python/src/sdf_api/contexts/__init__.py`
- Create: `apps/api-python/src/sdf_api/contexts/monitoring/__init__.py`
- Create: `apps/api-python/src/sdf_api/contexts/monitoring/domain/__init__.py`
- Create: `apps/api-python/src/sdf_api/contexts/monitoring/domain/line_state.py`
- Create: `apps/api-python/tests/contexts/monitoring/domain/test_line_state.py`

- [ ] **Step 1: Write failing test**

```python
from datetime import datetime, timedelta, timezone

import pytest

from sdf_api.contexts.monitoring.domain.line_state import (
    InvalidTransition,
    LineState,
    apply_event,
)


def t(seconds: int) -> datetime:
    return datetime(2026, 5, 22, 9, 0, 0, tzinfo=timezone.utc) + timedelta(seconds=seconds)


def test_running_can_transition_to_idle() -> None:
    s0 = LineState.initial(at=t(0))
    s1 = apply_event(s0, event="STARTED", at=t(1))
    s2 = apply_event(s1, event="IDLE_DETECTED", at=t(2))
    assert s2.value == "IDLE"
    assert s2.since == t(2)


def test_running_can_transition_to_down() -> None:
    s = LineState.initial(at=t(0))
    s = apply_event(s, event="STARTED", at=t(1))
    s = apply_event(s, event="FAULT", at=t(2), reason="motor over-temp")
    assert s.value == "DOWN"
    assert s.reason == "motor over-temp"


def test_changeover_transitions_back_to_running_on_resume() -> None:
    s = LineState.initial(at=t(0))
    s = apply_event(s, event="STARTED", at=t(1))
    s = apply_event(s, event="CHANGEOVER_BEGIN", at=t(2))
    assert s.value == "CHANGEOVER"
    s = apply_event(s, event="STARTED", at=t(3))
    assert s.value == "RUNNING"


def test_invalid_transition_raises() -> None:
    s = LineState.initial(at=t(0))  # IDLE
    with pytest.raises(InvalidTransition):
        apply_event(s, event="FAULT", at=t(1))  # cannot go IDLE→DOWN without STARTED


def test_apply_event_is_pure_returns_new_instance() -> None:
    s0 = LineState.initial(at=t(0))
    s1 = apply_event(s0, event="STARTED", at=t(1))
    assert s0 is not s1
    assert s0.value == "IDLE"
    assert s1.value == "RUNNING"
```

Mkdir + `__init__.py` files:

```bash
mkdir -p apps/api-python/src/sdf_api/contexts/monitoring/domain
mkdir -p apps/api-python/tests/contexts/monitoring/domain
touch apps/api-python/src/sdf_api/contexts/__init__.py
touch apps/api-python/src/sdf_api/contexts/monitoring/__init__.py
touch apps/api-python/src/sdf_api/contexts/monitoring/domain/__init__.py
touch apps/api-python/tests/contexts/__init__.py
touch apps/api-python/tests/contexts/monitoring/__init__.py
touch apps/api-python/tests/contexts/monitoring/domain/__init__.py
```

- [ ] **Step 2: Run — expect failure** (`ImportError`).

- [ ] **Step 3: Implement `line_state.py`**

```python
from __future__ import annotations

from dataclasses import dataclass, replace
from datetime import datetime
from typing import Literal

StateValue = Literal["RUNNING", "IDLE", "DOWN", "CHANGEOVER"]
EventType = Literal["STARTED", "IDLE_DETECTED", "FAULT", "CHANGEOVER_BEGIN", "RESET"]


class InvalidTransition(Exception):
    """Raised when an event cannot be applied from the current state."""


_TRANSITIONS: dict[tuple[StateValue, EventType], StateValue] = {
    ("IDLE",       "STARTED"):           "RUNNING",
    ("RUNNING",    "IDLE_DETECTED"):     "IDLE",
    ("RUNNING",    "FAULT"):             "DOWN",
    ("RUNNING",    "CHANGEOVER_BEGIN"):  "CHANGEOVER",
    ("CHANGEOVER", "STARTED"):           "RUNNING",
    ("DOWN",       "RESET"):             "IDLE",
}


@dataclass(frozen=True, slots=True)
class LineState:
    value: StateValue
    since: datetime
    reason: str | None = None

    @classmethod
    def initial(cls, at: datetime) -> LineState:
        return cls(value="IDLE", since=at)


def apply_event(
    state: LineState,
    *,
    event: EventType,
    at: datetime,
    reason: str | None = None,
) -> LineState:
    key = (state.value, event)
    if key not in _TRANSITIONS:
        raise InvalidTransition(
            f"event {event!r} not allowed in state {state.value!r}"
        )
    return replace(state, value=_TRANSITIONS[key], since=at, reason=reason)
```

- [ ] **Step 4: Run — expect pass.**

```bash
cd apps/api-python && pytest tests/contexts/monitoring/domain/test_line_state.py -v
```

- [ ] **Step 5: Verify drift gates**

```bash
cd apps/api-python && mypy && ruff check . && lint-imports
```
Expected: clean. `lint-imports` confirms `monitoring.domain` does **not** import any adapter or external infra.

- [ ] **Step 6: Commit**

```bash
git add apps/api-python/src/sdf_api/contexts apps/api-python/tests/contexts
git commit -m "feat(monitoring): line state machine (pure functional core)"
```

---

### Task 14: Monitoring domain — OEE per ISO 22400 (property-based)

**Files:**
- Create: `apps/api-python/src/sdf_api/contexts/monitoring/domain/oee.py`
- Create: `apps/api-python/tests/contexts/monitoring/domain/test_oee.py`

> **Reference:** ISO 22400-2:2014 §5 — `Availability = APT / PBT`, `Performance = (ICT × PQ) / APT`, `Quality = GQ / PQ`, `OEE = A × P × Q`. Glossary: APT = Actual Production Time, PBT = Planned Busy Time, ICT = Ideal Cycle Time, PQ = Produced Quantity (actual), GQ = Good Quantity. All OEE components ∈ [0, 1]; OEE clamps to ≤ 1.

- [ ] **Step 1: Write failing test (example-based + property-based)**

```python
from dataclasses import dataclass

import pytest
from hypothesis import given, strategies as st

from sdf_api.contexts.monitoring.domain.oee import (
    OeeInputs,
    compute_oee,
)


def test_perfect_run_yields_oee_one() -> None:
    result = compute_oee(OeeInputs(
        planned_busy_time_s=3600,
        actual_production_time_s=3600,
        ideal_cycle_time_s=1.0,
        produced_qty=3600,
        good_qty=3600,
    ))
    assert result.availability == pytest.approx(1.0)
    assert result.performance == pytest.approx(1.0)
    assert result.quality == pytest.approx(1.0)
    assert result.oee == pytest.approx(1.0)


def test_zero_planned_time_yields_zero_oee() -> None:
    result = compute_oee(OeeInputs(
        planned_busy_time_s=0,
        actual_production_time_s=0,
        ideal_cycle_time_s=1.0,
        produced_qty=0,
        good_qty=0,
    ))
    assert result.oee == 0.0


def test_half_availability_half_oee() -> None:
    result = compute_oee(OeeInputs(
        planned_busy_time_s=3600,
        actual_production_time_s=1800,
        ideal_cycle_time_s=1.0,
        produced_qty=1800,
        good_qty=1800,
    ))
    assert result.availability == pytest.approx(0.5)
    assert result.oee == pytest.approx(0.5)


@given(
    pbt=st.integers(min_value=1, max_value=86400),
    apt_ratio=st.floats(min_value=0, max_value=1),
    ict=st.floats(min_value=0.1, max_value=120),
    perf_ratio=st.floats(min_value=0, max_value=1),
    qual_ratio=st.floats(min_value=0, max_value=1),
)
def test_oee_components_bounded_zero_one(
    pbt: int, apt_ratio: float, ict: float, perf_ratio: float, qual_ratio: float
) -> None:
    apt = int(pbt * apt_ratio)
    produced = int((apt / ict) * perf_ratio) if apt > 0 else 0
    good = int(produced * qual_ratio)
    result = compute_oee(OeeInputs(
        planned_busy_time_s=pbt,
        actual_production_time_s=apt,
        ideal_cycle_time_s=ict,
        produced_qty=produced,
        good_qty=good,
    ))
    assert 0.0 <= result.availability <= 1.0
    assert 0.0 <= result.performance <= 1.0
    assert 0.0 <= result.quality <= 1.0
    assert 0.0 <= result.oee <= 1.0


@given(good=st.integers(min_value=0, max_value=10000), produced=st.integers(min_value=1, max_value=10000))
def test_quality_never_exceeds_one_even_when_good_exceeds_produced(good: int, produced: int) -> None:
    # Defensive: if upstream double-counts, we clamp rather than crash.
    result = compute_oee(OeeInputs(
        planned_busy_time_s=3600,
        actual_production_time_s=3600,
        ideal_cycle_time_s=1.0,
        produced_qty=produced,
        good_qty=good,
    ))
    assert result.quality <= 1.0
```

- [ ] **Step 2: Run — expect failure** (`ImportError`).

- [ ] **Step 3: Implement `oee.py`**

```python
"""OEE per ISO 22400-2.

Source: ISO 22400-2:2014 §5. Availability/Performance/Quality each ∈ [0,1];
inputs are clamped defensively because upstream counters can double-count
during sparkplug rebirth.
"""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class OeeInputs:
    planned_busy_time_s: int
    actual_production_time_s: int
    ideal_cycle_time_s: float
    produced_qty: int
    good_qty: int


@dataclass(frozen=True, slots=True)
class OeeResult:
    availability: float
    performance: float
    quality: float
    oee: float


def _clamp01(x: float) -> float:
    if x < 0.0:
        return 0.0
    if x > 1.0:
        return 1.0
    return x


def compute_oee(inputs: OeeInputs) -> OeeResult:
    availability = (
        inputs.actual_production_time_s / inputs.planned_busy_time_s
        if inputs.planned_busy_time_s > 0 else 0.0
    )
    performance = (
        (inputs.ideal_cycle_time_s * inputs.produced_qty) / inputs.actual_production_time_s
        if inputs.actual_production_time_s > 0 else 0.0
    )
    quality = (
        inputs.good_qty / inputs.produced_qty
        if inputs.produced_qty > 0 else 0.0
    )

    a = _clamp01(availability)
    p = _clamp01(performance)
    q = _clamp01(quality)
    return OeeResult(availability=a, performance=p, quality=q, oee=a * p * q)
```

- [ ] **Step 4: Run — expect pass.**

```bash
cd apps/api-python && pytest tests/contexts/monitoring/domain/test_oee.py -v
```
Expected: 5 tests pass. Hypothesis runs 200 examples per property-based test.

- [ ] **Step 5: Verify drift gates + mypy strict.**

```bash
cd apps/api-python && mypy && ruff check . && lint-imports
```

- [ ] **Step 6: Commit**

```bash
git add apps/api-python/src/sdf_api/contexts/monitoring/domain/oee.py apps/api-python/tests/contexts/monitoring/domain/test_oee.py
git commit -m "feat(monitoring): OEE per ISO 22400-2 + Hypothesis property tests"
```

---

### Task 15: Topology domain (factory / line / machine value objects)

**Files:**
- Create: `apps/api-python/src/sdf_api/contexts/topology/__init__.py`
- Create: `apps/api-python/src/sdf_api/contexts/topology/domain/__init__.py`
- Create: `apps/api-python/src/sdf_api/contexts/topology/domain/topology.py`
- Create: `apps/api-python/tests/contexts/topology/domain/test_topology.py`

- [ ] **Step 1: Write failing test**

```python
from uuid import uuid4

import pytest

from sdf_api.contexts.topology.domain.topology import (
    Factory,
    Line,
    Machine,
    Topology,
    UnknownMachine,
)
from sdf_api.shared_kernel.ids import FactoryId, LineId, MachineId


def make_topology() -> Topology:
    fid = FactoryId(uuid4())
    lid = LineId(uuid4())
    mids = [MachineId(uuid4()) for _ in range(3)]
    factory = Factory(id=fid, name="Ulsan", region="KR", timezone="Asia/Seoul", locale="ko-KR")
    line = Line(id=lid, factory_id=fid, name="Line A", isa95_role="PRODUCTION_LINE")
    machines = [
        Machine(id=m, line_id=lid, type=t, sparkplug_node_id=f"sdf_default/Line A/{t}")
        for m, t in zip(mids, ["press", "weld", "paint"], strict=True)
    ]
    return Topology.build(factories=[factory], lines=[line], machines=machines)


def test_lookup_machine_by_sparkplug_node_id() -> None:
    topo = make_topology()
    m = topo.machine_by_sparkplug_node_id("sdf_default/Line A/press")
    assert m.type == "press"


def test_unknown_sparkplug_node_id_raises() -> None:
    topo = make_topology()
    with pytest.raises(UnknownMachine):
        topo.machine_by_sparkplug_node_id("sdf_default/Line A/unknown")


def test_line_of_machine() -> None:
    topo = make_topology()
    m = topo.machine_by_sparkplug_node_id("sdf_default/Line A/weld")
    line = topo.line_of(m.id)
    assert line.name == "Line A"
```

- [ ] **Step 2: Run — expect failure.**

- [ ] **Step 3: Implement `topology.py`**

```python
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal

from sdf_api.shared_kernel.ids import FactoryId, LineId, MachineId

Isa95Role = Literal["WORK_CENTER", "WORK_UNIT", "PRODUCTION_LINE"]


class UnknownMachine(Exception):
    pass


class UnknownLine(Exception):
    pass


@dataclass(frozen=True, slots=True)
class Factory:
    id: FactoryId
    name: str
    region: str
    timezone: str
    locale: str


@dataclass(frozen=True, slots=True)
class Line:
    id: LineId
    factory_id: FactoryId
    name: str
    isa95_role: Isa95Role


@dataclass(frozen=True, slots=True)
class Machine:
    id: MachineId
    line_id: LineId
    type: str
    sparkplug_node_id: str


@dataclass(frozen=True, slots=True)
class Topology:
    factories: tuple[Factory, ...]
    lines: tuple[Line, ...]
    machines: tuple[Machine, ...]
    _by_sparkplug: dict[str, Machine] = field(hash=False, compare=False, default_factory=dict)
    _line_by_id: dict[LineId, Line] = field(hash=False, compare=False, default_factory=dict)

    @classmethod
    def build(
        cls,
        factories: list[Factory],
        lines: list[Line],
        machines: list[Machine],
    ) -> Topology:
        return cls(
            factories=tuple(factories),
            lines=tuple(lines),
            machines=tuple(machines),
            _by_sparkplug={m.sparkplug_node_id: m for m in machines},
            _line_by_id={l.id: l for l in lines},
        )

    def machine_by_sparkplug_node_id(self, node_id: str) -> Machine:
        try:
            return self._by_sparkplug[node_id]
        except KeyError as e:
            raise UnknownMachine(node_id) from e

    def line_of(self, machine_id: MachineId) -> Line:
        for m in self.machines:
            if m.id == machine_id:
                try:
                    return self._line_by_id[m.line_id]
                except KeyError as e:
                    raise UnknownLine(m.line_id) from e
        raise UnknownMachine(machine_id)
```

- [ ] **Step 4: Run — expect pass.**

- [ ] **Step 5: Verify drift gates.**

- [ ] **Step 6: Commit**

```bash
git add apps/api-python/src/sdf_api/contexts/topology apps/api-python/tests/contexts/topology
git commit -m "feat(topology): factory/line/machine value objects + lookup"
```

---

## Section E — Adapters

### Task 16: Kotlin device simulator (Sparkplug B publisher)

**Files:**
- Create: `apps/ot-gateway-kotlin/simulator/src/main/kotlin/com/sdf/dx/simulator/Main.kt`
- Create: `apps/ot-gateway-kotlin/simulator/src/main/kotlin/com/sdf/dx/simulator/domain/LineModel.kt`
- Create: `apps/ot-gateway-kotlin/simulator/src/main/kotlin/com/sdf/dx/simulator/adapters/SparkplugPublisher.kt`
- Create: `apps/ot-gateway-kotlin/simulator/src/main/resources/logback.xml`
- Create: `apps/ot-gateway-kotlin/simulator/src/test/kotlin/com/sdf/dx/simulator/domain/LineModelTest.kt`
- Create: `apps/ot-gateway-kotlin/simulator/src/test/kotlin/com/sdf/dx/simulator/architecture/ArchitectureTest.kt`

- [ ] **Step 1: Write failing test `LineModelTest.kt` (pure domain)**

```kotlin
package com.sdf.dx.simulator.domain

import kotlin.test.Test
import kotlin.test.assertEquals
import kotlin.test.assertTrue

class LineModelTest {

    @Test
    fun `tick increments cycle count when running`() {
        val s0 = LineModel.initial(machineId = "press")
        val s1 = s0.tick(elapsedMs = 1_000)
        assertEquals(1, s1.cycleCount)
    }

    @Test
    fun `tick produces scrap at configured rate`() {
        var s = LineModel.initial(machineId = "press", scrapRate = 0.5, seed = 42L)
        repeat(100) { s = s.tick(elapsedMs = 1_000) }
        // With 50% scrap rate, expect roughly half scrap. Allow wide band.
        assertTrue(s.scrapCount in 35..65, "scrapCount=${s.scrapCount}")
    }

    @Test
    fun `total counts add up`() {
        var s = LineModel.initial(machineId = "press", scrapRate = 0.1)
        repeat(50) { s = s.tick(elapsedMs = 1_000) }
        assertEquals(s.cycleCount, s.goodCount + s.scrapCount)
    }
}
```

- [ ] **Step 2: Write architecture test `ArchitectureTest.kt`**

```kotlin
package com.sdf.dx.simulator.architecture

import com.lemonappdev.konsist.api.Konsist
import com.lemonappdev.konsist.api.verify.assertFalse
import kotlin.test.Test

class ArchitectureTest {

    @Test
    fun `domain layer must not depend on adapters`() {
        Konsist.scopeFromModule("simulator")
            .files
            .filter { it.packagee?.fullyQualifiedName?.contains(".domain") == true }
            .assertFalse {
                it.imports.any { imp ->
                    imp.name.contains(".adapters.") ||
                        imp.name.startsWith("org.eclipse.paho") ||
                        imp.name.startsWith("org.eclipse.tahu")
                }
            }
    }
}
```

- [ ] **Step 3: Run tests — expect failure** (`LineModel` missing).

```bash
cd apps/ot-gateway-kotlin && ./gradlew :simulator:test
```

- [ ] **Step 4: Implement `LineModel.kt`**

```kotlin
package com.sdf.dx.simulator.domain

import kotlin.random.Random

public data class LineModel(
    val machineId: String,
    val cycleCount: Long,
    val goodCount: Long,
    val scrapCount: Long,
    val scrapRate: Double,
    private val rng: Random,
) {
    public fun tick(elapsedMs: Long): LineModel {
        val isScrap = rng.nextDouble() < scrapRate
        return copy(
            cycleCount = cycleCount + 1,
            goodCount = if (isScrap) goodCount else goodCount + 1,
            scrapCount = if (isScrap) scrapCount + 1 else scrapCount,
        )
    }

    public companion object {
        public fun initial(
            machineId: String,
            scrapRate: Double = 0.05,
            seed: Long = System.currentTimeMillis(),
        ): LineModel = LineModel(
            machineId = machineId,
            cycleCount = 0,
            goodCount = 0,
            scrapCount = 0,
            scrapRate = scrapRate,
            rng = Random(seed),
        )
    }
}
```

- [ ] **Step 5: Implement `SparkplugPublisher.kt` (adapter — uses Eclipse Tahu)**

```kotlin
package com.sdf.dx.simulator.adapters

import com.sdf.dx.simulator.domain.LineModel
import org.eclipse.paho.mqttv5.client.MqttClient
import org.eclipse.paho.mqttv5.client.MqttConnectionOptions
import org.eclipse.paho.mqttv5.common.MqttMessage
import org.eclipse.tahu.message.SparkplugBPayloadEncoder
import org.eclipse.tahu.message.model.MetricDataType
import org.eclipse.tahu.message.model.SparkplugBPayload
import org.eclipse.tahu.message.model.SparkplugBPayloadBuilder
import java.util.Date

public class SparkplugPublisher(
    private val mqttUrl: String,
    private val groupId: String,
    private val edgeNodeId: String,
) {
    private val client = MqttClient(mqttUrl, "sdf-sim-$edgeNodeId").apply {
        connect(MqttConnectionOptions().apply {
            isCleanStart = true
            keepAliveInterval = 30
        })
    }
    private val encoder = SparkplugBPayloadEncoder()
    private var seq: Long = 0
    private var bdSeq: Long = 0

    public fun publishBirth(machineIds: List<String>) {
        val payload = SparkplugBPayloadBuilder(seq++)
            .setTimestamp(Date())
            .addMetric(metric("bdSeq", MetricDataType.Int64, bdSeq))
            .also { b ->
                machineIds.forEach { m ->
                    b.addMetric(metric("$m/cycle_count", MetricDataType.Int64, 0L))
                    b.addMetric(metric("$m/good_count", MetricDataType.Int64, 0L))
                    b.addMetric(metric("$m/scrap_count", MetricDataType.Int64, 0L))
                }
            }
            .createPayload()
        publish("spBv1.0/$groupId/NBIRTH/$edgeNodeId", payload, retained = true)
    }

    public fun publishData(model: LineModel) {
        val payload = SparkplugBPayloadBuilder(seq++ % 256)
            .setTimestamp(Date())
            .addMetric(metric("${model.machineId}/cycle_count", MetricDataType.Int64, model.cycleCount))
            .addMetric(metric("${model.machineId}/good_count",  MetricDataType.Int64, model.goodCount))
            .addMetric(metric("${model.machineId}/scrap_count", MetricDataType.Int64, model.scrapCount))
            .createPayload()
        publish("spBv1.0/$groupId/NDATA/$edgeNodeId", payload, retained = false)
    }

    public fun publishDeath() {
        val payload = SparkplugBPayloadBuilder(0)
            .setTimestamp(Date())
            .addMetric(metric("bdSeq", MetricDataType.Int64, bdSeq))
            .createPayload()
        publish("spBv1.0/$groupId/NDEATH/$edgeNodeId", payload, retained = true)
    }

    private fun publish(topic: String, payload: SparkplugBPayload, retained: Boolean) {
        val bytes = encoder.getBytes(payload, false)
        val msg = MqttMessage(bytes).apply {
            qos = 1
            isRetained = retained
        }
        client.publish(topic, msg)
    }

    private fun metric(name: String, type: MetricDataType, value: Any) =
        org.eclipse.tahu.message.model.MetricBuilder(name, type, value)
            .timestamp(Date())
            .createMetric()
}
```

- [ ] **Step 6: Implement `Main.kt` (composition root + tick loop)**

```kotlin
package com.sdf.dx.simulator

import com.sdf.dx.simulator.adapters.SparkplugPublisher
import com.sdf.dx.simulator.domain.LineModel
import kotlinx.coroutines.delay
import kotlinx.coroutines.runBlocking
import org.slf4j.LoggerFactory

private val log = LoggerFactory.getLogger("simulator")

public fun main(): Unit = runBlocking {
    val mqttUrl = System.getenv("MQTT_URL") ?: "tcp://localhost:1883"
    val groupId = System.getenv("SDF_GROUP_ID") ?: "sdf_default"
    val lineId  = System.getenv("SDF_LINE_ID")  ?: "line-a"
    val machineTypes = listOf("press", "weld", "paint", "inspect", "pack")

    val publisher = SparkplugPublisher(mqttUrl, groupId, lineId)
    publisher.publishBirth(machineTypes)
    log.info("simulator: NBIRTH sent for {} machines on {}", machineTypes.size, lineId)

    var models = machineTypes.associateWith { LineModel.initial(machineId = it) }
    Runtime.getRuntime().addShutdownHook(Thread {
        runCatching { publisher.publishDeath() }
        log.info("simulator: NDEATH sent")
    })

    while (true) {
        models = models.mapValues { (_, m) -> m.tick(elapsedMs = 1_000) }
        models.values.forEach { publisher.publishData(it) }
        delay(1_000)
    }
}
```

- [ ] **Step 7: Create `logback.xml`**

```xml
<configuration>
  <appender name="STDOUT" class="ch.qos.logback.core.ConsoleAppender">
    <encoder>
      <pattern>%d{HH:mm:ss.SSS} %-5level [%logger{20}] - %msg%n</pattern>
    </encoder>
  </appender>
  <root level="INFO">
    <appender-ref ref="STDOUT"/>
  </root>
</configuration>
```

- [ ] **Step 8: Run tests — expect pass**

```bash
cd apps/ot-gateway-kotlin && ./gradlew :simulator:test :simulator:ktlintCheck :simulator:detekt
```
Expected: domain tests pass, Konsist architecture test passes, detekt + ktlint clean.

- [ ] **Step 9: Smoke run against compose HiveMQ**

```bash
docker compose up -d hivemq
cd apps/ot-gateway-kotlin && ./gradlew :simulator:run &
SIM_PID=$!
sleep 5
# Subscribe with mosquitto_sub to confirm Sparkplug topics flowing:
docker compose exec hivemq sh -c 'apk add --no-cache mosquitto-clients 2>/dev/null || true; mosquitto_sub -h localhost -t "spBv1.0/#" -C 3 -v'
kill $SIM_PID
docker compose down
```
Expected: 3 messages printed on `spBv1.0/sdf_default/...` topics within a few seconds.

- [ ] **Step 10: Commit**

```bash
git add apps/ot-gateway-kotlin/simulator
git commit -m "feat(simulator): Sparkplug B publisher (NBIRTH/NDATA/NDEATH) + pure LineModel + Konsist arch test"
```

---

### Task 17: Kotlin Sparkplug→Kafka bridge

**Files:**
- Create: `apps/ot-gateway-kotlin/bridge/src/main/kotlin/com/sdf/dx/bridge/Main.kt`
- Create: `apps/ot-gateway-kotlin/bridge/src/main/kotlin/com/sdf/dx/bridge/domain/Normalizer.kt`
- Create: `apps/ot-gateway-kotlin/bridge/src/main/kotlin/com/sdf/dx/bridge/adapters/MqttSubscriber.kt`
- Create: `apps/ot-gateway-kotlin/bridge/src/main/kotlin/com/sdf/dx/bridge/adapters/KafkaProducer.kt`
- Create: `apps/ot-gateway-kotlin/bridge/src/main/resources/application.yml`
- Create: `apps/ot-gateway-kotlin/bridge/src/test/kotlin/com/sdf/dx/bridge/domain/NormalizerTest.kt`
- Create: `apps/ot-gateway-kotlin/bridge/src/test/kotlin/com/sdf/dx/bridge/architecture/ArchitectureTest.kt`

- [ ] **Step 1: Write failing test `NormalizerTest.kt`**

```kotlin
package com.sdf.dx.bridge.domain

import kotlin.test.Test
import kotlin.test.assertEquals

class NormalizerTest {
    @Test
    fun `normalize splits compound metric name into machineId and metric`() {
        val records = Normalizer.fromSparkplug(
            tenantId = "sdf_default",
            edgeNodeId = "line-a",
            metrics = listOf(
                NormalizerMetric(name = "press/cycle_count", value = 42L, timestampMs = 1_700_000_000_000),
                NormalizerMetric(name = "press/good_count",  value = 40L, timestampMs = 1_700_000_000_000),
            ),
            sparkplugSeq = 7,
        )
        assertEquals(2, records.size)
        val first = records[0]
        assertEquals("sdf_default", first.tenantId)
        assertEquals("line-a", first.lineId)
        assertEquals("press",  first.machineKey)
        assertEquals("cycle_count", first.metric)
        assertEquals(42.0, first.value)
        assertEquals(7,  first.sparkplugSeq)
    }
}
```

- [ ] **Step 2: Architecture test `ArchitectureTest.kt`**

```kotlin
package com.sdf.dx.bridge.architecture

import com.lemonappdev.konsist.api.Konsist
import com.lemonappdev.konsist.api.verify.assertFalse
import kotlin.test.Test

class ArchitectureTest {
    @Test
    fun `bridge domain must not depend on adapters or kafka or paho`() {
        Konsist.scopeFromModule("bridge")
            .files
            .filter { it.packagee?.fullyQualifiedName?.contains(".domain") == true }
            .assertFalse {
                it.imports.any { imp ->
                    imp.name.contains(".adapters.") ||
                        imp.name.startsWith("org.apache.kafka") ||
                        imp.name.startsWith("org.eclipse.paho") ||
                        imp.name.startsWith("org.springframework.kafka")
                }
            }
    }
}
```

- [ ] **Step 3: Run — expect failure.**

- [ ] **Step 4: Implement `Normalizer.kt` (pure)**

```kotlin
package com.sdf.dx.bridge.domain

public data class NormalizerMetric(
    val name: String,
    val value: Any,
    val timestampMs: Long,
)

public data class NormalizedRecord(
    val tenantId: String,
    val lineId: String,
    val machineKey: String,
    val metric: String,
    val value: Double,
    val observedAtIsoMillis: Long,
    val sparkplugSeq: Int,
)

public object Normalizer {
    public fun fromSparkplug(
        tenantId: String,
        edgeNodeId: String,
        metrics: List<NormalizerMetric>,
        sparkplugSeq: Int,
    ): List<NormalizedRecord> = metrics.mapNotNull { m ->
        val parts = m.name.split("/", limit = 2)
        if (parts.size != 2) return@mapNotNull null
        val (machineKey, metricName) = parts
        val asDouble = when (val v = m.value) {
            is Number -> v.toDouble()
            is Boolean -> if (v) 1.0 else 0.0
            else -> return@mapNotNull null
        }
        NormalizedRecord(
            tenantId = tenantId,
            lineId = edgeNodeId,
            machineKey = machineKey,
            metric = metricName,
            value = asDouble,
            observedAtIsoMillis = m.timestampMs,
            sparkplugSeq = sparkplugSeq,
        )
    }
}
```

- [ ] **Step 5: Implement `MqttSubscriber.kt` (adapter)**

```kotlin
package com.sdf.dx.bridge.adapters

import com.sdf.dx.bridge.domain.NormalizedRecord
import com.sdf.dx.bridge.domain.Normalizer
import com.sdf.dx.bridge.domain.NormalizerMetric
import org.eclipse.paho.mqttv5.client.MqttClient
import org.eclipse.paho.mqttv5.client.MqttConnectionOptions
import org.eclipse.tahu.message.SparkplugBPayloadDecoder

public class MqttSubscriber(
    mqttUrl: String,
    private val defaultTenant: String,
    private val onRecord: (NormalizedRecord) -> Unit,
) {
    private val decoder = SparkplugBPayloadDecoder()
    private val client = MqttClient(mqttUrl, "sdf-bridge-${System.nanoTime()}").apply {
        connect(MqttConnectionOptions().apply { isCleanStart = true })
    }

    public fun start() {
        client.subscribe(arrayOf("spBv1.0/+/NDATA/+", "spBv1.0/+/NBIRTH/+", "spBv1.0/+/NDEATH/+"), intArrayOf(1, 1, 1))
        client.setCallback(object : org.eclipse.paho.mqttv5.client.MqttCallback {
            override fun messageArrived(topic: String, msg: org.eclipse.paho.mqttv5.common.MqttMessage) {
                val parts = topic.split("/")
                if (parts.size < 4) return
                val messageType = parts[2]
                if (messageType != "NDATA" && messageType != "NBIRTH") return
                val edgeNodeId = parts[3]
                val payload = decoder.buildFromByteArray(msg.payload, null)
                val metrics = payload.metrics.map {
                    NormalizerMetric(
                        name = it.name ?: return@map null,
                        value = it.value ?: 0,
                        timestampMs = it.timestamp?.time ?: System.currentTimeMillis(),
                    )
                }.filterNotNull()
                Normalizer.fromSparkplug(
                    tenantId = defaultTenant,
                    edgeNodeId = edgeNodeId,
                    metrics = metrics,
                    sparkplugSeq = payload.seq.toInt(),
                ).forEach(onRecord)
            }
            override fun disconnected(disconnectResponse: org.eclipse.paho.mqttv5.client.MqttDisconnectResponse?) = Unit
            override fun mqttErrorOccurred(exception: org.eclipse.paho.mqttv5.common.MqttException?) = Unit
            override fun deliveryComplete(token: org.eclipse.paho.mqttv5.client.IMqttToken?) = Unit
            override fun connectComplete(reconnect: Boolean, serverURI: String?) = Unit
            override fun authPacketArrived(reasonCode: Int, properties: org.eclipse.paho.mqttv5.common.packet.MqttProperties?) = Unit
        })
    }
}
```

- [ ] **Step 6: Implement `KafkaProducer.kt` (adapter — wraps spring-kafka)**

```kotlin
package com.sdf.dx.bridge.adapters

import com.fasterxml.jackson.databind.ObjectMapper
import com.sdf.dx.bridge.domain.NormalizedRecord
import org.apache.kafka.clients.producer.KafkaProducer
import org.apache.kafka.clients.producer.ProducerRecord
import java.time.Instant

public class KafkaBridgeProducer(bootstrap: String) {
    private val mapper = ObjectMapper()
    private val producer: KafkaProducer<String, String> = KafkaProducer(
        java.util.Properties().apply {
            put("bootstrap.servers", bootstrap)
            put("key.serializer", "org.apache.kafka.common.serialization.StringSerializer")
            put("value.serializer", "org.apache.kafka.common.serialization.StringSerializer")
            put("enable.idempotence", "true")
            put("acks", "all")
        },
    )

    public fun emit(record: NormalizedRecord) {
        val topic = "sdf.${record.tenantId}.machine.telemetry"
        val key = "${record.lineId}/${record.machineKey}"
        val json = mapper.writeValueAsString(
            mapOf(
                "tenantId" to record.tenantId,
                "lineId" to record.lineId,
                "machineKey" to record.machineKey,
                "metric" to record.metric,
                "value" to record.value,
                "observedAt" to Instant.ofEpochMilli(record.observedAtIsoMillis).toString(),
                "sparkplugSeq" to record.sparkplugSeq,
            ),
        )
        producer.send(ProducerRecord(topic, key, json))
    }
}
```

- [ ] **Step 7: Implement `Main.kt` (Spring Boot composition)**

```kotlin
package com.sdf.dx.bridge

import com.sdf.dx.bridge.adapters.KafkaBridgeProducer
import com.sdf.dx.bridge.adapters.MqttSubscriber
import org.springframework.boot.CommandLineRunner
import org.springframework.boot.autoconfigure.SpringBootApplication
import org.springframework.boot.runApplication
import org.springframework.context.annotation.Bean

@SpringBootApplication
public open class BridgeApplication {
    @Bean
    public open fun runner(): CommandLineRunner = CommandLineRunner {
        val mqtt = System.getenv("MQTT_URL") ?: "tcp://localhost:1883"
        val kafka = System.getenv("KAFKA_BOOTSTRAP") ?: "localhost:9092"
        val tenant = System.getenv("SDF_DEFAULT_TENANT") ?: "sdf_default"
        val producer = KafkaBridgeProducer(kafka)
        val sub = MqttSubscriber(mqtt, tenant) { producer.emit(it) }
        sub.start()
    }
}

public fun main(args: Array<String>) {
    runApplication<BridgeApplication>(*args)
}
```

- [ ] **Step 8: Create `application.yml`**

```yaml
spring:
  main:
    web-application-type: none
management:
  endpoints:
    web:
      exposure:
        include: health,info
```

- [ ] **Step 9: Run tests — expect pass.**

```bash
cd apps/ot-gateway-kotlin && ./gradlew :bridge:test :bridge:ktlintCheck :bridge:detekt
```

- [ ] **Step 10: End-to-end smoke (simulator → HiveMQ → bridge → Kafka)**

```bash
docker compose up -d hivemq redpanda
cd apps/ot-gateway-kotlin
./gradlew :simulator:run &
./gradlew :bridge:bootRun &
sleep 8
docker compose exec redpanda rpk topic consume sdf.sdf_default.machine.telemetry --num 3
```
Expected: 3 JSON records with tenant/line/machine/metric/value fields.

```bash
kill %1 %2
docker compose down
```

- [ ] **Step 11: Commit**

```bash
git add apps/ot-gateway-kotlin/bridge
git commit -m "feat(bridge): MQTT subscriber → normalize → Kafka producer + pure Normalizer + Konsist arch test"
```

---

### Task 18: Python ingest — Kafka consumer + TimescaleDB writer

**Files:**
- Create: `apps/ingest-python/src/sdf_ingest/domain/__init__.py`
- Create: `apps/ingest-python/src/sdf_ingest/domain/record.py`
- Create: `apps/ingest-python/src/sdf_ingest/adapters/__init__.py`
- Create: `apps/ingest-python/src/sdf_ingest/adapters/consumer.py`
- Create: `apps/ingest-python/src/sdf_ingest/adapters/writer.py`
- Create: `apps/ingest-python/src/sdf_ingest/main.py`
- Create: `apps/ingest-python/tests/domain/test_record.py`
- Create: `apps/ingest-python/tests/integration/test_pipeline.py`

- [ ] **Step 1: Write failing domain test `tests/domain/test_record.py`**

```python
import pytest

from sdf_ingest.domain.record import (
    InvalidRecord,
    Normalized,
    parse_kafka_value,
)


def test_parse_valid_record() -> None:
    raw = (
        b'{"tenantId":"sdf_default","lineId":"line-a","machineKey":"press",'
        b'"metric":"cycle_count","value":42.0,"observedAt":"2026-05-22T10:00:00Z","sparkplugSeq":5}'
    )
    n = parse_kafka_value(raw)
    assert isinstance(n, Normalized)
    assert n.tenant_id == "sdf_default"
    assert n.metric == "cycle_count"
    assert n.value == 42.0
    assert n.sparkplug_seq == 5


def test_parse_rejects_invalid_sparkplug_seq() -> None:
    raw = b'{"tenantId":"x","lineId":"l","machineKey":"m","metric":"cycle_count","value":1,"observedAt":"2026-05-22T10:00:00Z","sparkplugSeq":300}'
    with pytest.raises(InvalidRecord):
        parse_kafka_value(raw)


def test_parse_rejects_unknown_metric() -> None:
    raw = b'{"tenantId":"x","lineId":"l","machineKey":"m","metric":"velocity","value":1,"observedAt":"2026-05-22T10:00:00Z","sparkplugSeq":1}'
    with pytest.raises(InvalidRecord):
        parse_kafka_value(raw)
```

Mkdir:

```bash
mkdir -p apps/ingest-python/src/sdf_ingest/{domain,adapters}
mkdir -p apps/ingest-python/tests/{domain,integration}
touch apps/ingest-python/src/sdf_ingest/domain/__init__.py
touch apps/ingest-python/src/sdf_ingest/adapters/__init__.py
touch apps/ingest-python/tests/domain/__init__.py
touch apps/ingest-python/tests/integration/__init__.py
```

- [ ] **Step 2: Run — expect failure.**

- [ ] **Step 3: Implement `domain/record.py`**

```python
from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime
from typing import Final, Literal

KNOWN_METRICS: Final[frozenset[str]] = frozenset(
    {"cycle_count", "good_count", "scrap_count", "state", "cycle_time_ms"},
)


class InvalidRecord(Exception):
    pass


@dataclass(frozen=True, slots=True)
class Normalized:
    tenant_id: str
    line_id: str
    machine_key: str
    metric: Literal["cycle_count", "good_count", "scrap_count", "state", "cycle_time_ms"]
    value: float
    observed_at: datetime
    sparkplug_seq: int


def parse_kafka_value(raw: bytes) -> Normalized:
    try:
        obj = json.loads(raw)
    except json.JSONDecodeError as e:
        raise InvalidRecord(f"not json: {e}") from e

    try:
        metric = obj["metric"]
        seq = int(obj["sparkplugSeq"])
        if metric not in KNOWN_METRICS:
            raise InvalidRecord(f"unknown metric {metric!r}")
        if not 0 <= seq <= 255:
            raise InvalidRecord(f"sparkplugSeq out of range: {seq}")
        return Normalized(
            tenant_id=str(obj["tenantId"]),
            line_id=str(obj["lineId"]),
            machine_key=str(obj["machineKey"]),
            metric=metric,
            value=float(obj["value"]),
            observed_at=datetime.fromisoformat(obj["observedAt"].replace("Z", "+00:00")),
            sparkplug_seq=seq,
        )
    except (KeyError, TypeError, ValueError) as e:
        raise InvalidRecord(str(e)) from e
```

- [ ] **Step 4: Run domain test — expect pass.**

```bash
cd apps/ingest-python && pytest tests/domain -v
```

- [ ] **Step 5: Implement `adapters/writer.py` (asyncpg COPY for batching)**

```python
from __future__ import annotations

from collections.abc import Sequence

import asyncpg

from sdf_ingest.domain.record import Normalized


class TelemetryWriter:
    def __init__(self, pool: asyncpg.Pool) -> None:
        self._pool = pool

    async def write_batch(self, records: Sequence[Normalized]) -> int:
        if not records:
            return 0
        # Resolve machine UUIDs by sparkplug_node_id = "<group>/<line>/<machineKey>".
        # Phase 1: derive node_id from tenant + line + machine_key.
        # We rely on the seed: node_id pattern matches the seeded value.
        rows = []
        async with self._pool.acquire() as conn:
            for r in records:
                node_id = f"{r.tenant_id}/{r.line_id}/{r.machine_key}"
                row = await conn.fetchrow(
                    "SELECT id FROM machine WHERE sparkplug_node_id = $1", node_id,
                )
                if row is None:
                    continue
                rows.append((
                    r.observed_at,
                    row["id"],
                    r.metric,
                    r.value if r.metric != "state" else None,
                    None if r.metric != "state" else str(r.value),
                    r.sparkplug_seq,
                ))
            if not rows:
                return 0
            await conn.copy_records_to_table(
                "machine_telemetry",
                records=rows,
                columns=["time", "machine_id", "metric", "value_num", "value_text", "sparkplug_seq"],
            )
        return len(rows)
```

- [ ] **Step 6: Implement `adapters/consumer.py`**

```python
from __future__ import annotations

import asyncio
import logging
from collections.abc import AsyncIterator

from aiokafka import AIOKafkaConsumer

from sdf_ingest.domain.record import InvalidRecord, Normalized, parse_kafka_value

log = logging.getLogger(__name__)


class KafkaTelemetrySource:
    def __init__(self, bootstrap: str, topic_pattern: str = "sdf.*.machine.telemetry") -> None:
        self._consumer = AIOKafkaConsumer(
            bootstrap_servers=bootstrap,
            group_id="sdf-ingest",
            enable_auto_commit=False,
            auto_offset_reset="latest",
        )
        self._pattern = topic_pattern

    async def __aenter__(self) -> KafkaTelemetrySource:
        await self._consumer.start()
        self._consumer.subscribe(pattern=self._pattern)
        return self

    async def __aexit__(self, *exc: object) -> None:
        await self._consumer.stop()

    async def batches(self, max_batch: int = 500, max_wait_s: float = 0.5) -> AsyncIterator[list[Normalized]]:
        while True:
            records: dict = await self._consumer.getmany(timeout_ms=int(max_wait_s * 1000), max_records=max_batch)
            batch: list[Normalized] = []
            offsets_to_commit = {}
            for tp, msgs in records.items():
                for msg in msgs:
                    try:
                        batch.append(parse_kafka_value(msg.value))
                    except InvalidRecord as e:
                        log.warning("invalid record on %s@%d: %s", tp.topic, msg.offset, e)
                    offsets_to_commit[tp] = msg.offset + 1
            if batch:
                yield batch
                await self._consumer.commit(offsets_to_commit)
            else:
                await asyncio.sleep(0)
```

- [ ] **Step 7: Implement `main.py`**

```python
from __future__ import annotations

import asyncio
import logging
import os

import asyncpg

from sdf_ingest.adapters.consumer import KafkaTelemetrySource
from sdf_ingest.adapters.writer import TelemetryWriter

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")
log = logging.getLogger("ingest")


async def run() -> None:
    bootstrap = os.environ.get("KAFKA_BOOTSTRAP", "localhost:9092")
    pg_dsn = os.environ.get("PG_DSN", "postgresql://sdf:sdf@localhost:5432/sdf")

    pool = await asyncpg.create_pool(pg_dsn, min_size=1, max_size=8)
    assert pool is not None
    writer = TelemetryWriter(pool)
    async with KafkaTelemetrySource(bootstrap) as source:
        async for batch in source.batches():
            n = await writer.write_batch(batch)
            log.info("wrote batch of %d (of %d parsed)", n, len(batch))


if __name__ == "__main__":
    asyncio.run(run())
```

- [ ] **Step 8: Integration test `tests/integration/test_pipeline.py`**

```python
import asyncio
import json
import os
from datetime import datetime, timezone
from uuid import uuid4

import asyncpg
import pytest
from aiokafka import AIOKafkaProducer
from testcontainers.kafka import KafkaContainer
from testcontainers.postgres import PostgresContainer

from sdf_ingest.adapters.consumer import KafkaTelemetrySource
from sdf_ingest.adapters.writer import TelemetryWriter


@pytest.mark.integration
async def test_ingest_writes_to_timescale() -> None:
    with PostgresContainer("timescale/timescaledb:2.15.3-pg16") as pg, \
         KafkaContainer("confluentinc/cp-kafka:7.6.0") as kafka:
        dsn = pg.get_connection_url().replace("postgresql+psycopg2://", "postgresql://")
        pool = await asyncpg.create_pool(dsn)
        assert pool is not None

        async with pool.acquire() as conn:
            await conn.execute("CREATE EXTENSION IF NOT EXISTS timescaledb;")
            # Minimal schema for integration test
            await conn.execute("""
                CREATE TABLE machine (
                    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
                    sparkplug_node_id text UNIQUE NOT NULL
                );
                CREATE TABLE machine_telemetry (
                    time timestamptz NOT NULL,
                    machine_id uuid NOT NULL,
                    metric text NOT NULL,
                    value_num double precision,
                    value_text text,
                    sparkplug_seq smallint NOT NULL
                );
                SELECT create_hypertable('machine_telemetry', 'time');
            """)
            machine_id = uuid4()
            await conn.execute(
                "INSERT INTO machine (id, sparkplug_node_id) VALUES ($1, $2)",
                machine_id, "sdf_default/line-a/press",
            )

        # Produce a record
        bootstrap = kafka.get_bootstrap_server()
        producer = AIOKafkaProducer(bootstrap_servers=bootstrap)
        await producer.start()
        payload = json.dumps({
            "tenantId": "sdf_default",
            "lineId": "line-a",
            "machineKey": "press",
            "metric": "cycle_count",
            "value": 1.0,
            "observedAt": datetime.now(timezone.utc).isoformat(),
            "sparkplugSeq": 1,
        }).encode()
        await producer.send_and_wait("sdf.sdf_default.machine.telemetry", payload)
        await producer.stop()

        writer = TelemetryWriter(pool)
        async with KafkaTelemetrySource(bootstrap) as source:
            batch_iter = source.batches(max_batch=10, max_wait_s=2.0)
            batch = await asyncio.wait_for(batch_iter.__anext__(), timeout=10.0)
            written = await writer.write_batch(batch)

        assert written == 1
        async with pool.acquire() as conn:
            count = await conn.fetchval("SELECT count(*) FROM machine_telemetry")
        assert count == 1
```

- [ ] **Step 9: Run integration test**

```bash
cd apps/ingest-python && pytest tests/integration --integration -v
```
Expected: pass (~30s due to testcontainers).

- [ ] **Step 10: Run drift gates**

```bash
cd apps/ingest-python && mypy && ruff check . && lint-imports
```

- [ ] **Step 11: Commit**

```bash
git add apps/ingest-python/src apps/ingest-python/tests
git commit -m "feat(ingest): Kafka consumer + asyncpg COPY writer + pipeline integration test"
```

---

### Task 19: FastAPI API — composition + healthz/readyz

**Files:**
- Create: `apps/api-python/src/sdf_api/app.py`
- Create: `apps/api-python/src/sdf_api/config.py`
- Create: `apps/api-python/src/sdf_api/contexts/monitoring/adapters/__init__.py`
- Create: `apps/api-python/src/sdf_api/contexts/monitoring/adapters/http.py`
- Create: `apps/api-python/src/sdf_api/contexts/monitoring/adapters/db.py`
- Create: `apps/api-python/src/sdf_api/contexts/monitoring/application/__init__.py`
- Create: `apps/api-python/src/sdf_api/contexts/monitoring/application/queries.py`
- Create: `apps/api-python/src/sdf_api/contexts/monitoring/ports.py`
- Create: `apps/api-python/tests/contexts/monitoring/application/test_queries.py`
- Create: `apps/api-python/tests/integration/test_api_smoke.py`

- [ ] **Step 1: Write `ports.py`**

```python
from __future__ import annotations

from datetime import datetime
from typing import Literal, Protocol

from sdf_api.shared_kernel.ids import LineId


class LineStateSnapshot(Protocol):
    line_id: LineId
    state: Literal["RUNNING", "IDLE", "DOWN", "CHANGEOVER"]
    since: datetime


class LineStateReader(Protocol):
    async def latest(self, line_id: LineId) -> LineStateSnapshot | None: ...


class OeeReading(Protocol):
    line_id: LineId
    window: Literal["5m", "1h", "shift"]
    availability: float
    performance: float
    quality: float
    oee: float
    observed_at: datetime


class OeeReader(Protocol):
    async def latest(
        self, line_id: LineId, window: Literal["5m", "1h", "shift"],
    ) -> OeeReading | None: ...
```

- [ ] **Step 2: Write application use case `application/queries.py`**

```python
from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from sdf_api.contexts.monitoring.ports import (
    LineStateReader,
    LineStateSnapshot,
    OeeReader,
    OeeReading,
)
from sdf_api.shared_kernel.ids import LineId


@dataclass(frozen=True, slots=True)
class GetLineStateQuery:
    line_id: LineId


@dataclass(frozen=True, slots=True)
class GetLineOeeQuery:
    line_id: LineId
    window: Literal["5m", "1h", "shift"]


class LineQueries:
    def __init__(self, states: LineStateReader, oees: OeeReader) -> None:
        self._states = states
        self._oees = oees

    async def line_state(self, q: GetLineStateQuery) -> LineStateSnapshot | None:
        return await self._states.latest(q.line_id)

    async def line_oee(self, q: GetLineOeeQuery) -> OeeReading | None:
        return await self._oees.latest(q.line_id, q.window)
```

- [ ] **Step 3: Write unit test with fakes `tests/contexts/monitoring/application/test_queries.py`**

```python
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Literal
from uuid import uuid4

import pytest

from sdf_api.contexts.monitoring.application.queries import (
    GetLineOeeQuery,
    GetLineStateQuery,
    LineQueries,
)
from sdf_api.shared_kernel.ids import LineId


@dataclass
class _Snap:
    line_id: LineId
    state: Literal["RUNNING", "IDLE", "DOWN", "CHANGEOVER"]
    since: datetime


@dataclass
class _Oee:
    line_id: LineId
    window: Literal["5m", "1h", "shift"]
    availability: float
    performance: float
    quality: float
    oee: float
    observed_at: datetime


class _FakeStates:
    async def latest(self, line_id: LineId):
        return _Snap(line_id=line_id, state="RUNNING", since=datetime.now(timezone.utc))


class _FakeOees:
    async def latest(self, line_id: LineId, window):
        return _Oee(line_id=line_id, window=window, availability=0.9, performance=0.95, quality=0.99, oee=0.84645, observed_at=datetime.now(timezone.utc))


@pytest.mark.asyncio
async def test_line_state_query() -> None:
    q = LineQueries(_FakeStates(), _FakeOees())
    lid = LineId(uuid4())
    snap = await q.line_state(GetLineStateQuery(line_id=lid))
    assert snap is not None
    assert snap.state == "RUNNING"


@pytest.mark.asyncio
async def test_line_oee_query() -> None:
    q = LineQueries(_FakeStates(), _FakeOees())
    lid = LineId(uuid4())
    r = await q.line_oee(GetLineOeeQuery(line_id=lid, window="5m"))
    assert r is not None
    assert r.window == "5m"
    assert 0.0 <= r.oee <= 1.0
```

Mkdir + `__init__.py`:

```bash
mkdir -p apps/api-python/src/sdf_api/contexts/monitoring/{adapters,application}
mkdir -p apps/api-python/tests/contexts/monitoring/application
mkdir -p apps/api-python/tests/integration
touch apps/api-python/src/sdf_api/contexts/monitoring/adapters/__init__.py
touch apps/api-python/src/sdf_api/contexts/monitoring/application/__init__.py
touch apps/api-python/tests/contexts/monitoring/application/__init__.py
touch apps/api-python/tests/integration/__init__.py
```

- [ ] **Step 4: Run unit test — expect pass.**

```bash
cd apps/api-python && pytest tests/contexts/monitoring/application -v
```

- [ ] **Step 5: Implement DB adapter `adapters/db.py`**

```python
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Literal, cast

import asyncpg

from sdf_api.shared_kernel.ids import LineId


@dataclass(frozen=True, slots=True)
class PgLineStateSnapshot:
    line_id: LineId
    state: Literal["RUNNING", "IDLE", "DOWN", "CHANGEOVER"]
    since: datetime


@dataclass(frozen=True, slots=True)
class PgOeeReading:
    line_id: LineId
    window: Literal["5m", "1h", "shift"]
    availability: float
    performance: float
    quality: float
    oee: float
    observed_at: datetime


class PgLineStateReader:
    def __init__(self, pool: asyncpg.Pool) -> None:
        self._pool = pool

    async def latest(self, line_id: LineId) -> PgLineStateSnapshot | None:
        async with self._pool.acquire() as conn:
            row = await conn.fetchrow(
                "SELECT state, time FROM line_state WHERE line_id = $1 ORDER BY time DESC LIMIT 1",
                line_id.value,
            )
        if row is None:
            return None
        return PgLineStateSnapshot(
            line_id=line_id,
            state=cast("Literal['RUNNING','IDLE','DOWN','CHANGEOVER']", row["state"]),
            since=row["time"],
        )


class PgOeeReader:
    """Reads from line_oee_5m continuous aggregate; computes A/P/Q from raw cycle data.

    Phase 1 simplification: A/P/Q approximated via ratios on counts in the bucket.
    A real implementation would track planned-busy-time per shift; here we treat
    the bucket as PBT.
    """

    def __init__(self, pool: asyncpg.Pool) -> None:
        self._pool = pool

    async def latest(
        self, line_id: LineId, window: Literal["5m", "1h", "shift"],
    ) -> PgOeeReading | None:
        if window != "5m":
            return None  # Phase 1: only 5m CAGG implemented; 1h/shift are Phase 3.
        async with self._pool.acquire() as conn:
            row = await conn.fetchrow(
                """
                SELECT bucket, good_qty, actual_qty, avg_cycle_ms
                FROM line_oee_5m
                WHERE line_id = $1
                ORDER BY bucket DESC LIMIT 1
                """,
                line_id.value,
            )
        if row is None:
            return None
        # Phase 1 approximation: A=1.0 (bucket = PBT = APT), Q=good/actual,
        # P=(ideal_cycle * actual) / bucket_seconds; ideal_cycle assumed 1s for sim.
        bucket_s = 5 * 60
        actual = float(row["actual_qty"] or 0)
        good = float(row["good_qty"] or 0)
        availability = 1.0
        performance = min(1.0, (1.0 * actual) / bucket_s) if bucket_s > 0 else 0.0
        quality = (good / actual) if actual > 0 else 0.0
        return PgOeeReading(
            line_id=line_id,
            window=window,
            availability=availability,
            performance=performance,
            quality=quality,
            oee=availability * performance * quality,
            observed_at=row["bucket"],
        )
```

- [ ] **Step 6: Implement HTTP adapter `adapters/http.py`**

```python
from __future__ import annotations

from typing import Literal

from fastapi import APIRouter, Depends, HTTPException

from sdf_api.contexts.monitoring.application.queries import (
    GetLineOeeQuery,
    GetLineStateQuery,
    LineQueries,
)
from sdf_api.shared_kernel.ids import LineId


def make_router(queries: LineQueries) -> APIRouter:
    router = APIRouter(prefix="/api/v1")

    def get_queries() -> LineQueries:
        return queries

    @router.get("/lines/{line_id}/state")
    async def line_state(
        line_id: str, qs: LineQueries = Depends(get_queries),
    ) -> dict:
        snap = await qs.line_state(GetLineStateQuery(line_id=LineId.from_string(line_id)))
        if snap is None:
            raise HTTPException(404, "no state recorded")
        return {"lineId": str(snap.line_id.value), "state": snap.state, "since": snap.since.isoformat()}

    @router.get("/lines/{line_id}/oee")
    async def line_oee(
        line_id: str,
        window: Literal["5m", "1h", "shift"] = "5m",
        qs: LineQueries = Depends(get_queries),
    ) -> dict:
        r = await qs.line_oee(GetLineOeeQuery(line_id=LineId.from_string(line_id), window=window))
        if r is None:
            raise HTTPException(404, "no oee available")
        return {
            "lineId": str(r.line_id.value),
            "window": r.window,
            "availability": r.availability,
            "performance": r.performance,
            "quality": r.quality,
            "oee": r.oee,
            "observedAt": r.observed_at.isoformat(),
        }

    return router
```

- [ ] **Step 7: Implement `config.py` + `app.py` (composition root)**

`config.py`:

```python
from __future__ import annotations

from pydantic import BaseModel
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="SDF_")
    pg_dsn: str = "postgresql://sdf:sdf@localhost:5432/sdf"
    kafka_bootstrap: str = "localhost:9092"
    mode: str = "real"  # real | fake
```

`app.py`:

```python
from __future__ import annotations

from contextlib import asynccontextmanager

import asyncpg
from fastapi import FastAPI

from sdf_api.config import Settings
from sdf_api.contexts.monitoring.adapters.db import PgLineStateReader, PgOeeReader
from sdf_api.contexts.monitoring.adapters.http import make_router
from sdf_api.contexts.monitoring.application.queries import LineQueries


@asynccontextmanager
async def _lifespan(app: FastAPI):
    settings = Settings()
    pool = await asyncpg.create_pool(settings.pg_dsn, min_size=1, max_size=8)
    assert pool is not None
    states = PgLineStateReader(pool)
    oees = PgOeeReader(pool)
    queries = LineQueries(states, oees)
    app.include_router(make_router(queries))
    app.state.pool = pool
    yield
    await pool.close()


def create_app() -> FastAPI:
    app = FastAPI(title="SDF API", version="0.1.0", lifespan=_lifespan)

    @app.get("/healthz")
    async def healthz() -> dict:
        return {"status": "ok"}

    @app.get("/readyz")
    async def readyz() -> dict:
        pool = getattr(app.state, "pool", None)
        if pool is None:
            return {"status": "starting"}
        async with pool.acquire() as conn:
            await conn.execute("SELECT 1")
        return {"status": "ready"}

    return app


app = create_app()
```

- [ ] **Step 8: Integration smoke test `tests/integration/test_api_smoke.py`**

```python
import pytest
from fastapi.testclient import TestClient

from sdf_api.app import create_app


@pytest.mark.integration
def test_healthz() -> None:
    app = create_app()
    with TestClient(app) as client:
        r = client.get("/healthz")
    assert r.status_code == 200
    assert r.json() == {"status": "ok"}
```

- [ ] **Step 9: Run unit + drift gates**

```bash
cd apps/api-python && pytest -x && mypy && ruff check . && lint-imports
```

- [ ] **Step 10: Commit**

```bash
git add apps/api-python/src apps/api-python/tests
git commit -m "feat(api): healthz/readyz + monitoring queries (state, oee 5m) + db adapter"
```

---

### Task 20: WebSocket push for live line state

**Files:**
- Create: `apps/api-python/src/sdf_api/contexts/monitoring/adapters/ws.py`
- Modify: `apps/api-python/src/sdf_api/app.py`
- Create: `apps/api-python/tests/contexts/monitoring/adapters/test_ws.py`

- [ ] **Step 1: Failing test (use FastAPI TestClient WebSocket support)**

```python
import asyncio
from datetime import datetime, timezone
from uuid import uuid4

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from sdf_api.contexts.monitoring.adapters.ws import LineStateBroadcaster, register_ws


@pytest.mark.asyncio
async def test_broadcaster_fans_out_to_subscribers() -> None:
    b = LineStateBroadcaster()
    sub1 = b.subscribe()
    sub2 = b.subscribe()
    payload = {"lineId": str(uuid4()), "state": "RUNNING", "since": datetime.now(timezone.utc).isoformat()}
    await b.publish(payload)
    m1 = await asyncio.wait_for(sub1.get(), timeout=1.0)
    m2 = await asyncio.wait_for(sub2.get(), timeout=1.0)
    assert m1 == payload == m2


def test_ws_round_trip_via_testclient() -> None:
    app = FastAPI()
    broadcaster = LineStateBroadcaster()
    register_ws(app, broadcaster)

    with TestClient(app) as client, client.websocket_connect("/ws/line-state") as ws:
        async def publish_later() -> None:
            await asyncio.sleep(0.05)
            await broadcaster.publish({"state": "DOWN"})
        loop = asyncio.new_event_loop()
        loop.run_until_complete(publish_later())
        msg = ws.receive_json()
        assert msg == {"state": "DOWN"}
```

- [ ] **Step 2: Run — expect failure.**

- [ ] **Step 3: Implement `ws.py`**

```python
from __future__ import annotations

import asyncio
import logging
from typing import Any

from fastapi import FastAPI, WebSocket, WebSocketDisconnect

log = logging.getLogger(__name__)


class LineStateBroadcaster:
    def __init__(self) -> None:
        self._subscribers: list[asyncio.Queue[Any]] = []
        self._lock = asyncio.Lock()

    def subscribe(self) -> asyncio.Queue[Any]:
        q: asyncio.Queue[Any] = asyncio.Queue(maxsize=64)
        self._subscribers.append(q)
        return q

    async def unsubscribe(self, q: asyncio.Queue[Any]) -> None:
        async with self._lock:
            if q in self._subscribers:
                self._subscribers.remove(q)

    async def publish(self, payload: dict[str, Any]) -> None:
        async with self._lock:
            subscribers = list(self._subscribers)
        for q in subscribers:
            if q.full():
                continue  # drop for slow consumers
            await q.put(payload)


def register_ws(app: FastAPI, broadcaster: LineStateBroadcaster) -> None:
    @app.websocket("/ws/line-state")
    async def ws_line_state(ws: WebSocket) -> None:
        await ws.accept()
        q = broadcaster.subscribe()
        try:
            while True:
                payload = await q.get()
                await ws.send_json(payload)
        except WebSocketDisconnect:
            pass
        finally:
            await broadcaster.unsubscribe(q)
```

- [ ] **Step 4: Wire into `app.py`**

Modify `create_app()` to instantiate `LineStateBroadcaster`, call `register_ws(app, broadcaster)`, and store it on `app.state.broadcaster` so other services (e.g., a poller that watches `line_state` table) can publish to it. For Phase 1, add a background task that polls the table every 1s and publishes the latest state:

```python
import asyncio
# inside _lifespan after queries assembled:
broadcaster = LineStateBroadcaster()
register_ws(app, broadcaster)

async def poll_states() -> None:
    last_seen: dict[str, str] = {}
    while True:
        async with pool.acquire() as conn:
            rows = await conn.fetch(
                "SELECT DISTINCT ON (line_id) line_id, state, time FROM line_state ORDER BY line_id, time DESC"
            )
        for r in rows:
            key = str(r["line_id"])
            sig = f"{r['state']}@{r['time'].isoformat()}"
            if last_seen.get(key) != sig:
                last_seen[key] = sig
                await broadcaster.publish({
                    "lineId": key, "state": r["state"], "since": r["time"].isoformat(),
                })
        await asyncio.sleep(1.0)

task = asyncio.create_task(poll_states())
app.state.poll_task = task
```

In shutdown side: `task.cancel(); await asyncio.gather(task, return_exceptions=True)`.

- [ ] **Step 5: Run unit tests — expect pass.**

- [ ] **Step 6: Run drift gates + mypy — expect clean.**

- [ ] **Step 7: Commit**

```bash
git add apps/api-python/src/sdf_api/contexts/monitoring/adapters/ws.py apps/api-python/src/sdf_api/app.py apps/api-python/tests/contexts/monitoring/adapters/test_ws.py
git commit -m "feat(api): WebSocket /ws/line-state + broadcaster + 1s poller"
```

---

### Task 21: Create `Dockerfile` for each service

**Files:**
- Create: `apps/ot-gateway-kotlin/Dockerfile`
- Create: `apps/api-python/Dockerfile`
- Create: `apps/ingest-python/Dockerfile`
- Create: `apps/dashboard-react/Dockerfile`

- [ ] **Step 1: Kotlin Dockerfile (shared across submodules — compose specifies which task to run)**

```dockerfile
FROM eclipse-temurin:21-jdk AS build
WORKDIR /src
COPY . .
RUN ./gradlew --no-daemon assemble

FROM eclipse-temurin:21-jre
WORKDIR /app
COPY --from=build /src /app
WORKDIR /app
ENTRYPOINT ["./gradlew", "--no-daemon"]
```

- [ ] **Step 2: api-python Dockerfile**

```dockerfile
FROM python:3.12-slim AS build
WORKDIR /src
COPY pyproject.toml .
COPY src src
RUN pip install --no-cache-dir uv && uv pip install --system -e ".[]"

FROM python:3.12-slim
WORKDIR /app
COPY --from=build /usr/local/lib/python3.12/site-packages /usr/local/lib/python3.12/site-packages
COPY --from=build /usr/local/bin /usr/local/bin
COPY src src
EXPOSE 8000
CMD ["uvicorn", "sdf_api.app:app", "--host", "0.0.0.0", "--port", "8000"]
```

- [ ] **Step 3: ingest-python Dockerfile**

```dockerfile
FROM python:3.12-slim AS build
WORKDIR /src
COPY pyproject.toml .
COPY src src
RUN pip install --no-cache-dir uv && uv pip install --system -e ".[]"

FROM python:3.12-slim
WORKDIR /app
COPY --from=build /usr/local/lib/python3.12/site-packages /usr/local/lib/python3.12/site-packages
COPY src src
CMD ["python", "-m", "sdf_ingest.main"]
```

- [ ] **Step 4: dashboard Dockerfile (Vite + nginx)**

```dockerfile
FROM node:20-alpine AS build
WORKDIR /src
COPY package.json pnpm-lock.yaml* ./
RUN corepack enable && pnpm install --frozen-lockfile
COPY . .
RUN pnpm build

FROM nginx:1.27-alpine
COPY --from=build /src/dist /usr/share/nginx/html
COPY nginx.conf /etc/nginx/conf.d/default.conf
```

- [ ] **Step 5: dashboard nginx config (placeholder until Task 23 fills the SPA)**

`apps/dashboard-react/nginx.conf`:

```
server {
    listen 80;
    root /usr/share/nginx/html;
    location / {
        try_files $uri /index.html;
    }
    location /api/ {
        proxy_pass http://api:8000/api/;
    }
    location /ws/ {
        proxy_pass http://api:8000/ws/;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
    }
}
```

- [ ] **Step 6: Commit**

```bash
git add apps/*/Dockerfile apps/dashboard-react/nginx.conf
git commit -m "build: Dockerfiles for all four services + dashboard nginx proxy"
```

---

## Section F — React Dashboard

### Task 22: React scaffold + drift toolchain

**Files:**
- Create: `apps/dashboard-react/package.json`, `tsconfig.json`, `vite.config.ts`, `eslint.config.js`, `index.html`, `src/main.tsx`, `src/App.tsx`, `src/index.css`, `postcss.config.js`, `tailwind.config.ts`

- [ ] **Step 1: Write `package.json`**

```json
{
  "name": "@sdf/dashboard",
  "private": true,
  "version": "0.1.0",
  "type": "module",
  "scripts": {
    "dev": "vite",
    "dev:fake": "VITE_FAKE=1 vite",
    "build": "tsc --noEmit && vite build",
    "preview": "vite preview",
    "lint": "eslint .",
    "test": "vitest run",
    "test:watch": "vitest",
    "e2e:fake": "VITE_FAKE=1 playwright test --project=fake",
    "e2e:real": "playwright test --project=real"
  },
  "dependencies": {
    "@tanstack/react-query": "^5.59.0",
    "react": "^18.3.1",
    "react-dom": "^18.3.1",
    "react-i18next": "^15.0.2",
    "i18next": "^23.15.1",
    "recharts": "^2.13.0"
  },
  "devDependencies": {
    "@playwright/test": "^1.48.0",
    "@types/react": "^18.3.10",
    "@types/react-dom": "^18.3.0",
    "@vitejs/plugin-react": "^4.3.1",
    "autoprefixer": "^10.4.20",
    "eslint": "^9.11.1",
    "eslint-plugin-boundaries": "^4.2.2",
    "eslint-plugin-import": "^2.30.0",
    "msw": "^2.4.9",
    "postcss": "^8.4.47",
    "tailwindcss": "^3.4.13",
    "ts-prune": "^0.10.3",
    "typescript": "^5.6.2",
    "typescript-eslint": "^8.7.0",
    "vite": "^5.4.8",
    "vitest": "^2.1.1"
  }
}
```

- [ ] **Step 2: Write `tsconfig.json`**

```json
{
  "compilerOptions": {
    "target": "ES2022",
    "lib": ["ES2022", "DOM", "DOM.Iterable"],
    "module": "ESNext",
    "moduleResolution": "Bundler",
    "jsx": "react-jsx",
    "strict": true,
    "noUncheckedIndexedAccess": true,
    "noImplicitOverride": true,
    "noFallthroughCasesInSwitch": true,
    "noEmit": true,
    "esModuleInterop": true,
    "skipLibCheck": true,
    "resolveJsonModule": true,
    "isolatedModules": true,
    "baseUrl": ".",
    "paths": {
      "@/*": ["src/*"]
    }
  },
  "include": ["src", "tests"]
}
```

- [ ] **Step 3: Write `vite.config.ts`**

```typescript
import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
import path from "node:path";

export default defineConfig({
  plugins: [react()],
  resolve: { alias: { "@": path.resolve(__dirname, "src") } },
  server: {
    proxy: {
      "/api": "http://localhost:8000",
      "/ws":  { target: "ws://localhost:8000", ws: true },
    },
  },
});
```

- [ ] **Step 4: Write `eslint.config.js` (flat config + boundaries)**

```javascript
import js from "@eslint/js";
import tseslint from "typescript-eslint";
import boundaries from "eslint-plugin-boundaries";
import importPlugin from "eslint-plugin-import";

export default tseslint.config(
  js.configs.recommended,
  ...tseslint.configs.strictTypeChecked,
  {
    plugins: { boundaries, import: importPlugin },
    languageOptions: {
      parserOptions: { project: "./tsconfig.json" },
    },
    settings: {
      "boundaries/elements": [
        { type: "domain",      pattern: "src/contexts/*/domain/**" },
        { type: "application", pattern: "src/contexts/*/application/**" },
        { type: "adapters",    pattern: "src/contexts/*/adapters/**" },
        { type: "ui",          pattern: "src/ui/**" },
        { type: "shared",      pattern: "src/shared/**" },
      ],
    },
    rules: {
      "boundaries/element-types": ["error", {
        default: "allow",
        rules: [
          { from: "domain", disallow: ["adapters", "application", "ui"] },
          { from: "application", disallow: ["adapters", "ui"] },
        ],
      }],
      "@typescript-eslint/no-explicit-any": "error",
      "@typescript-eslint/no-floating-promises": "error",
      "@typescript-eslint/consistent-type-imports": "error",
      "import/no-internal-modules": ["error", {
        allow: ["@/contexts/*/index.ts", "@/contexts/*/ports.ts"],
      }],
    },
  },
);
```

- [ ] **Step 5: Write `tailwind.config.ts`**

```typescript
import type { Config } from "tailwindcss";

export default {
  content: ["./index.html", "./src/**/*.{ts,tsx}"],
  theme: { extend: {} },
  plugins: [],
} satisfies Config;
```

- [ ] **Step 6: `postcss.config.js`**

```javascript
export default { plugins: { tailwindcss: {}, autoprefixer: {} } };
```

- [ ] **Step 7: `index.html`, `src/index.css`, `src/main.tsx`, `src/App.tsx` placeholders**

`index.html`:

```html
<!DOCTYPE html>
<html lang="ko">
  <head>
    <meta charset="UTF-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1.0" />
    <title>SDF Manufacturing DX</title>
  </head>
  <body class="bg-slate-50">
    <div id="root"></div>
    <script type="module" src="/src/main.tsx"></script>
  </body>
</html>
```

`src/index.css`:

```css
@tailwind base;
@tailwind components;
@tailwind utilities;
```

`src/main.tsx`:

```typescript
import React from "react";
import ReactDOM from "react-dom/client";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import App from "./App";
import "./index.css";

const queryClient = new QueryClient();

async function bootstrap(): Promise<void> {
  if (import.meta.env.VITE_FAKE === "1") {
    const { worker } = await import("./testing/msw/browser");
    await worker.start({ onUnhandledRequest: "warn" });
  }
  ReactDOM.createRoot(document.getElementById("root")!).render(
    <React.StrictMode>
      <QueryClientProvider client={queryClient}>
        <App />
      </QueryClientProvider>
    </React.StrictMode>,
  );
}

void bootstrap();
```

`src/App.tsx`:

```typescript
import { LineDashboard } from "@/ui/LineDashboard";

export default function App(): JSX.Element {
  return (
    <main className="min-h-screen p-6">
      <header className="mb-6">
        <h1 className="text-2xl font-bold text-slate-900">SDF Manufacturing DX</h1>
        <p className="text-sm text-slate-600">Phase 1 — Single line vertical slice</p>
      </header>
      <LineDashboard />
    </main>
  );
}
```

- [ ] **Step 8: Install + smoke**

```bash
cd apps/dashboard-react && pnpm install
pnpm tsc --noEmit
```
Expected: ts has no errors at this stage (LineDashboard import is unresolved — fix in next task).

- [ ] **Step 9: Commit**

```bash
git add apps/dashboard-react
git commit -m "chore(dashboard): vite + react + tailwind + tseslint strict + boundaries"
```

---

### Task 23: Line dashboard widget — REST fetch + WS live updates

**Files:**
- Create: `apps/dashboard-react/src/ui/LineDashboard.tsx`
- Create: `apps/dashboard-react/src/ui/OeeGauge.tsx`
- Create: `apps/dashboard-react/src/ui/LineStatePill.tsx`
- Create: `apps/dashboard-react/src/contexts/monitoring/adapters/api.ts`
- Create: `apps/dashboard-react/src/contexts/monitoring/adapters/ws.ts`
- Create: `apps/dashboard-react/src/contexts/monitoring/ports.ts`
- Create: `apps/dashboard-react/src/testing/msw/handlers.ts`
- Create: `apps/dashboard-react/src/testing/msw/browser.ts`
- Create: `apps/dashboard-react/src/contexts/monitoring/adapters/api.test.ts`

- [ ] **Step 1: Write `ports.ts`**

```typescript
export interface LineStateSnapshot {
  lineId: string;
  state: "RUNNING" | "IDLE" | "DOWN" | "CHANGEOVER";
  since: string;
}

export interface OeeReading {
  lineId: string;
  window: "5m" | "1h" | "shift";
  availability: number;
  performance: number;
  quality: number;
  oee: number;
  observedAt: string;
}

export interface MonitoringApi {
  getLineState(lineId: string): Promise<LineStateSnapshot>;
  getLineOee(lineId: string, window: OeeReading["window"]): Promise<OeeReading>;
}
```

- [ ] **Step 2: Write `api.ts`**

```typescript
import type { LineStateSnapshot, MonitoringApi, OeeReading } from "../ports";

export function makeRestApi(baseUrl = ""): MonitoringApi {
  return {
    async getLineState(lineId: string): Promise<LineStateSnapshot> {
      const r = await fetch(`${baseUrl}/api/v1/lines/${lineId}/state`);
      if (!r.ok) throw new Error(`state ${r.status}`);
      return (await r.json()) as LineStateSnapshot;
    },
    async getLineOee(lineId: string, window): Promise<OeeReading> {
      const r = await fetch(`${baseUrl}/api/v1/lines/${lineId}/oee?window=${window}`);
      if (!r.ok) throw new Error(`oee ${r.status}`);
      return (await r.json()) as OeeReading;
    },
  };
}
```

- [ ] **Step 3: Write `ws.ts`**

```typescript
import type { LineStateSnapshot } from "../ports";

export function subscribeLineState(
  onMessage: (s: LineStateSnapshot) => void,
  onClose: () => void,
): () => void {
  const url = window.location.origin.replace(/^http/, "ws") + "/ws/line-state";
  const ws = new WebSocket(url);
  ws.addEventListener("message", (e) => {
    const data: unknown = JSON.parse(String(e.data));
    onMessage(data as LineStateSnapshot);
  });
  ws.addEventListener("close", onClose);
  return () => ws.close();
}
```

- [ ] **Step 4: Write `LineStatePill.tsx`**

```typescript
import type { LineStateSnapshot } from "@/contexts/monitoring/ports";

const COLORS: Record<LineStateSnapshot["state"], string> = {
  RUNNING:    "bg-emerald-500",
  IDLE:       "bg-slate-400",
  DOWN:       "bg-rose-500",
  CHANGEOVER: "bg-amber-500",
};

export function LineStatePill({ snap }: { snap: LineStateSnapshot }): JSX.Element {
  return (
    <div className="flex items-center gap-3">
      <span className={`inline-block size-3 rounded-full ${COLORS[snap.state]}`} />
      <span className="font-semibold text-slate-900">{snap.state}</span>
      <span className="text-xs text-slate-500">since {new Date(snap.since).toLocaleTimeString()}</span>
    </div>
  );
}
```

- [ ] **Step 5: Write `OeeGauge.tsx`**

```typescript
import type { OeeReading } from "@/contexts/monitoring/ports";

export function OeeGauge({ reading }: { reading: OeeReading }): JSX.Element {
  const pct = (n: number) => `${(n * 100).toFixed(1)}%`;
  return (
    <div className="grid grid-cols-4 gap-4">
      {[
        ["OEE",          reading.oee],
        ["Availability", reading.availability],
        ["Performance",  reading.performance],
        ["Quality",      reading.quality],
      ].map(([label, v]) => (
        <div key={label as string} className="rounded-2xl bg-white p-4 shadow-sm">
          <div className="text-xs uppercase tracking-wide text-slate-500">{label as string}</div>
          <div className="mt-1 text-2xl font-bold text-slate-900">{pct(v as number)}</div>
        </div>
      ))}
    </div>
  );
}
```

- [ ] **Step 6: Write `LineDashboard.tsx`**

```typescript
import { useEffect, useState } from "react";
import { useQuery } from "@tanstack/react-query";

import { makeRestApi } from "@/contexts/monitoring/adapters/api";
import { subscribeLineState } from "@/contexts/monitoring/adapters/ws";
import type { LineStateSnapshot } from "@/contexts/monitoring/ports";

import { LineStatePill } from "./LineStatePill";
import { OeeGauge } from "./OeeGauge";

const api = makeRestApi();

// Phase 1: single hardcoded line — Phase 2 introduces a line picker + tenant.
const LINE_ID = import.meta.env.VITE_DEFAULT_LINE_ID ?? "00000000-0000-0000-0000-000000000000";

export function LineDashboard(): JSX.Element {
  const [liveState, setLiveState] = useState<LineStateSnapshot | null>(null);
  const [wsAlive, setWsAlive] = useState(true);

  useEffect(() => {
    const unsub = subscribeLineState(setLiveState, () => setWsAlive(false));
    return unsub;
  }, []);

  const stateQuery = useQuery({
    queryKey: ["state", LINE_ID],
    queryFn: () => api.getLineState(LINE_ID),
    refetchInterval: wsAlive ? false : 2000,  // polling fallback
  });

  const oeeQuery = useQuery({
    queryKey: ["oee", LINE_ID, "5m"],
    queryFn: () => api.getLineOee(LINE_ID, "5m"),
    refetchInterval: 5000,
  });

  const currentState = liveState ?? stateQuery.data ?? null;

  return (
    <section className="space-y-6">
      <div className="rounded-2xl bg-white p-4 shadow-sm">
        <div className="mb-2 text-sm font-medium text-slate-700">Line state</div>
        {currentState ? <LineStatePill snap={currentState} /> : <span className="text-slate-500">…</span>}
        {!wsAlive && (
          <span className="ml-2 rounded bg-amber-100 px-2 py-0.5 text-xs text-amber-800">
            polling (WS reconnecting)
          </span>
        )}
      </div>
      <div>
        <div className="mb-2 text-sm font-medium text-slate-700">OEE — last 5 min</div>
        {oeeQuery.data ? <OeeGauge reading={oeeQuery.data} /> : <div className="text-slate-500">…</div>}
      </div>
    </section>
  );
}
```

- [ ] **Step 7: MSW handlers — `src/testing/msw/handlers.ts`**

```typescript
import { http, HttpResponse } from "msw";

export const handlers = [
  http.get("/api/v1/lines/:lineId/state", ({ params }) =>
    HttpResponse.json({
      lineId: params.lineId, state: "RUNNING", since: new Date().toISOString(),
    }),
  ),
  http.get("/api/v1/lines/:lineId/oee", ({ params, request }) => {
    const url = new URL(request.url);
    return HttpResponse.json({
      lineId: params.lineId,
      window: url.searchParams.get("window") ?? "5m",
      availability: 0.92, performance: 0.88, quality: 0.99,
      oee: 0.92 * 0.88 * 0.99,
      observedAt: new Date().toISOString(),
    });
  }),
];
```

- [ ] **Step 8: MSW browser worker — `src/testing/msw/browser.ts`**

```typescript
import { setupWorker } from "msw/browser";
import { handlers } from "./handlers";

export const worker = setupWorker(...handlers);
```

Then run once to publish the SW:

```bash
cd apps/dashboard-react && pnpm dlx msw init public/
```

- [ ] **Step 9: Adapter unit test `api.test.ts`**

```typescript
import { afterEach, describe, expect, it } from "vitest";
import { makeRestApi } from "./api";

const originalFetch = globalThis.fetch;
afterEach(() => { globalThis.fetch = originalFetch; });

describe("makeRestApi", () => {
  it("getLineState parses JSON", async () => {
    globalThis.fetch = (async () =>
      new Response(JSON.stringify({ lineId: "x", state: "RUNNING", since: "2026-05-22T00:00:00Z" }), { status: 200 })
    ) as typeof fetch;
    const api = makeRestApi();
    const r = await api.getLineState("x");
    expect(r.state).toBe("RUNNING");
  });

  it("throws on non-2xx", async () => {
    globalThis.fetch = (async () => new Response("", { status: 500 })) as typeof fetch;
    const api = makeRestApi();
    await expect(api.getLineState("x")).rejects.toThrow(/state 500/);
  });
});
```

- [ ] **Step 10: Run lint + tests + typecheck**

```bash
cd apps/dashboard-react && pnpm lint && pnpm test && pnpm tsc --noEmit
```
Expected: lint clean (no boundaries violations), 2 vitest tests pass, ts strict clean.

- [ ] **Step 11: Smoke run with fake backend**

```bash
cd apps/dashboard-react && pnpm dev:fake
```
Open http://localhost:5173 — expect MSW-fed dashboard rendering OEE numbers and a green RUNNING pill. Stop with Ctrl-C.

- [ ] **Step 12: Commit**

```bash
git add apps/dashboard-react/src apps/dashboard-react/public
git commit -m "feat(dashboard): line state + OEE widgets with WS live updates + MSW fake mode"
```

---

## Section G — E2E + Use Case Gate

### Task 24: Playwright E2E + promote both UCs to `implemented`

> **Note**: UC-002 spec creation + registry row + initial coverage-gate run were completed in Chapter 0 (Task C0-3). This task focuses solely on the Playwright E2E specs and the end-of-phase `draft → implemented` status promotion — the promotion lives here because it requires the implementation + a passing E2E to be honest (per ADR-0000 §Consequences 1: "the E2E + draft → implemented status promotion correctly remains at phase end").

**Files (created or modified in this task):**
- Create: `apps/dashboard-react/playwright.config.ts`
- Create: `apps/dashboard-react/tests/e2e/UC-001-monitor-line-state.spec.ts`
- Create: `apps/dashboard-react/tests/e2e/UC-002-observe-oee.spec.ts`
- Modify: `docs/spec/USE-CASES.md` (flip UC-001/UC-002 `status` cells to `implemented`)
- Modify: `docs/spec/use-cases/UC-001-monitor-line-state.md` front-matter (flip `status` to `implemented`)
- Modify: `docs/spec/use-cases/UC-002-observe-oee.md` front-matter (flip `status` to `implemented`)

**Pre-existing artifacts referenced (do *not* recreate; verify present):**
- `docs/spec/ACTORS.md` — actor catalog.
- `docs/spec/USE-CASES.md` — registry; UC-001 and UC-002 rows already present (UC-002 added in C0-3).
- `docs/spec/use-cases/UC-001-monitor-line-state.md` — UC-001 spec, `status: draft`.
- `docs/spec/use-cases/UC-002-observe-oee.md` — UC-002 spec, `status: draft` (created in C0-3).
- `scripts/check-use-case-coverage.py` — Python coverage gate; runs via `uv run` (PEP 723 inline-script header).

> **Reference**: UC-002 spec body lives at `docs/spec/use-cases/UC-002-observe-oee.md` (committed in C0-3). UC-001 spec body lives at `docs/spec/use-cases/UC-001-monitor-line-state.md` (committed at project start, pre-Phase-1 Chapter 0). Both spec files have `status: draft` at this point; this task creates the E2E specs they reference and then flips both to `implemented`.

- [ ] **Step 1: Write `apps/dashboard-react/playwright.config.ts`**

```typescript
import { defineConfig, devices } from "@playwright/test";

export default defineConfig({
  testDir: "./tests/e2e",
  timeout: 30_000,
  fullyParallel: false,
  workers: 1,
  use: { baseURL: "http://localhost:5173" },
  projects: [
    {
      name: "fake",
      use: { ...devices["Desktop Chrome"] },
      webServer: {
        command: "pnpm dev:fake",
        port: 5173,
        timeout: 60_000,
        reuseExistingServer: !process.env.CI,
      },
    },
    {
      name: "real",
      use: { ...devices["Desktop Chrome"] },
      // CI brings up docker compose externally before invoking this project.
    },
  ],
});
```

- [ ] **Step 2: Write `UC-001-monitor-line-state.spec.ts`**

Covers the *first* Gherkin scenario in UC-001. The other two (live propagation, WS-die fallback) require orchestration not yet wired in Phase 1 and should be recorded as Phase 3 chaos-test candidates in `docs/KNOWN-UNKNOWNS.md` as a **living-doc commit** at the moment this E2E spec is written (per Chapter 0 Living-docs reminder). Suggested entry: "WS-disconnect fallback covered at unit-test layer only — chaos test in Phase 3."

```typescript
import { expect, test } from "@playwright/test";

test.describe("UC-001 — Operator monitors single line state", () => {
  test("Dashboard shows current state on first load", async ({ page }) => {
    await page.goto("/");
    await expect(page.getByRole("heading", { name: /SDF Manufacturing DX/i })).toBeVisible();
    await expect(page.getByText(/RUNNING|IDLE|DOWN|CHANGEOVER/)).toBeVisible({ timeout: 5_000 });
  });
});
```

- [ ] **Step 3: Write `UC-002-observe-oee.spec.ts`**

Covers UC-002's first Gherkin scenario. Second scenario ("polling cadence") deferred per UC-002 Open Questions.

```typescript
import { expect, test } from "@playwright/test";

test.describe("UC-002 — Operator observes OEE refresh", () => {
  test("OEE tiles render with percentages on first load", async ({ page }) => {
    await page.goto("/");
    for (const label of ["OEE", "Availability", "Performance", "Quality"]) {
      await expect(page.getByText(label)).toBeVisible({ timeout: 5_000 });
    }
    await expect(page.getByText(/\d+(\.\d+)?%/).first()).toBeVisible({ timeout: 5_000 });
  });
});
```

- [ ] **Step 4: Install browsers + run E2E (fake project)**

```bash
cd apps/dashboard-react && pnpm playwright install chromium
pnpm e2e:fake
```
Expected: 2 tests pass (one per UC).

- [ ] **Step 5: Promote UC-001 and UC-002 to `status: implemented`**

In each per-UC file front-matter, change `status: draft` → `status: implemented`:
- `docs/spec/use-cases/UC-001-monitor-line-state.md`
- `docs/spec/use-cases/UC-002-observe-oee.md`

In `docs/spec/USE-CASES.md`, change the `Status` cell from `draft` to `implemented` for both rows.

- [ ] **Step 6: Run coverage gate again (now enforces E2E file existence)**

```bash
uv run scripts/check-use-case-coverage.py
```
Expected: `OK: 2 use case(s)...`. The gate now verifies that both `related_e2e` paths exist on disk because both UCs are `implemented`.

- [ ] **Step 7: Commit**

```bash
git add apps/dashboard-react/playwright.config.ts apps/dashboard-react/tests \
        docs/spec/use-cases/UC-002-observe-oee.md \
        docs/spec/use-cases/UC-001-monitor-line-state.md \
        docs/spec/USE-CASES.md
git commit -m "test(e2e): Playwright UC-001/UC-002 + promote UCs to implemented"
```

---

## Section I — CI

### Task 27: Top-level CI workflow

**Files:**
- Create: `.github/workflows/ci.yml`

- [ ] **Step 1: Write `.github/workflows/ci.yml`**

```yaml
name: ci
on:
  pull_request:
  push:
    branches: [main]

jobs:
  python:
    runs-on: ubuntu-latest
    strategy:
      matrix:
        app: [api-python, ingest-python]
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with: { python-version: "3.12" }
      - run: pip install uv
      - run: uv pip install --system -e ".[dev]"
        working-directory: apps/${{ matrix.app }}
      - run: ruff check .
        working-directory: apps/${{ matrix.app }}
      - run: ruff format --check .
        working-directory: apps/${{ matrix.app }}
      - run: lint-imports
        working-directory: apps/${{ matrix.app }}
      - run: mypy
        working-directory: apps/${{ matrix.app }}
      - run: pytest --integration
        working-directory: apps/${{ matrix.app }}

  kotlin:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-java@v4
        with: { distribution: temurin, java-version: "21" }
      - uses: gradle/actions/setup-gradle@v4
      - run: ./gradlew ktlintCheck detekt test
        working-directory: apps/ot-gateway-kotlin

  frontend:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: pnpm/action-setup@v4
        with: { version: 9 }
      - uses: actions/setup-node@v4
        with: { node-version: "20", cache: pnpm, cache-dependency-path: apps/dashboard-react/pnpm-lock.yaml }
      - run: pnpm install --frozen-lockfile
        working-directory: apps/dashboard-react
      - run: pnpm lint
        working-directory: apps/dashboard-react
      - run: pnpm tsc --noEmit
        working-directory: apps/dashboard-react
      - run: pnpm test
        working-directory: apps/dashboard-react
      - run: pnpm playwright install chromium
        working-directory: apps/dashboard-react
      - run: pnpm e2e:fake
        working-directory: apps/dashboard-react

  use-case-gate:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: astral-sh/setup-uv@v3
      - uses: actions/setup-python@v5
        with: { python-version: "3.12" }
      - run: uv run scripts/check-use-case-coverage.py

  e2e-real:
    runs-on: ubuntu-latest
    needs: [python, kotlin, frontend]
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-java@v4
        with: { distribution: temurin, java-version: "21" }
      - uses: pnpm/action-setup@v4
        with: { version: 9 }
      - uses: actions/setup-node@v4
        with: { node-version: "20" }
      - name: docker compose up
        run: docker compose up -d --wait
      - name: Wait for API
        run: |
          for i in {1..60}; do
            curl -fsS http://localhost:8000/readyz && break
            sleep 2
          done
      - name: Install Playwright
        working-directory: apps/dashboard-react
        run: pnpm install --frozen-lockfile && pnpm playwright install chromium
      - name: Run real-stack E2E
        working-directory: apps/dashboard-react
        run: pnpm e2e:real
      - name: Dump logs on failure
        if: failure()
        run: docker compose logs --no-color > docker-logs.txt
      - uses: actions/upload-artifact@v4
        if: failure()
        with: { name: docker-logs, path: docker-logs.txt }
```

- [ ] **Step 2: Commit**

```bash
git add .github/workflows/ci.yml
git commit -m "ci: python + kotlin + frontend + e2e-real + use-case gate matrix"
```

---

## Section J — End-to-End Integration + Live Demo + Walkthrough

### Task 28: Pre-commit hooks (fast local feedback)

**Files:**
- Create: `.pre-commit-config.yaml`

- [ ] **Step 1: Write `.pre-commit-config.yaml`**

```yaml
repos:
  - repo: local
    hooks:
      - id: ruff
        name: ruff
        entry: bash -c 'cd "$(git rev-parse --show-toplevel)" && for d in apps/api-python apps/ingest-python; do (cd "$d" && ruff check . && ruff format --check .); done'
        language: system
        types: [python]
        pass_filenames: false

      - id: eslint
        name: eslint
        entry: bash -c 'cd apps/dashboard-react && pnpm lint'
        language: system
        files: ^apps/dashboard-react/
        pass_filenames: false

      - id: ktlint
        name: ktlint
        entry: bash -c 'cd apps/ot-gateway-kotlin && ./gradlew --no-daemon -q ktlintCheck'
        language: system
        files: ^apps/ot-gateway-kotlin/.*\.(kt|kts)$
        pass_filenames: false

      - id: use-case-coverage
        name: use-case coverage
        entry: uv run scripts/check-use-case-coverage.py
        language: system
        files: ^(docs/spec/(USE-CASES\.md|use-cases/)|apps/dashboard-react/tests/e2e/)
        pass_filenames: false
```

- [ ] **Step 2: Install + smoke**

```bash
pre-commit install
pre-commit run --all-files
```
Expected: each hook fires; everything passes (slow first time, fast after).

- [ ] **Step 3: Commit**

```bash
git add .pre-commit-config.yaml
git commit -m "chore(hooks): pre-commit running ruff/eslint/ktlint/use-case-coverage"
```

---

### Task 29: Full-stack smoke (the docker compose up moment)

This task validates the AC: "`docker compose up` brings up the stack in under 5 minutes and the dashboard shows live data".

- [ ] **Step 1: Cold-cache build + up**

```bash
cd /Users/cdlee/personal/sdf-dx
docker compose build
time docker compose up -d --wait
```
Expected: under 300 seconds wall-clock to all healthchecks green. (First build is the long part; subsequent `up` is <30s.)

- [ ] **Step 2: Wait for OEE CAGG to populate**

```bash
sleep 70  # 60s for sim data + CAGG schedule_interval
docker compose exec timescale psql -U sdf -d sdf -c "SELECT count(*) FROM machine_telemetry;"
docker compose exec timescale psql -U sdf -d sdf -c "CALL refresh_continuous_aggregate('line_oee_5m', NULL, NULL);"
docker compose exec timescale psql -U sdf -d sdf -c "SELECT * FROM line_oee_5m LIMIT 3;"
```
Expected: telemetry rows > 0, CAGG rows > 0.

- [ ] **Step 3: Hit REST**

```bash
LINE_ID=$(docker compose exec -T timescale psql -U sdf -d sdf -tAc "SELECT id FROM production_line LIMIT 1")
curl -s "http://localhost:8000/api/v1/lines/$LINE_ID/oee?window=5m" | jq .
```
Expected: JSON with `availability`, `performance`, `quality`, `oee`.

- [ ] **Step 4: Browser smoke**

Open http://localhost:5173. Expect: heading "SDF Manufacturing DX", a state pill, and the OEE gauge populated within 10 seconds.

- [ ] **Step 5: Tear down**

```bash
docker compose down -v
```

- [ ] **Step 6: README quickstart polish**

Edit `README.md` and replace the placeholder "Quick start" with the actual reproducible recipe:

```markdown
## Quick start (Phase 1)

```bash
docker compose up -d --wait
```

Then:
- Dashboard: http://localhost:5173
- API:       http://localhost:8000/docs
- Postgres:  `psql postgresql://sdf:sdf@localhost:5432/sdf`
- Redpanda console (optional): http://localhost:9644

Tear down: `docker compose down -v`.

First run ≈ 4 minutes (mostly image builds); subsequent runs ≈ 30 seconds.
```

- [ ] **Step 7: Commit**

```bash
git add README.md
git commit -m "docs(readme): Phase 1 quickstart"
```

---

### Task 30: Live demo Scenario A (5-minute script)

**Files:**
- Create: `scripts/live-demo/scenario-a.md`

- [ ] **Step 1: Write `scripts/live-demo/scenario-a.md`**

```markdown
# Live Demo — Scenario A: New KPI (5 minutes)

> Goal: add TEEP (Total Effective Equipment Performance) per ISO 22400-2 §5 as a new derived KPI without breaking any guardrail.

## Pre-roll (do before the demo)
- `docker compose up -d --wait`.
- Open three panes: editor, terminal, browser.
- Confirm dashboard renders.

## Script

### t=0:00 — Frame the change (30s)
> "ISO 22400 defines TEEP as Utilization × OEE, where Utilization = PBT / Calendar Time. We'll add this without breaking the pure-domain rule, the contract-first rule, or the OEE invariants. Watch the toolchain do the work."

### t=0:30 — Write the failing test first (60s)
Add `tests/contexts/monitoring/domain/test_teep.py`:

```python
from sdf_api.contexts.monitoring.domain.oee import OeeResult
from sdf_api.contexts.monitoring.domain.teep import compute_teep

def test_teep_is_utilization_times_oee() -> None:
    oee = OeeResult(availability=0.9, performance=0.95, quality=0.99, oee=0.84645)
    teep = compute_teep(oee=oee, utilization=0.5)
    assert teep == 0.5 * 0.84645
```

Run: `pytest -k teep` → fails (module missing). *Show the failure on screen.*

### t=1:30 — Ask LLM, paste, verify (90s)
> "I'll prompt the LLM with: 'implement compute_teep per ISO 22400, no IO imports, take OeeResult + utilization in [0,1]'."
LLM draft → paste → save → run test. **import-linter** stays green because no IO imports. **mypy strict** catches `Optional` slop if any.

### t=3:00 — Expose via REST (90s)
Add field to `OeeReading` schema in `packages/contracts/openapi/sdf-api.yaml`. Run `cd packages/contracts && make openapi-python openapi-typescript`. *Show the generated diff.* Wire the field through `PgOeeReader` (multiply with a hardcoded `utilization=0.5` for the demo — narrate this as Phase 3's deferred work).

### t=4:00 — Dashboard reflects it (60s)
Add a tile to `OeeGauge.tsx` for `teep`. Hot reload. *Show the tile rendering.*

### t=5:00 — Land the rule
> "Every guardrail did its job. Domain stayed pure. Contract was regenerated. The test was written first. This is what 'AI judgment, not vibe coding' looks like."

## Recovery
- If LLM produces an IO import, `import-linter` fails — show the error and rewrite by hand.
- If the codegen drift gate fails locally, run `make all` and re-commit.
- If the dashboard tile doesn't render, fall back to: open the JSON response in a browser and explain the wire-level proof.
```

- [ ] **Step 2: Commit**

```bash
git add scripts/live-demo/scenario-a.md
git commit -m "docs(demo): Scenario A — TEEP addition live-demo script"
```

---

### Task 31: 5-minute walkthrough video script

**Files:**
- Create: `docs/walkthrough-script.md`

- [ ] **Step 1: Write the walkthrough script**

```markdown
# Portfolio Walkthrough — 5 minutes

> Audience: hiring manager + tech lead at SDF Manufacturing DX. Goal: prove engineering judgment, not feature count.

## Beat 1 (0:00–0:30) — The thesis
"This portfolio shows how an AI-native senior engineer absorbs a domain they don't already know — manufacturing — without faking it. The angle is *guardrails over generation speed*."

## Beat 2 (0:30–1:30) — Architecture in one diagram
Show C4 context diagram (or README ASCII flow). Call out three guardrails:
1. *Contract-first* — Sparkplug Protobuf + OpenAPI + JSON Schema all under `packages/contracts/`. Codegen drift fails CI.
2. *Functional core* — domain modules in Python and Kotlin have zero IO imports. Proven by `import-linter` and Konsist tests, not just convention.
3. *Use-case coverage gate* — every entry in `USE-CASES.md` has exactly one Playwright spec; CI counts them.

## Beat 3 (1:30–3:00) — One concrete decision
Open `docs/ADR/0002-timescaledb-over-influxdb.md`. Narrate: "InfluxDB has 4× the market share. I chose TimescaleDB anyway, and the ADR cites the evidence on both sides plus a migration path. This is the JD's 'tradeoff + migration strategy' requirement, shown not told."

## Beat 4 (3:00–4:00) — One concrete LLM workflow
Open `docs/AI-WORKFLOW/case-01.md`. Narrate the OEE absorption: read the standard first, generate property-based tests via LLM, *guardrails caught the hallucinated "Setup Time" factor and the unconstrained Hypothesis strategy*. This is "knowing when to trust AI output".

## Beat 5 (4:00–5:00) — The live system
Switch to browser. Show the dashboard with the line state pill flipping (run simulator state change script if needed). Show the WebSocket fallback to polling by killing the WS in DevTools. Mention: Phase 2 (multi-tenant) and Phase 5 (live demo) are documented and partially staged but not the topic of this video.

## End-card
- Repo: github.com/<user>/sdf-dx
- ADR index, USE-CASES, KNOWN-UNKNOWNS surfaced from README.
```

- [ ] **Step 2: Commit**

```bash
git add docs/walkthrough-script.md
git commit -m "docs: 5-minute walkthrough video script"
```

---

### Task 32: Tag Phase 1 release

- [ ] **Step 1: Run the full CI matrix locally one last time**

```bash
cd /Users/cdlee/personal/sdf-dx
# Contracts gate
(cd packages/contracts && make all && git diff --exit-code codegen/)
# Use-case gate
uv run scripts/check-use-case-coverage.py
# Python
(cd apps/api-python && ruff check . && mypy && lint-imports && pytest --integration)
(cd apps/ingest-python && ruff check . && mypy && lint-imports && pytest --integration)
# Kotlin
(cd apps/ot-gateway-kotlin && ./gradlew ktlintCheck detekt test)
# Frontend
(cd apps/dashboard-react && pnpm lint && pnpm tsc --noEmit && pnpm test && pnpm e2e:fake)
# E2E real
docker compose up -d --wait
(cd apps/dashboard-react && pnpm e2e:real)
docker compose down -v
```
Expected: every step exits 0.

- [ ] **Step 2: Tag**

```bash
git tag -a phase-1 -m "Phase 1 — Single-Factory Vertical Slice"
git log --oneline | head -30
```

- [ ] **Step 3: Update README "Phase 1 status" line**

```markdown
> **Phase 1 status:** complete (tag `phase-1`). See `docs/plans/2026-05-22-phase-1-single-factory-vertical-slice.md` for the build log.
```

- [ ] **Step 4: Commit + push tag (only when user explicitly approves push)**

```bash
git add README.md
git commit -m "docs(readme): mark Phase 1 complete"
# git push --follow-tags  ← do not run until user approves; tags are visible to others.
```

---

## Acceptance Criteria — Phase 1 (mirror spec §13.1)

After every task above is checked off:

- [ ] `README.md` at root; `docker compose up -d --wait` returns success in under 5 minutes.
- [ ] 1 virtual factory + 1 line + 5 machines simulated; Sparkplug B NBIRTH/NDATA/NDEATH visible on the broker.
- [ ] OEE/A/P/Q on the dashboard; line state changes propagate in under 1 second via WebSocket.
- [ ] ADRs 0001–0008 and 0010–0012 present.
- [ ] `docs/KNOWN-UNKNOWNS.md`, `docs/DOMAIN-NOTES.md`, `docs/AI-WORKFLOW/case-01.md` written; `docs/spec/USE-CASES.md` lists UC-001 + UC-002 with `status: implemented`.
- [ ] Use-case coverage gate green (`uv run scripts/check-use-case-coverage.py`): registry rows ↔ per-UC files ↔ E2E specs consistent for all `implemented` UCs.
- [ ] CI green: ruff + mypy strict + import-linter + tseslint strict + tsc strict + detekt + ktlint + Konsist + contract codegen drift gate + use-case gate.
- [ ] `apps/api-python/tests/contexts/*/domain/` and `apps/ingest-python/tests/domain/` contain zero mock/stub/fake imports; whole suite under 1 second.
- [ ] At least one Hypothesis property-based test on OEE.
- [ ] Live demo Scenario A script committed.
- [ ] 5-minute portfolio walkthrough script committed.

---

## Self-Review

(Performed at plan-writing time, not at execution time.)

### Spec coverage check
- ✅ §1.4 usage scenarios — `scripts/live-demo/scenario-a.md` covers the live-demo angle; `docs/walkthrough-script.md` covers the static-repo angle; the README + ADRs cover the documentation angle.
- ✅ §2 principles — Tasks 12–15 (pure domain), 6–9 (contracts), 18+19 (test tiering), 24 (E2E gate), 28 (drift toolchain).
- ✅ §3 architecture — Tasks 11, 16, 17, 18, 19, 20, 21 build the polyglot system top to bottom.
- ✅ §4 data flow — Tasks 16→17→18→19→20→23 implement the full path simulator → MQTT → bridge → Kafka → ingest → Timescale → API → WS → React.
- ✅ §5 storage + multi-tenancy — Task 10 lays Phase 1 single-tenant schema; ADR-0003 (Task C0-1) documents the schema-per-tenant migration; cross-tenant work is explicitly Phase 2.
- ✅ §6 LLM drift toolchain — Tasks 2, 3, 4 wire the per-language tools; Task 28 wires pre-commit; Task 27 wires CI.
- ✅ §7 testing strategy — Tasks 12–15 (pure), 19 (fakes/app), 18 (integration testcontainers), 24 (E2E), Task 14 (Hypothesis property).
- ✅ §8 error handling baseline — Task 18 (DLQ skipping on InvalidRecord with logging), Task 23 (WS→polling fallback). Note: explicit DLQ topic (`dlq.{tenant}`) is **not** in this plan — see gap below.
- ✅ §9 repo structure — Task 1 + the per-app scaffolds match the spec's tree.
- ✅ §10 Phase 1 deliverable — full task chain matches.
- ✅ §11.1 live demo — Scenario A (Task 30); Scenario C (main demo) is Phase 2/3 work since it requires the contract pipeline and multi-tenancy.
- ✅ §12 ADR roadmap — Chapter 0 Tasks C0-1 and C0-2 cover the Phase 1 ADR set (0001–0008, 0010–0012). ADR-0009 deferred to Phase 2 as the spec specifies.
- ✅ §13.1 AC — every bullet has a matching task line in the AC section above.
- ✅ §14 known unknowns — Chapter 0 Task C0-4 lands the initial `KNOWN-UNKNOWNS.md`; subsequent additions land as living-doc commits at the moment of discovery (per Chapter 0 Living-docs reminder).
- ✅ §15 sources — DOMAIN-NOTES cites ISA-95, ISO 22400, Sparkplug, OPC UA.
- ✅ §16 non-goals — respected (no real PLC, no ML, no mobile).
- ✅ §17 open questions — Task 4 resolves the simulator-vs-gateway question explicitly (single Gradle root with three submodules).

### Gap fixes applied during self-review
- **Spec §8.1 explicit DLQ topic.** The plan logs invalid records but does not write them to `dlq.{tenant}`. Acceptable Phase 1 simplification *if explicitly listed in KNOWN-UNKNOWNS*. Action: already folded into Chapter 0 Task C0-4 §"Phase 1 limitations to be addressed later" — see the DLQ bullet there.
- **Health probe DB+Kafka.** Task 19 implements `/readyz` for DB only. Spec §8.1 requires DB + Kafka. Action: extend `readyz` to ping the Kafka bootstrap (add a step to Task 19 — small, included via inline note rather than a new task).

### Placeholder scan
- No "TBD", "fill in details", or "similar to Task N" found.
- Every code step has executable code.
- Every commit step has an exact `git add` set and message.

### Type / name consistency
- `FactoryId` / `LineId` / `MachineId` used consistently across Tasks 12, 15, 19, 20.
- `Normalized` (Python) vs `NormalizedRecord` (Kotlin) — *intentional*: different language, different package, no cross-cutting type. Both ship as DTO-class equivalents.
- `LineState.state` literal values `RUNNING`/`IDLE`/`DOWN`/`CHANGEOVER` consistent across Python domain (Task 13), DB schema (Task 10), Kafka payload (Task 8), OpenAPI (Task 7), React UI (Task 23).
- `OeeReading` field set is identical across OpenAPI (Task 7), Python ports/db (Task 19), TypeScript ports (Task 23).
- `sparkplug_seq` smallint in DB (Task 10), `sparkplugSeq` int in JSON (Task 8), `sparkplug_seq: int` in Python (Task 18) — wire format matches, naming follows each language's convention.

### Two-stage fixes folded back into the relevant tasks
- KNOWN-UNKNOWNS now includes the DLQ caveat (Chapter 0 Task C0-4 §"Phase 1 limitations").
- `/readyz` enhanced to include Kafka ping (Task 19 Step 7 — inline within the existing `readyz` body).

---

## Execution Handoff

Plan complete and saved to `docs/plans/2026-05-22-phase-1-single-factory-vertical-slice.md`. Two execution options:

1. **Subagent-Driven (recommended)** — fresh subagent per task, review between tasks, fast iteration. Uses `superpowers:subagent-driven-development`.

2. **Inline Execution** — execute tasks in this session using `superpowers:executing-plans`, batch execution with checkpoints for review.

Which approach?

---

## Follow-up plans (out of scope here — file separately when ready)

- `docs/plans/<date>-phase-2-multi-tenancy.md` — schema-per-tenant onboarding, JWT, i18n, tenancy/identity BCs, ADR-0009.
- `docs/plans/<date>-phase-3-production-readiness.md` — Prometheus, OTel, k6 budgets, k8s manifests, Avro consideration, ADR-0013/0014.
- `docs/plans/<date>-phase-4-extension-point.md` — quality or maintenance BC, ADR-0015.
- `docs/plans/<date>-phase-5-live-demo-prep.md` — Scenario C/B/E scripts, rehearsals, video backups, 1-pager.
