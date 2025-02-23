-- Create Iceberg catalog schema and default schema for tables
CREATE SCHEMA IF NOT EXISTS iceberg;
CREATE SCHEMA IF NOT EXISTS default_db;

-- Grant permissions to default_db schema
GRANT ALL ON SCHEMA default_db TO iceberg;
GRANT ALL ON ALL TABLES IN SCHEMA default_db TO iceberg;

-- Create tables for Iceberg catalog
CREATE TABLE IF NOT EXISTS iceberg.tables (
    table_id bigint NOT NULL GENERATED ALWAYS AS IDENTITY,
    table_namespace varchar(255),
    table_name varchar(255),
    metadata_location text,
    previous_metadata_location text,
    created_at timestamp with time zone DEFAULT current_timestamp,
    PRIMARY KEY (table_id),
    UNIQUE (table_namespace, table_name)
);

CREATE TABLE IF NOT EXISTS iceberg.snapshots (
    snapshot_id bigint NOT NULL,
    table_id bigint NOT NULL,
    parent_id bigint,
    sequence_number bigint,
    manifest_list text,
    created_at timestamp with time zone DEFAULT current_timestamp,
    PRIMARY KEY (snapshot_id, table_id),
    FOREIGN KEY (table_id) REFERENCES iceberg.tables(table_id)
);

CREATE TABLE IF NOT EXISTS iceberg.properties (
    table_id bigint NOT NULL,
    key varchar(255) NOT NULL,
    value text,
    PRIMARY KEY (table_id, key),
    FOREIGN KEY (table_id) REFERENCES iceberg.tables(table_id)
);

-- Grant permissions
GRANT ALL ON SCHEMA iceberg TO iceberg;
GRANT ALL ON ALL TABLES IN SCHEMA iceberg TO iceberg;
GRANT ALL ON SCHEMA default_db TO iceberg;
GRANT ALL ON ALL TABLES IN SCHEMA default_db TO iceberg;
