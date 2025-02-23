# Iceberg Kafka Connect Playground

This project demonstrates the integration between Apache Kafka and Apache Iceberg using Kafka Connect. It provides a complete playground environment for testing and experimenting with Iceberg table management through Kafka Connect sink connectors.

## Prerequisites

Before running this project, you need to:

1. Download `tabular-iceberg-kafka-connect-0.6.19.zip` separately and place it in the root folder of the project. This file is required for the Kafka Connect Iceberg sink connector.
2. Have Docker and Docker Compose installed on your system.
3. Set up your environment variables:
   - Copy `.env.example` to `.env`
   - Update the values in `.env` with your desired credentials:
     - PostgreSQL credentials (POSTGRES_USER, POSTGRES_PASSWORD)
     - MinIO root credentials (MINIO_ROOT_USER, MINIO_ROOT_PASSWORD)
     - MinIO/AWS user credentials (AWS_ACCESS_KEY_ID, AWS_SECRET_ACCESS_KEY)

## Project Components

The playground consists of the following services:

- **Kafka & Zookeeper**: Message streaming platform (Confluent Platform 7.3.0)
- **PostgreSQL**: Metadata storage for Iceberg tables
- **MinIO**: S3-compatible object storage for Iceberg data files
- **Kafka Connect**: With Iceberg sink connector integration
- **Kafka Publisher**: Example data publisher service

## Getting Started

1. Ensure you have placed `tabular-iceberg-kafka-connect-0.6.19.zip` in the project root directory
2. Start all services:
   ```bash
   docker-compose up -d
   ```
3. Wait for all services to be healthy (you can check status with `docker-compose ps`)
4. The following endpoints will be available:
   - Kafka Connect: http://localhost:8083
   - MinIO Console: http://localhost:9001 (credentials: minioadmin/minioadmin)
   - PostgreSQL: localhost:5432 (credentials: iceberg/iceberg)

## Configuration

The project includes:
- Preconfigured Kafka Connect environment
- MinIO setup with required buckets and permissions
- PostgreSQL with initialized Iceberg catalog
- Example publisher service for data generation

### Connector Configuration

The Iceberg sink connector is preconfigured with the following key settings:

```json
{
  "connector.class": "io.tabular.iceberg.connect.IcebergSinkConnector",
  "topics": "iceberg-topic",
  "iceberg.tables": "default_db.purchase_events",
  "iceberg.tables.evolve-schema-enabled": "true",
  "iceberg.tables.auto-create-enabled": "true",
  "iceberg.tables.auto-create-namespace": "true"
}
```

Key features enabled:
- Automatic table creation
- Schema evolution
- Parquet format with Snappy compression
- Automatic namespace creation
- 5-second commit intervals

For full configuration details, see [connector-config.json](connector-config.json).

## License

See the [LICENSE](LICENSE) file for details.
