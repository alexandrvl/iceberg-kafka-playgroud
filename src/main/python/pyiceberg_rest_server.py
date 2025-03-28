import os
import json
from flask import Flask, request, jsonify
from pyiceberg.catalog import load_catalog
from pyiceberg.catalog.sql import SqlCatalog
from pyiceberg.exceptions import NoSuchTableError

app = Flask(__name__)

# Initialize PyIceberg catalog
catalog = None

def init_pyiceberg():
    """Initialize PyIceberg catalog with necessary configurations."""
    global catalog

    # Get environment variables
    aws_access_key_id = os.environ.get("AWS_ACCESS_KEY_ID")
    aws_secret_access_key = os.environ.get("AWS_SECRET_ACCESS_KEY")
    aws_endpoint_url = os.environ.get("AWS_ENDPOINT_URL", "http://minio:9000")
    postgres_user = os.environ.get("POSTGRES_USER")
    postgres_password = os.environ.get("POSTGRES_PASSWORD")

    # Get catalog configuration from environment variables
    catalog_name = os.environ.get("ICEBERG_CATALOG_NAME", "iceberg")
    warehouse = os.environ.get("ICEBERG_CATALOG_WAREHOUSE", "s3://warehouse/")
    jdbc_uri = os.environ.get("ICEBERG_CATALOG_URI", "jdbc:postgresql://postgres:5432/iceberg")

    # Replace environment variables in the JDBC URI if needed
    if '${POSTGRES_USER}' in jdbc_uri:
        jdbc_uri = jdbc_uri.replace('${POSTGRES_USER}', postgres_user)
    if '${POSTGRES_PASSWORD}' in jdbc_uri:
        jdbc_uri = jdbc_uri.replace('${POSTGRES_PASSWORD}', postgres_password)

    try:

        # Extract the PostgreSQL connection details from the JDBC URI
        # Format: jdbc:postgresql://host:port/database?user=username&password=password
        import re
        import urllib.parse

        # Extract host, port, database
        match = re.match(r'jdbc:postgresql://([^:]+):(\d+)/([^?]+)', jdbc_uri)
        if match:
            host, port, database = match.groups()
        else:
            host = 'postgres'
            port = '5432'
            database = 'iceberg'

        # Extract username and password from query parameters
        username = postgres_user
        password = postgres_password

        # Check if username and password are in the JDBC URL
        query_params = {}
        if '?' in jdbc_uri:
            query_string = jdbc_uri.split('?', 1)[1]
            query_params = dict(param.split('=') for param in query_string.split('&'))

            if 'user' in query_params:
                username = query_params['user']
            if 'password' in query_params:
                password = query_params['password']

        # Construct SQLAlchemy URL
        sqlalchemy_uri = f"postgresql://{username}:{password}@{host}:{port}/{database}"
        print(f"Converted JDBC URI to SQLAlchemy URI: {sqlalchemy_uri}")

        # Initialize the SqlCatalog
        catalog = SqlCatalog(
            catalog_name,
            **{
                'uri': sqlalchemy_uri,
                'warehouse': warehouse,
                's3.endpoint': aws_endpoint_url,
                's3.access-key-id': aws_access_key_id,
                's3.secret-access-key': aws_secret_access_key,
                's3.path-style-access': 'true'
            }
        )
        print(f"PyIceberg catalog '{catalog_name}' initialized successfully")

    except Exception as e:
        print(f"Error initializing PyIceberg catalog: {str(e)}")
        raise

# Initialize PyIceberg when the module is imported
try:
    init_pyiceberg()
except Exception as e:
    print(f"Failed to initialize PyIceberg catalog on import: {str(e)}")
    # Don't raise the exception here to allow the app to start
    # The error will be handled in the endpoint functions

@app.route('/health', methods=['GET'])
def health_check():
    """Health check endpoint."""
    return jsonify({"status": "healthy", "message": "PyIceberg REST server is running"})

