# Iceberg Kafka Connect Playground

This project demonstrates the integration between Apache Kafka and Apache Iceberg using Kafka Connect, with additional S3 sink capabilities. It provides a complete playground environment for testing and experimenting with both Iceberg table management and S3 data lake storage through Kafka Connect sink connectors.

## Architecture Overview

The playground implements a robust data pipeline with the following components:

### Data Sinks
1. **Iceberg Sink**: Stores data in Apache Iceberg tables managed by a PostgreSQL catalog
2. **S3 Sink**: Stores data directly in S3-compatible storage (MinIO)

Both connectors consume from the same Kafka topic ('iceberg-topic') but store the data in different formats and locations.

### Message Schema
The system uses a rich message schema that includes:
- Basic fields (timestamp, user_id, action, amount)
- Structured user details (STRUCT type)
- Purchase metadata (MAP type)
- Previous purchases history (ARRAY type)

All messages are validated through Schema Registry to ensure data consistency.

## Prerequisites

Before running this project, ensure you have:

### Required Files
1. Connector Archives (place in project root):
   - `tabular-iceberg-kafka-connect-0.6.19.zip` - Iceberg sink connector
   - `confluentinc-kafka-connect-s3-10.5.23.zip` - S3 sink connector

### System Requirements
1. Docker Engine (version 20.10.0 or later)
2. Docker Compose (version 2.0.0 or later)
3. At least 4GB of available RAM
4. Internet access for downloading Docker images

### Environment Setup
1. Create environment file:
   ```bash
   cp .env.example .env
   ```
2. Configure the following variables in `.env`:
   - PostgreSQL settings:
     - `POSTGRES_USER`: Database username
     - `POSTGRES_PASSWORD`: Database password
   - MinIO settings:
     - `MINIO_ROOT_USER`: MinIO admin username
     - `MINIO_ROOT_PASSWORD`: MinIO admin password
     - `AWS_ACCESS_KEY_ID`: S3 access key
     - `AWS_SECRET_ACCESS_KEY`: S3 secret key

## System Architecture

The playground consists of the following integrated services:

### Core Services
- **Kafka & Zookeeper**: Message streaming platform (Confluent Platform 7.3.0)
  - Handles message queuing and distribution
  - Supports multiple consumers with different formats
- **Schema Registry**: Schema evolution and compatibility management
  - Validates message format
  - Ensures data consistency
  - Supports Avro schema format

### Storage Services
- **PostgreSQL**: Metadata storage
  - Manages Iceberg table metadata
  - Stores table schemas and snapshots
- **MinIO**: S3-compatible object storage
  - Stores Iceberg data files
  - Handles S3 sink data
  - Provides S3 API compatibility
- **DuckDB REST API**: Analytical query engine
  - Queries Parquet files from S3 sink
  - Provides REST API for data analysis
- **PyIceberg REST API**: Iceberg-specific query engine
  - Queries Iceberg tables using PyIceberg
  - Provides REST API for Iceberg table operations

### Connector Services
- **Kafka Connect (Iceberg)**: Primary connector service
  - Manages Iceberg table creation
  - Handles schema evolution
  - Supports transaction management
- **S3 Kafka Connect**: Secondary connector service
  - Manages S3 data sink
  - Handles JSON data formatting
  - Supports custom partitioning

### Support Services
- **Kafka Publisher**: Data generation service
  - Produces sample purchase events
  - Implements retry mechanisms
  - Handles schema validation
- **S3 Deployer**: Automation service
  - Deploys S3 connector configuration
  - Monitors connector health
  - Handles configuration updates

## Getting Started

### Initial Setup
1. Place connector files in project root:
   ```bash
   # Copy connector files to project root
   cp /path/to/tabular-iceberg-kafka-connect-0.6.19.zip .
   cp /path/to/confluentinc-kafka-connect-s3-10.5.23.zip .
   ```

2. Configure environment:
   ```bash
   # Create and edit environment file
   cp .env.example .env
   # Edit .env with your preferred settings
   ```

### Deployment
1. Start the infrastructure:
   ```bash
   # Build and start all services
   docker compose up -d --build

   # Monitor service health
   docker compose ps
   ```

2. Verify service availability:
   - Schema Registry: http://localhost:8081
   - Kafka Connect (Iceberg): http://localhost:8083
   - Kafka Connect (S3): http://localhost:8084
   - MinIO Console: http://localhost:9001
   - PostgreSQL: localhost:5432
   - DuckDB REST API: http://localhost:8888
   - PyIceberg REST API: http://localhost:8889

