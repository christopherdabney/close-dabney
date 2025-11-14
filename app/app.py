import asyncio

from datetime import datetime
from flask import Flask, jsonify, request

from .request_client import make_concurrent_requests
from .redis_client import RedisClient, RedisOperationError, NAMESPACE, NAMESPACE_TEST

app = Flask(__name__)
redis_client = RedisClient()

@app.route('/api/', defaults={'path': ''})
@app.route('/api/<path:path>')
def api_endpoints(path):
    """
    Handle all GET requests to /api/* paths.
    This simulates real API endpoints with resilient Redis counting.
    """
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
    """
    # Input validation
    if num_requests <= 0:
        return jsonify({"error": "Number of requests must be positive"}), 400

    # Clear previous test data
    redis_client.clear_namespace(NAMESPACE_TEST)

    # Run async work synchronously
    results = asyncio.run(make_concurrent_requests(num_requests))
    
    return jsonify(results)

@app.route('/stats/')
def get_stats():
    """
    Return JSON report of URL request statistics.
    Ordered from most requested to least requested.
    """
    stats = redis_client.get_url_stats(namespace=NAMESPACE_TEST)
    return jsonify(stats)

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