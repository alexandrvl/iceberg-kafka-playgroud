import json
import time
import logging
import requests
from requests.exceptions import RequestException
from kafka import KafkaProducer
from kafka.errors import KafkaError
import os
from pyiceberg.catalog import load_catalog
from pyiceberg.schema import Schema
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

def create_producer():
    logger.info("Creating Kafka producer with bootstrap servers: %s", 
                os.environ.get('KAFKA_BOOTSTRAP_SERVERS'))
    return KafkaProducer(
        bootstrap_servers=os.environ.get('KAFKA_BOOTSTRAP_SERVERS'),
        value_serializer=lambda v: json.dumps(v).encode('utf-8'),
        acks='all',  # Wait for all replicas
        retries=5,   # Retry a few times
        retry_backoff_ms=1000  # Wait 1 second between retries
    )

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
    message = {
        "timestamp": timestamp,
        "user_id": f"user_{timestamp % 1000}",
        "action": "purchase",
        "amount": float(int(time.time() * 100) % 1000) / 100
    }
    logger.debug("Generated message: %s", message)
    return message

def main():
    logger.info("Starting Kafka publisher...")
    try:
        # Register the connector
        register_connector()

        producer = create_producer()
        topic = os.environ.get('KAFKA_TOPIC', 'iceberg-topic')
        logger.info("Successfully created Kafka producer. Publishing to topic: %s", topic)

        while True:
            try:
                message = generate_message()
                future = producer.send(topic, value=message)
                # Wait for the message to be delivered
                record_metadata = future.get(timeout=10)
                logger.info(
                    "Published message to topic %s partition %s offset %s: %s",
                    record_metadata.topic,
                    record_metadata.partition,
                    record_metadata.offset,
                    message
                )
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
