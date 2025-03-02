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
   docker-compose up -d --build

   # Monitor service health
   docker-compose ps
   ```

2. Verify service availability:
   - Schema Registry: http://localhost:8081
   - Kafka Connect (Iceberg): http://localhost:8083
   - Kafka Connect (S3): http://localhost:8084
   - MinIO Console: http://localhost:9001
   - PostgreSQL: localhost:5432

### Health Check
Monitor deployment status:
```bash
# Check connector status
curl http://localhost:8083/connectors/iceberg-sink/status
curl http://localhost:8084/connectors/s3-sink/status

# View deployment logs
docker-compose logs -f s3-deployer
docker-compose logs -f kafka-publisher
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

## Monitoring and Maintenance

### Health Monitoring
1. Check service status:
   ```bash
   docker-compose ps
   docker-compose logs -f <service-name>
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

## Troubleshooting

### Common Issues

1. **Connector Deployment Failures**
   - **Symptom**: Connector status shows FAILED
   - **Solution**: 
     ```bash
     # Check detailed error message
     docker-compose logs kafka-connect
     # Verify Schema Registry is accessible
     curl localhost:8081
     ```

2. **Schema Compatibility Issues**
   - **Symptom**: Producer fails to send messages
   - **Solution**:
     ```bash
     # Check Schema Registry logs
     docker-compose logs schema-registry
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
     - Check MinIO container logs: `docker-compose logs minio`

## License

See the [LICENSE](LICENSE) file for details.
