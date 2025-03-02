import json
import time
import logging
import requests
from requests.exceptions import RequestException
import os

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

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

def restart_connector(connect_url, connector_name):
    """Restart the connector to apply configuration changes"""
    try:
        logger.info(f"Restarting connector {connector_name}...")
        response = requests.post(f"{connect_url}/connectors/{connector_name}/restart")
        if response.status_code == 204:
            logger.info(f"Successfully restarted connector {connector_name}")
            return True
        else:
            logger.error(f"Failed to restart connector. Status: {response.status_code}, Response: {response.text}")
            return False
    except Exception as e:
        logger.error(f"Error restarting connector: {str(e)}")
        return False

def register_s3_connector():
    """Register the S3 sink connector with Kafka Connect"""
    # Use localhost and exposed port when running outside Docker
    connect_url = "http://s3-kafka-connect:8083"
    logger.info("Waiting for S3 Kafka Connect to be ready...")

    # Wait for Kafka Connect to be ready
    max_retries = 30
    retry_interval = 2
    for i in range(max_retries):
        try:
            response = requests.get(f"{connect_url}/connector-plugins")
            if response.status_code == 200:
                logger.info("S3 Kafka Connect is ready")
                break
        except RequestException as e:
            logger.warning("S3 Kafka Connect not ready yet: %s", str(e))
        if i < max_retries - 1:
            time.sleep(retry_interval)
    else:
        raise Exception("S3 Kafka Connect not available after maximum retries")

    # Read connector config
    try:
        with open('s3-connector-config.json', 'r') as f:
            connector_config = json.load(f)
    except Exception as e:
        logger.error("Failed to read S3 connector config: %s", str(e))
        raise

    # Register connector
    try:
        # Replace environment variables in the configuration
        connector_config = substitute_env_vars(connector_config)
        connector_name = connector_config['name']
        logger.info("Registering S3 connector: %s", connector_name)

        # Check if connector already exists
        response = requests.get(f"{connect_url}/connectors/{connector_name}")
        if response.status_code == 200:
            logger.info("S3 Connector %s exists, updating configuration...", connector_name)
            # Update existing connector configuration
            response = requests.put(
                f"{connect_url}/connectors/{connector_name}/config",
                headers={"Content-Type": "application/json"},
                data=json.dumps(connector_config['config'])
            )
            if response.status_code == 200:
                logger.info("Successfully updated S3 connector configuration")
                # Restart connector to apply new configuration
                if not restart_connector(connect_url, connector_name):
                    raise Exception("Failed to restart connector after configuration update")
            else:
                raise Exception(f"Failed to update S3 connector configuration. Status: {response.status_code}, Response: {response.text}")
            return

        # Create new connector
        response = requests.post(
            f"{connect_url}/connectors",
            headers={"Content-Type": "application/json"},
            data=json.dumps(connector_config)
        )
        if response.status_code in (200, 201):
            logger.info("Successfully registered S3 connector: %s", connector_name)
        else:
            raise Exception(f"Failed to register S3 connector. Status: {response.status_code}, Response: {response.text}")

        # Check connector status
        time.sleep(5)  # Wait for connector to initialize
        response = requests.get(f"{connect_url}/connectors/{connector_name}/status")
        if response.status_code == 200:
            status = response.json()
            logger.info("S3 Connector status: %s", json.dumps(status, indent=2))
        else:
            logger.warning("Failed to get S3 connector status")

    except Exception as e:
        logger.error("Failed to register S3 connector: %s", str(e))
        raise

def main():
    logger.info("Starting S3 connector deployment...")
    try:
        register_s3_connector()
        logger.info("S3 connector deployment completed successfully")
    except Exception as e:
        logger.exception("Fatal error in S3 connector deployment")
        raise

if __name__ == "__main__":
    main()
