# Sparkplug B Contracts

Vendored Protobuf schema from Eclipse Tahu v1.0.10. This is the single source of truth for all Sparkplug B payloads in this monorepo (ADR-0005).

`sparkplug_b.proto` is **vendored — do not edit**. It declares `package org.eclipse.tahu.protobuf` (proto2); the upstream `java_package` / `java_outer_classname` options are preserved verbatim, so generated Kotlin/Java land under `codegen/kotlin/org/eclipse/tahu/protobuf/`.

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