### Health Check
Monitor deployment status:
```bash
# Check connector status
curl http://localhost:8083/connectors/iceberg-sink/status
curl http://localhost:8084/connectors/s3-sink/status

# View deployment logs
docker compose logs -f s3-deployer
docker compose logs -f kafka-publisher
```

## Configuration

### Infrastructure Setup
The project automatically configures:
- Kafka Connect environment with required plugins
- MinIO buckets and permissions
- PostgreSQL with Iceberg catalog
- Schema Registry with compatibility settings

### Data Generation
The publisher service generates sample purchase events with:
- Randomized user data
- Structured purchase information
- Historical purchase records
- Metadata attributes

### Connector Configurations

#### Iceberg Sink Connector
```json
{
  "connector.class": "io.tabular.iceberg.connect.IcebergSinkConnector",
  "topics": "iceberg-topic",
  "iceberg.tables": "default_db.purchase_events"
}
```

Key Features:
- **Schema Evolution**: Automatic schema updates (`evolve-schema-enabled`)
- **Auto Creation**: Tables and namespaces created automatically
- **Storage Format**: Parquet with Snappy compression
- **Commit Interval**: 5-second intervals for consistent state
- **Full Config**: See [connector-config.json](connector-config.json)

#### S3 Sink Connector
```json
{
  "connector.class": "io.confluent.connect.s3.S3SinkConnector",
  "topics": "iceberg-topic",
  "s3.bucket.name": "s3-sink"
}
```

Key Features:
- **Format**: Parquet data storage
- **Partitioning**: Default time-based partitioning
- **Performance**: Configurable flush size and rotation
- **Credentials**: Automatic environment variable substitution
- **Full Config**: See [s3-connector-config.json](s3-connector-config.json)

### DuckDB S3 Configuration

The DuckDB service uses a secure method for storing AWS credentials using the CREATE SECRET command:

#### Using CREATE SECRET for AWS Credentials

Instead of directly setting the AWS credentials using the `s3_access_key_id` and `s3_secret_access_key` parameters, we create a secret using the CREATE SECRET command and reference it using the `s3_secret_name` parameter:

```python
# Create a secret for AWS credentials
conn.execute(f"""
CREATE SECRET IF NOT EXISTS aws_credentials TYPE aws AS (
    'aws_access_key_id' = '{aws_access_key_id}',
    'aws_secret_access_key' = '{aws_secret_access_key}'
)
""")

# Use the secret for S3 configuration
conn.execute("SET s3_secret_name = 'aws_credentials'")
```

This approach is more secure because:
- It prevents the credentials from being exposed in query logs or error messages
- It provides a centralized way to manage credentials
- It follows security best practices for handling sensitive information

#### Handling S3 Endpoint URL

The S3 endpoint URL is processed to ensure compatibility with DuckDB's httpfs extension:

```python
# Remove the protocol (http:// or https://) from the endpoint URL
# This is to fix an issue with DuckDB's httpfs extension
endpoint_for_s3 = aws_endpoint_url
if aws_endpoint_url and (aws_endpoint_url.startswith("http://") or aws_endpoint_url.startswith("https://")):
    # Extract the host and port part without the protocol
    endpoint_for_s3 = aws_endpoint_url.split("://")[1]
conn.execute(f"SET s3_endpoint='{endpoint_for_s3}'")
```

This ensures that DuckDB's httpfs extension won't strip the protocol incorrectly, which was causing connection errors.

## Monitoring and Maintenance

### Health Monitoring
1. Check service status:
   ```bash
   docker compose ps
   docker compose logs -f <service-name>
   ```

2. Verify connector health:
   ```bash
   curl -s localhost:8083/connectors/iceberg-sink/status | jq
   curl -s localhost:8084/connectors/s3-sink/status | jq
   ```

3. Monitor data flow:
   - MinIO Console: http://localhost:9001
     - `warehouse`: Iceberg tables
     - `s3-sink`: JSON data
   - Schema Registry: http://localhost:8081
     - Schema versions
     - Compatibility status
   - DuckDB REST API: http://localhost:8888
     - REST endpoints for data queries
     - Health check at /health
   - PyIceberg REST API: http://localhost:8889
     - REST endpoints for Iceberg table operations
     - Health check at /health

### Using DuckDB REST API for Data Analysis

The DuckDB REST API service provides a powerful interface for analyzing data stored in both Parquet and Iceberg formats in MinIO S3.

#### Accessing DuckDB REST API

The REST API is available at http://localhost:8888 and provides the following endpoints:

1. **Health Check**:
   ```bash
   curl http://localhost:8888/health
   ```
   Returns the health status of the DuckDB REST API service.