@app.route('/namespaces', methods=['GET'])
def list_namespaces():
    """List all namespaces in the catalog."""
    try:
        # Check if catalog is initialized
        if catalog is None:
            return jsonify({"error": "PyIceberg catalog is not initialized. Please check server logs for details."}), 500

        namespaces = catalog.list_namespaces()
        return jsonify({"namespaces": namespaces}), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/tables', methods=['GET'])
def list_tables():
    """List all tables in a namespace."""
    try:
        namespace = request.args.get('namespace', 'default_db')

        # Check if catalog is initialized
        if catalog is None:
            return jsonify({"error": "PyIceberg catalog is not initialized. Please check server logs for details."}), 500

        tables = catalog.list_tables(namespace)
        return jsonify({"namespace": namespace, "tables": tables}), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/table', methods=['GET'])
def get_table():
    """Get table information."""
    try:
        namespace = request.args.get('namespace', 'default_db')
        table_name = request.args.get('table', 'purchase_events')

        if not table_name:
            return jsonify({"error": "Missing 'table' parameter"}), 400

        # Check if catalog is initialized
        if catalog is None:
            return jsonify({"error": "PyIceberg catalog is not initialized. Please check server logs for details."}), 500

        table_identifier = f"{namespace}.{table_name}"
        try:
            table = catalog.load_table(table_identifier)

            # Get table schema
            schema = table.schema()
            schema_dict = {
                "id": schema.schema_id,
                "fields": [{"id": f.field_id, "name": f.name, "type": str(f.field_type)} for f in schema.fields]
            }

            # Get table metadata
            metadata = {
                "location": table.metadata.location,
                "format_version": table.metadata.format_version,
                "properties": table.metadata.properties
            }

            return jsonify({
                "identifier": table_identifier,
                "schema": schema_dict,
                "metadata": metadata
            }), 200

        except NoSuchTableError:
            return jsonify({"error": f"Table {table_identifier} not found"}), 404

    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/query', methods=['POST'])
def query_table():
    print(f"params: {request.json}")

    """Query data from an Iceberg table."""
    try:
        if not request.json:
            return jsonify({"error": "Missing JSON body"}), 400

        namespace = request.json.get('namespace', 'default_db')
        table_name = request.json.get('table', 'purchase_events')
        limit = request.json.get('limit', 100)

        if not table_name:
            return jsonify({"error": "Missing 'table' parameter"}), 400

        print(f"table_name: {table_name}")
       # Check if catalog is initialized
        if catalog is None:
            return jsonify({"error": "PyIceberg catalog is not initialized. Please check server logs for details."}), 500
        print(f"catalog: {catalog}")

        table_identifier = f"{namespace}.{table_name}"
        print(f"table_identifier: {table_identifier}")
        try:
            table = catalog.load_table(table_identifier)
            print(f"table: {table}")

            if table is None:
                return jsonify({"error": f"Failed to load table {table_identifier}"}), 500

            # Create a scan and fetch records
            scan = table.scan()
            print(f"scan: {scan}")

            if scan is None:
                return jsonify({"error": f"Failed to create scan for table {table_identifier}"}), 500
#             print(f"limit: {limit}")
#             if limit:
#                 print(f"scan.limit(limit): {scan.limit(limit)}")
#                 scan = scan.limit(limit)
#                 if scan is None:
#                     return jsonify({"error": f"Failed to apply limit to scan for table {table_identifier}"}), 500
            print(f"scan: {scan}")
            records = []
            print(f"scan: {scan.to_arrow()}")
            for record in scan.to_arrow():
                print(f"record: {record}")
                if record is None:
                    continue  # Skip None records
                # Convert Arrow table to Python dictionary
                print(f"record.to_pylist(): {record.to_pylist()}")
                records.extend(record.to_pylist())
            print(f"records: {records}")

            return jsonify({"records": records}), 200

        except NoSuchTableError:
            return jsonify({"error": f"Table {table_identifier} not found"}), 404

    except Exception as e:
        return jsonify({"error": str(e)}), 500

if __name__ == '__main__':
    # PyIceberg is already initialized when the module is imported
    # No need to call init_pyiceberg() again

    # Run the Flask app
    app.run(host='0.0.0.0', port=8889)
