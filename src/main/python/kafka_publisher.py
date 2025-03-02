import json
import time
import logging
import requests
from requests.exceptions import RequestException
from confluent_kafka import Producer
from confluent_kafka.schema_registry import SchemaRegistryClient, Schema
from confluent_kafka.schema_registry.avro import AvroSerializer
from confluent_kafka.serialization import SerializationContext, MessageField
from kafka.errors import KafkaError
import os
from pyiceberg.catalog import load_catalog
from pyiceberg.types import (
    TimestampType,
    StringType,
    DoubleType,
    StructType,
    NestedField,
)

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

MESSAGE_SCHEMA = {
    "type": "record",
    "name": "PurchaseEvent",
    "namespace": "com.example",
    "doc": "Schema for purchase event messages",
    "fields": [
        {
            "name": "timestamp",
            "type": "long",
            "doc": "Unix timestamp in milliseconds"
        },
        {
            "name": "user_id",
            "type": "string",
            "doc": "Unique identifier for the user"
        },
        {
            "name": "action",
            "type": "string",
            "doc": "Type of action performed"
        },
        {
            "name": "amount",
            "type": "double",
            "doc": "Purchase amount"
        },
        {
            "name": "user_details",
            "type": {
                "type": "record",
                "name": "UserDetails",
                "fields": [
                    {"name": "name", "type": "string"},
                    {"name": "age", "type": "int"},
                    {"name": "email", "type": "string"}
                ]
            },
            "doc": "Structured user details (STRUCT type)"
        },
        {
            "name": "purchase_metadata",
            "type": {
                "type": "map",
                "values": "string"
            },
            "doc": "Additional purchase metadata (MAP type)"
        },
        {
            "name": "previous_purchases",
            "type": {
                "type": "array",
                "items": "double"
            },
            "doc": "List of previous purchase amounts (ARRAY type)"
        }
    ]
}

def create_serializer(schema_registry_client):
    try:
        logger.info("[DEBUG_LOG] Starting schema registration process")

        # Log the complete schema being registered
        logger.info("[DEBUG_LOG] Registering complete schema: %s", json.dumps(MESSAGE_SCHEMA))

        # Log individual complex types for debugging
        logger.info("[DEBUG_LOG] STRUCT type: %s", 
                    next(f for f in MESSAGE_SCHEMA['fields'] if f['name'] == 'user_details'))
        logger.info("[DEBUG_LOG] MAP type: %s", 
                    next(f for f in MESSAGE_SCHEMA['fields'] if f['name'] == 'purchase_metadata'))
        logger.info("[DEBUG_LOG] ARRAY type: %s", 
                    next(f for f in MESSAGE_SCHEMA['fields'] if f['name'] == 'previous_purchases'))

        # Explicitly register the schema first
        topic = os.environ.get('KAFKA_TOPIC', 'iceberg-topic')
        subject = f"{topic}-value"
        try:
            # Prepare schema string
            schema_str = json.dumps(MESSAGE_SCHEMA)
            logger.info("[DEBUG_LOG] Schema string: %s", schema_str)

            # Check if subject exists and handle schema compatibility
            subjects = schema_registry_client.get_subjects()
            logger.info("[DEBUG_LOG] Available subjects: %s", subjects)

            if subject in subjects:
                logger.info("[DEBUG_LOG] Subject already exists: %s", subject)
                # Get the latest schema version
                latest_schema = schema_registry_client.get_latest_version(subject)
                logger.info("[DEBUG_LOG] Found existing schema version: %s", latest_schema)

                # Test compatibility before proceeding
                is_compatible = schema_registry_client.test_compatibility(subject, schema_str)
                if not is_compatible:
                    raise ValueError(f"New schema is not compatible with existing schema in subject {subject}")

                # Use existing schema if compatible
                schema_id = latest_schema.schema_id
            else:
                logger.info("[DEBUG_LOG] Registering new schema for subject: %s", subject)
                # Register new schema
                avro_schema = Schema(schema_str, "AVRO")
                schema_id = schema_registry_client.register_schema(
                    subject,
                    avro_schema
                )

            logger.info("[DEBUG_LOG] Using schema ID: %s", schema_id)
            # Get the registered schema
            registered_schema = schema_registry_client.get_schema(schema_id)
            logger.info("[DEBUG_LOG] Retrieved registered schema: %s", registered_schema.schema_str)
        except Exception as reg_error:
            logger.error("[DEBUG_LOG] Failed to register schema: %s", str(reg_error))
            raise

        # Create serializer with error handling
        serializer = AvroSerializer(
            schema_registry_client,
            registered_schema.schema_str,
            lambda x, ctx: x
        )

        # Test schema registration
        logger.info("[DEBUG_LOG] Testing schema registration...")
        test_message = {
            "timestamp": int(time.time() * 1000),
            "user_id": "test_user",
            "action": "test",
            "amount": 0.0,
            "user_details": {"name": "Test User", "age": 30, "email": "test@example.com"},
            "purchase_metadata": {"test": "value"},
            "previous_purchases": [0.0]
        }

        # Actually try to serialize a test message
        try:
            ctx = SerializationContext("test-topic", MessageField.VALUE)
            serialized_data = serializer(test_message, ctx)
            logger.info("[DEBUG_LOG] Test serialization successful")
        except Exception as se:
            logger.error("[DEBUG_LOG] Test serialization failed: %s", str(se))
            raise

        logger.info("[DEBUG_LOG] Schema registration successful")
        return serializer

    except Exception as e:
        logger.error("[DEBUG_LOG] Error in create_serializer: %s", str(e))
        logger.error("[DEBUG_LOG] Schema Registry Client state: %s", vars(schema_registry_client))
        raise