2. **Execute Custom SQL Query**:
   ```bash
   curl -X POST -H "Content-Type: application/json" \
     -d '{"query": "SELECT * FROM read_parquet(\"s3://s3-sink/topics/iceberg-topic/partition=0/*.parquet\") LIMIT 5"}' \
     http://localhost:8888/query
   ```
   Executes a custom SQL query and returns the results as JSON.

3. **List Parquet Files**:
   ```bash
   curl "http://localhost:8888/list_parquet?path=s3://s3-sink/topics/iceberg-topic/partition=*/*.parquet"
   ```
   Lists Parquet files in the specified S3 path.

4. **Query Parquet Data**:
   ```bash
   curl "http://localhost:8888/query_parquet?path=s3://s3-sink/topics/iceberg-topic/partition=0/*.parquet&limit=5"
   ```
   Queries Parquet data from the specified S3 path and returns the results as JSON.

#### Example Queries

1. **Query Parquet files from S3 sink**:
   ```bash
   # List available Parquet files
   curl "http://localhost:8888/list_parquet"

   # Query Parquet data
   curl "http://localhost:8888/query_parquet"
   ```

2. **Execute a custom SQL query**:
   ```bash
   # Query data with custom SQL
   curl -X POST -H "Content-Type: application/json" \
     -d '{
       "query": "SELECT * FROM read_parquet(\"s3://s3-sink/topics/iceberg-topic/partition=0/*.parquet\") LIMIT 10"
     }' \
     http://localhost:8888/query
   ```

Note: The actual paths may vary based on your data. Use the `/list_parquet` endpoint to discover the available Parquet files in your environment.

### Using PyIceberg REST API for Iceberg Table Operations

The PyIceberg REST API service provides a specialized interface for working with Apache Iceberg tables using the PyIceberg Python library (version 0.9.0).

#### Accessing PyIceberg REST API

The REST API is available at http://localhost:8889 and provides the following endpoints:

1. **Health Check**:
   ```bash
   curl http://localhost:8889/health
   ```
   Returns the health status of the PyIceberg REST API service.

2. **List Namespaces**:
   ```bash
   curl http://localhost:8889/namespaces
   ```
   Lists all namespaces (databases) in the Iceberg catalog.

3. **List Tables**:
   ```bash
   curl "http://localhost:8889/tables?namespace=default_db"
   ```
   Lists all tables in the specified namespace (defaults to 'default_db').

4. **Get Table Information**:
   ```bash
   curl "http://localhost:8889/table?namespace=default_db&table=purchase_events"
   ```
   Returns detailed information about the specified table, including schema and metadata.

5. **Query Table Data**:
   ```bash
   curl -X POST -H "Content-Type: application/json" \
     -d '{
       "namespace": "default_db",
       "table": "purchase_events",
       "limit": 10
     }' \
     http://localhost:8889/query
   ```
   Queries data from the specified Iceberg table and returns the results as JSON.

#### Example Queries

1. **List all namespaces**:
   ```bash
   curl http://localhost:8889/namespaces
   ```

2. **List tables in the default namespace**:
   ```bash
   curl http://localhost:8889/tables
   ```

3. **Get table schema and metadata**:
   ```bash
   curl "http://localhost:8889/table?table=purchase_events"
   ```

4. **Query table data with limit**:
   ```bash
   curl -X POST -H "Content-Type: application/json" \
     -d '{
       "table": "purchase_events",
       "limit": 5
     }' \
     http://localhost:8889/query
   ```

Note: The PyIceberg REST API uses the configuration from connector-config.json to connect to the Iceberg catalog using Apache Iceberg SQL catalog based on PostgreSQL, ensuring consistency with the Iceberg sink connector.

### Common Operations
1. Restart a connector:
   ```bash
   curl -X POST localhost:8083/connectors/iceberg-sink/restart
   curl -X POST localhost:8084/connectors/s3-sink/restart
   ```

2. Update connector config:
   ```bash
   curl -X PUT -H "Content-Type: application/json" \
       --data @connector-config.json \
       localhost:8083/connectors/iceberg-sink/config
   ```

### Rebuilding and Validating DuckDB Service

If you need to rebuild the DuckDB service after making changes:

1. Rebuild the DuckDB service:
   ```bash
   # Rebuild the DuckDB service
   docker compose build duckdb

   # Start the DuckDB service
   docker compose up -d duckdb
   ```

2. Validate DuckDB with Parquet:
   ```bash
   # Run the test script to validate functionality
   docker exec -it duckdb python /app/notebooks/test_duckdb.py
   ```

3. Check logs for errors:
   ```bash
   # View the DuckDB service logs
   docker compose logs duckdb
   ```

4. Expected results:
   - Successful connection to DuckDB
   - Successful loading of extensions (httpfs, parquet)
   - Successful listing and querying of Parquet files

