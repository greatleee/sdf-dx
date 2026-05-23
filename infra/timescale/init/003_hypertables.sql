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
