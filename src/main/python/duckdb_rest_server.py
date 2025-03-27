import duckdb
import os
import json
from flask import Flask, request, jsonify

app = Flask(__name__)

# Initialize DuckDB connection
conn = None

def init_duckdb():
    """Initialize DuckDB with necessary extensions and configurations."""
    global conn
    conn = duckdb.connect(database=":memory:", read_only=False)

    # Install and load extensions
    conn.install_extension("httpfs")
    conn.load_extension("httpfs")
    conn.install_extension("parquet")
    conn.load_extension("parquet")

    # Configure S3 connection
    conn.execute("SET s3_region='eu-central-1'")
    aws_access_key_id = os.environ.get("AWS_ACCESS_KEY_ID")
    aws_secret_access_key = os.environ.get("AWS_SECRET_ACCESS_KEY")
    aws_endpoint_url = os.environ.get("AWS_ENDPOINT_URL")

    # Create a secret for AWS credentials
    conn.execute(f"""
    CREATE SECRET IF NOT EXISTS aws_credentials (
        TYPE s3,
        KEY_ID '{aws_access_key_id}',
        SECRET '{aws_secret_access_key}',
        REGION 'eu-central-1'
    )
    """)

    # Secret is created but not referenced by name as s3_secret_name is not supported in this DuckDB version

    # Check if using HTTP or HTTPS and set SSL accordingly
    use_ssl = True
    if aws_endpoint_url and aws_endpoint_url.startswith("http://"):
        use_ssl = False
    conn.execute(f"SET s3_use_ssl='{str(use_ssl).lower()}'")

    # Remove the protocol (http:// or https://) from the endpoint URL
    # This is to fix an issue with DuckDB's httpfs extension
    endpoint_for_s3 = aws_endpoint_url
    if aws_endpoint_url and (aws_endpoint_url.startswith("http://") or aws_endpoint_url.startswith("https://")):
        # Extract the host and port part without the protocol
        endpoint_for_s3 = aws_endpoint_url.split("://")[1]
    conn.execute(f"SET s3_endpoint='{endpoint_for_s3}'")

    # Configure S3 to use path style access (required for MinIO)
    conn.execute("SET s3_url_style='path'")

    # Additional S3 settings that might help with connection issues
    conn.execute("SET http_timeout='300'")

    print("DuckDB initialized with S3 configuration")

@app.route('/health', methods=['GET'])
def health_check():
    """Health check endpoint."""
    return jsonify({"status": "healthy", "message": "DuckDB REST server is running"})

@app.route('/query', methods=['POST'])
def execute_query():
    """Execute a SQL query and return the results as JSON."""
    if not request.json or 'query' not in request.json:
        return jsonify({"error": "Missing 'query' parameter"}), 400

    query = request.json['query']
    limit = request.json.get('limit', 1000)  # Default limit to 1000 rows

    try:
        # Execute the query
        result = conn.execute(query).fetchdf().head(limit)

        # Convert to JSON
        result_json = result.to_json(orient='records')
        return result_json, 200, {'Content-Type': 'application/json'}
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/list_parquet', methods=['GET'])
def list_parquet():
    """List Parquet files in S3."""
    try:
        # Get the bucket and prefix from the path
        default_path = 's3://s3-sink/topics/iceberg-topic/year=2025/month=03/day=02/hour=16/*.parquet'
        path = request.args.get('path', default_path)

        # Extract bucket and prefix
        parts = path.replace('s3://', '').split('/', 1)
        bucket = parts[0]
        prefix = parts[1] if len(parts) > 1 else ''

        # Use a more specific query that doesn't rely on glob
        # This approach uses a direct SQL query to list files
        query = f"""
        SELECT * FROM read_parquet('{path}')
        LIMIT 0
        """

        try:
            # First try to read a specific Parquet file to check connectivity
            conn.execute(query)

            # If that works, then try to list files using glob
            result = conn.execute(f"SELECT * FROM glob('{path}')").fetchdf()
            return result.to_json(orient='records'), 200, {'Content-Type': 'application/json'}
        except Exception as inner_e:
            # If the direct query fails, try an alternative approach
            # Use the query_parquet endpoint's approach which is known to work
            try:
                # Use a more specific path without wildcards
                specific_path = path.replace('*', '0')
                result = conn.execute(f"SELECT * FROM read_parquet('{specific_path}')").fetchdf()
                return result.to_json(orient='records'), 200, {'Content-Type': 'application/json'}
            except Exception as inner_e2:
                return jsonify({"error": f"Failed to list Parquet files: {str(inner_e)}, Alternative approach failed: {str(inner_e2)}"}), 500
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/query_parquet', methods=['GET'])
def query_parquet():
    """Query Parquet data from S3."""
    try:
        path = request.args.get('path', 's3://s3-sink/topics/iceberg-topic/year=2025/month=03/day=02/hour=16/*.parquet')
        limit = request.args.get('limit', 5)
        result = conn.execute(f"SELECT * FROM read_parquet('{path}') LIMIT {limit}").fetchdf()
        return result.to_json(orient='records'), 200, {'Content-Type': 'application/json'}
    except Exception as e:
        return jsonify({"error": str(e)}), 500

if __name__ == '__main__':
    # Initialize DuckDB
    init_duckdb()

    # Run the Flask app
    app.run(host='0.0.0.0', port=8888)