## Troubleshooting

### Common Issues

1. **Connector Deployment Failures**
   - **Symptom**: Connector status shows FAILED
   - **Solution**: 
     ```bash
     # Check detailed error message
     docker compose logs kafka-connect
     # Verify Schema Registry is accessible
     curl localhost:8081
     ```

2. **Schema Compatibility Issues**
   - **Symptom**: Producer fails to send messages
   - **Solution**:
     ```bash
     # Check Schema Registry logs
     docker compose logs schema-registry
     # Verify schema compatibility
     curl localhost:8081/subjects/iceberg-topic-value/versions
     ```

3. **MinIO Connection Issues**
   - **Symptom**: S3 connector fails to write data
   - **Solution**:
     - Verify MinIO credentials in `.env`
     - Check MinIO is accessible: `curl localhost:9001`
     - Verify bucket permissions

4. **Performance Issues**
   - **Symptom**: Slow data ingestion or high latency
   - **Solution**:
     - Adjust `flush.size` and `rotate.interval.ms`
     - Monitor resource usage: `docker stats`
     - Check network connectivity between services

5. **MinIO "Text file busy" Error**
   - **Symptom**: Error message: `/bin/sh: line 1: /usr/bin/mc: Text file busy`
   - **Solution**:
     - This occurs due to a race condition when executing the MinIO client (mc) right after installation
     - Add a small delay (1-2 seconds) after chmod and before executing mc
     - Ensure proper error handling for mc commands
     - Check MinIO container logs: `docker compose logs minio`

6. **DuckDB REST API Connection Issues**
   - **Symptom**: Unable to query S3 data from DuckDB REST API
   - **Solution**:
     - Verify S3 credentials in environment variables
     - Check MinIO is accessible: `curl -I http://minio:9000`
     - Check if the REST API is running: `curl http://localhost:8888/health`
     - Check DuckDB REST API logs: `docker compose logs duckdb-rest`
     - Verify the S3 path format is correct (should be `s3://bucket-name/path`)
     - Test a simple query: `curl -X POST -H "Content-Type: application/json" -d '{"query":"SELECT 1"}' http://localhost:8888/query`


7. **DuckDB S3 Connection Error**
   - **Symptom**: Error message: `IO Error: Connection error for HTTP GET to '//minio:9000/s3-sink/?encoding-type=url&list-type=2&prefix=topics%2Ficeberg-topic%2Fpartition%3D'`
   - **Root Cause**: DuckDB's httpfs extension strips the "http:" part from the endpoint URL, resulting in an invalid URL format.
   - **Solution**:
     - Remove the protocol (http:// or https://) from the endpoint URL before setting it using the `s3_endpoint` parameter:
       ```python
       # Remove the protocol (http:// or https://) from the endpoint URL
       if aws_endpoint_url and (aws_endpoint_url.startswith("http://") or aws_endpoint_url.startswith("https://")):
           # Extract the host and port part without the protocol
           aws_endpoint_url = aws_endpoint_url.split("://")[1]
       conn.execute(f"SET s3_endpoint='{aws_endpoint_url}'")
       ```
     - This ensures that DuckDB's httpfs extension won't strip the protocol incorrectly, which was causing the connection error.
     - Files that were modified to fix this issue:
       - `src/main/python/init_duckdb.py`
       - `notebooks/test_duckdb.py`
       - `notebooks/query_examples.py`
       - `notebooks/test_duckdb_notebook.ipynb`

8. **PyIceberg REST API Connection Issues**
   - **Symptom**: Unable to query Iceberg tables from PyIceberg REST API
   - **Solution**:
     - Verify PostgreSQL credentials in environment variables
     - Check if the REST API is running: `curl http://localhost:8889/health`
     - Check PyIceberg REST API logs: `docker compose logs pyiceberg-rest`
     - Verify the connector-config.json file is correctly mounted in the container
     - Test a simple query: `curl http://localhost:8889/namespaces`

9. **PyIceberg Catalog Configuration Issues**
   - **Symptom**: Error message: `Error initializing PyIceberg catalog`
   - **Root Cause**: Incorrect SQL catalog configuration or missing environment variables
   - **Solution**:
     - Verify the catalog configuration in connector-config.json
     - Check that all required environment variables are set
     - Ensure PostgreSQL is accessible from the PyIceberg container
     - Verify that the SQL catalog is properly configured with the PostgreSQL connection details
     - Check that the PyIceberg version is 0.9.0: `docker exec -it pyiceberg-rest pip freeze | grep pyiceberg`

## License

See the [LICENSE](LICENSE) file for details.
