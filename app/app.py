import asyncio

from datetime import datetime
from flask import Flask, jsonify, request

from .request_client import RequestClient
from .redis_client import RedisClient, RedisOperationError, NAMESPACE, NAMESPACE_TEST
from .validation import validate_api_path, validate_pagination_params, validate_test_request_count

app = Flask(__name__)
redis_client = RedisClient()

@app.route('/api/', defaults={'path': ''})
@app.route('/api/<path:path>')
def api_endpoints(path):
    """
    Handle all GET requests to /api/* paths with input validation.
    This simulates real API endpoints with resilient Redis counting.
    """
    # Validate input path
    is_valid, error_msg = validate_api_path(path)
    if not is_valid:
        return jsonify({"error": f"Invalid path: {error_msg}"}), 400
    # Construct the full URL path
    url_path = f"/api/{path}" if path else "/api/"
    # Normalize: ensure trailing slash for consistent counting
    if not url_path.endswith('/'):
        url_path += '/'

    # Determine namespace based on request source
    source = request.headers.get('X-Request-Source', None)
    namespace = source if source else NAMESPACE
    is_test_request = source == NAMESPACE_TEST
    
    # Attempt to count request - Redis client handles all error cases
    try:
        redis_client.increment_url_count(url_path, namespace)
    except RedisOperationError:
        # For test requests, fail if Redis counting failed
        if is_test_request:
            return jsonify({"error": "Redis counting failed during test"}), 500
        # For real requests, continue normally even if counting failed
    
    return '', 200

@app.route('/test/<int:num_requests>/', methods=['POST'])
def test_endpoint(num_requests):
    """
    Generate fake requests to test the system.
    Stores test metadata in Redis for stats endpoint.
    """
    # Input validation
    is_valid, error_msg = validate_test_request_count(num_requests)
    if not is_valid:
        return jsonify({"error": error_msg}), 400

    # Clear previous test data (including metadata)
    redis_client.clear_namespace(NAMESPACE_TEST)

    # Run async work using RequestClient class
    async def run_test():
        async with RequestClient() as client:
            return await client.execute_test(num_requests)
    
    results = asyncio.run(run_test())
    
    # Store test metadata in Redis for stats endpoint
    try:
        redis_client.store_test_metadata(results, NAMESPACE_TEST)
    except RedisOperationError as e:
        print(f"Warning: Failed to store test metadata: {e}")
        # Continue anyway - test completed successfully
    
    return jsonify(results)

@app.route('/stats/')
def get_stats():
    """
    Return combined JSON with stats, pagination, and test metadata.
    Ordered from most requested to least requested.
    
    Query Parameters:
        page (int): Page number, 0-based (default: 0)
        page_size (int): Results per page (default: 25, max: 1000)
        
    Returns:
        JSON with stats, pagination, and metadata keys
    """
    try:
        # Parse query parameters
        page = request.args.get('page', 0, type=int)
        page_size = request.args.get('page_size', 25, type=int)
        
        # Validate parameters
        is_valid, error_msg = validate_pagination_params(page, page_size)
        if not is_valid:
            return jsonify({"error": error_msg}), 400
        
        # Get combined statistics with metadata
        result = redis_client.get_url_stats(
            namespace=NAMESPACE_TEST, 
            page=page, 
            page_size=page_size
        )
        
        return jsonify(result)
        
    except RedisOperationError as e:
        return jsonify({
            "error": "Failed to retrieve statistics",
            "details": str(e)
        }), 500
    except Exception as e:
        return jsonify({
            "error": "Internal server error",
            "details": str(e)
        }), 500

@app.route('/health')
def health_check():
    try:
        # Test Redis connection
        redis_client.client.ping()
        return jsonify({
            'status': 'healthy',
            'redis': 'connected',
            'timestamp': str(datetime.now())
        })
    except Exception as e:
        return jsonify({
            'status': 'unhealthy',
            'redis': 'disconnected',
            'error': str(e),
            'timestamp': str(datetime.now())
        }), 500

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)