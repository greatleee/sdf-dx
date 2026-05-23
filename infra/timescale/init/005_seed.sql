WITH f AS (
    INSERT INTO factory (name, region, timezone, locale)
    VALUES ('Ulsan Plant', 'KR', 'Asia/Seoul', 'ko-KR')
    RETURNING id
),
l AS (
    INSERT INTO production_line (factory_id, name, isa95_role)
    SELECT id, 'Line A', 'PRODUCTION_LINE' FROM f
    RETURNING id, name
)
INSERT INTO machine (line_id, type, sparkplug_node_id)
SELECT l.id, t.type, 'sdf_default/' || l.name || '/' || t.type
FROM l, (VALUES
    ('press'),
    ('weld'),
    ('paint'),
    ('inspect'),
    ('pack')
) AS t(type);
