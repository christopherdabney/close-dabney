from flask import Flask, jsonify, request
from .redis_client import RedisClient, NAMESPACE, NAMESPACE_TEST
from datetime import datetime
import requests
import random
import string

app = Flask(__name__)
redis_client = RedisClient()

LOCAL_HOST_URL = "http://localhost:5000"

@app.route('/api/', defaults={'path': ''})
@app.route('/api/<path:path>')
def api_endpoints(path):
    """
    Handle all GET requests to /api/* paths.
    This simulates real API endpoints.
    """
    # Construct the full URL path
    url_path = f"/api/{path}" if path else "/api/"
    # Normalize: ensure trailing slash for consistent counting
    if not url_path.endswith('/'):
        url_path += '/'

    source = request.headers.get('X-Request-Source', None)
    redis_client.increment_url_count(url_path, source if source else NAMESPACE)
    
    # Return a simple response (simulating an API endpoint)
    return '', 200

@app.route('/stats/')
def get_stats():
    """
    Return JSON report of URL request statistics.
    Ordered from most requested to least requested.
    """
    stats = redis_client.get_url_stats(namespace=NAMESPACE_TEST)
    return jsonify(stats)

@app.route('/test/<int:num_requests>/', methods=['POST'])
def test_endpoint(num_requests):
    """
    Generate fake requests to test the system.
    Creates random URLs with 1-6 path segments using 3 random strings.
    """
    # Input validation
    if num_requests <= 0:
        return jsonify({"error": "Number of requests must be positive"}), 400
    
    # Do we want an upper limit?
    #if num_requests > 10000:  # reasonable upper limit
    #    return jsonify({"error": "Number of requests exceeds maximum limit of 10,000"}), 400

    # Clear previous test data
    redis_client.clear_namespace(NAMESPACE_TEST)

    # More realistic character set for API identifiers
    chars = string.ascii_letters + string.digits + '-'
    
    # Pick a random length between 3-12 for this test run, all strings same length
    segment_length = random.randint(3, 12)
    
    # Generate 3 random strings for this test run
    random_strings = [
        ''.join(random.choices(chars, k=segment_length)) 
        for _ in range(3)
    ]
    
    generated_urls = []
    
    for _ in range(num_requests):
        # Random number of path segments (1-6)
        num_segments = random.randint(1, 6)
        
        # Build path using random strings
        segments = [random.choice(random_strings) for _ in range(num_segments)]
        url_path = "/api/" + "/".join(segments) + "/"
        
        # Make actual HTTP request to our own API endpoint
        try:
            response = requests.get(
                f"{LOCAL_HOST_URL}{url_path}",
                headers={'X-Request-Source': NAMESPACE_TEST}
            )
            if response.status_code == 200:
                generated_urls.append(url_path)
        except requests.exceptions.RequestException as e:
            # Log error but continue with other requests
            print(f"Request failed for {url_path}: {e}")
    
    return jsonify({
        "message": f"Generated {num_requests} fake requests",
        "successful_requests": len(generated_urls),
        "segment_length": segment_length,
        "random_strings_used": random_strings,
        "sample_urls": generated_urls[:5]  # Show first 5 as examples
    })

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