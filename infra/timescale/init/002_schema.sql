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
