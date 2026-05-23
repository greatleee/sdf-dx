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