def create_producer():
    logger.info("Creating Kafka producer with bootstrap servers: %s", 
                os.environ.get('KAFKA_BOOTSTRAP_SERVERS'))

    # Create Schema Registry Client with validation
    schema_registry_url = os.environ.get('SCHEMA_REGISTRY_URL')
    if not schema_registry_url:
        raise ValueError("[DEBUG_LOG] SCHEMA_REGISTRY_URL environment variable is not set")

    logger.info("[DEBUG_LOG] Initializing Schema Registry Client with URL: %s", schema_registry_url)
    schema_registry_conf = {'url': schema_registry_url}

    try:
        schema_registry_client = SchemaRegistryClient(schema_registry_conf)
        # Test the connection to Schema Registry
        try:
            subjects = schema_registry_client.get_subjects()
            logger.info("[DEBUG_LOG] Successfully connected to Schema Registry. Available subjects: %s", subjects)
        except Exception as se:
            logger.error("[DEBUG_LOG] Failed to connect to Schema Registry: %s", str(se))
            raise
    except Exception as e:
        logger.error("[DEBUG_LOG] Failed to create Schema Registry client: %s", str(e))
        raise

    # Create Avro Serializer
    try:
        serializer = create_serializer(schema_registry_client)
        logger.info("[DEBUG_LOG] Successfully created Avro serializer")
    except Exception as e:
        logger.error("[DEBUG_LOG] Failed to create serializer: %s", str(e))
        raise

    # Configure Producer
    producer_conf = {
        'bootstrap.servers': os.environ.get('KAFKA_BOOTSTRAP_SERVERS'),
        'acks': 'all',
        'retries': 5,
        'retry.backoff.ms': 1000
    }

    return {
        'producer': Producer(producer_conf),
        'serializer': serializer
    }

def substitute_env_vars(config):
    """Replace environment variables in the configuration"""
    if isinstance(config, dict):
        return {k: substitute_env_vars(v) for k, v in config.items()}
    elif isinstance(config, list):
        return [substitute_env_vars(v) for v in config]
    elif isinstance(config, str):
        # Find all ${VAR} patterns and replace them with environment variables
        import re
        pattern = r'\$\{([^}]+)\}'
        matches = re.finditer(pattern, config)
        result = config
        for match in matches:
            env_var = match.group(1)
            env_value = os.environ.get(env_var)
            if env_value is None:
                logger.warning(f"Environment variable {env_var} not found")
                continue
            result = result.replace(f"${{{env_var}}}", env_value)
        return result
    return config

