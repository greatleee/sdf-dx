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
-- sparkplug_node_id is the edge↔topology join key the ingest service resolves
-- (KNOWN-UNKNOWNS "Edge↔topology identifier resolution"). It MUST be the real
-- Sparkplug address `{group}/{edge_node_id}/{machineKey}`, where edge_node_id is
-- the line *slug* — not the display name. The slug 'line-a' matches the
-- simulator's SDF_LINE_ID and the bridge's edge_node_id; machineKey == machine.type.
-- (Earlier this embedded production_line.name 'Line A', which the edge slug never
-- matched — corrected when ingest landed in Phase 1 Section E.)
INSERT INTO machine (line_id, type, sparkplug_node_id)
SELECT l.id, t.type, 'sdf_default/line-a/' || t.type
FROM l, (VALUES
    ('press'),
    ('weld'),
    ('paint'),
    ('inspect'),
    ('pack')
) AS t(type);