def register_connector():
    """Register the Iceberg sink connector with Kafka Connect"""
    connect_url = "http://kafka-connect:8083"
    logger.info("Waiting for Kafka Connect to be ready...")

    # Wait for Kafka Connect to be ready
    max_retries = 30
    retry_interval = 2
    for i in range(max_retries):
        try:
            response = requests.get(f"{connect_url}/connector-plugins")
            if response.status_code == 200:
                logger.info("Kafka Connect is ready")
                break
        except RequestException as e:
            logger.warning("Kafka Connect not ready yet: %s", str(e))
        if i < max_retries - 1:
            time.sleep(retry_interval)
    else:
        raise Exception("Kafka Connect not available after maximum retries")

    # Read connector config
    try:
        with open('connector-config.json', 'r') as f:
            connector_config = json.load(f)
    except Exception as e:
        logger.error("Failed to read connector config: %s", str(e))
        raise

    # Register connector
    try:
        # Replace environment variables in the configuration
        connector_config = substitute_env_vars(connector_config)
        connector_name = connector_config['name']
        logger.info("Registering connector: %s", connector_name)

        # Check if connector already exists
        response = requests.get(f"{connect_url}/connectors/{connector_name}")
        if response.status_code == 200:
            logger.info("Connector %s already exists", connector_name)
            return

        # Create new connector
        response = requests.post(
            f"{connect_url}/connectors",
            headers={"Content-Type": "application/json"},
            data=json.dumps(connector_config)
        )
        if response.status_code in (200, 201):
            logger.info("Successfully registered connector: %s", connector_name)
        else:
            raise Exception(f"Failed to register connector. Status: {response.status_code}, Response: {response.text}")
    except Exception as e:
        logger.error("Failed to register connector: %s", str(e))
        raise

def generate_message():
    timestamp = int(time.time() * 1000)
    user_num = timestamp % 1000
    current_amount = float(int(time.time() * 100) % 1000) / 100

    message = {
        "timestamp": timestamp,
        "user_id": f"user_{user_num}",
        "action": "purchase",
        "amount": current_amount,
        "user_details": {
            "name": f"User Name {user_num}",
            "age": (user_num % 50) + 18,  # Generate age between 18 and 67
            "email": f"user{user_num}@example.com"
        },
        "purchase_metadata": {
            "device": "mobile",
            "location": "online",
            "payment_method": "credit_card",
            "category": "electronics"
        },
        "previous_purchases": [
            float(int((timestamp - i * 1000) * 100) % 1000) / 100 
            for i in range(3)  # Last 3 purchase amounts
        ]
    }
    logger.debug("Generated message: %s", message)
    return message

def delivery_report(err, msg):
    if err is not None:
        logger.error(f'Message delivery failed: {err}')
    else:
        logger.info(f'Message delivered to {msg.topic()} [{msg.partition()}] at offset {msg.offset()}')

def main():
    logger.info("Starting Kafka publisher...")
    try:
        # Register the connector
        register_connector()

        producer_config = create_producer()
        producer = producer_config['producer']
        serializer = producer_config['serializer']
        topic = os.environ.get('KAFKA_TOPIC', 'iceberg-topic')
        logger.info("Successfully created Kafka producer. Publishing to topic: %s", topic)

        while True:
            try:
                message = generate_message()
                logger.info("[DEBUG_LOG] Generated message with complex types:")
                logger.info("[DEBUG_LOG] STRUCT (user_details): %s", message['user_details'])
                logger.info("[DEBUG_LOG] MAP (purchase_metadata): %s", message['purchase_metadata'])
                logger.info("[DEBUG_LOG] ARRAY (previous_purchases): %s", message['previous_purchases'])

                # Serialize the message using the schema
                serialized_message = serializer(
                    message,
                    SerializationContext(topic, MessageField.VALUE)
                )
                logger.info("[DEBUG_LOG] Successfully serialized message with schema")

                # Produce message
                producer.produce(
                    topic=topic,
                    value=serialized_message,
                    on_delivery=delivery_report
                )

                # Flush to ensure message is sent
                producer.flush()

                logger.info("Published message: %s", message)
                time.sleep(5)  # Publish every 5 seconds
            except KafkaError as e:
                logger.error("Error publishing message: %s", str(e))
                time.sleep(5)  # Wait before retrying
            except Exception as e:
                logger.exception("Unexpected error while publishing message")
                time.sleep(5)  # Wait before retrying
    except Exception as e:
        logger.exception("Fatal error in publisher")
        raise

if __name__ == "__main__":
    main()
