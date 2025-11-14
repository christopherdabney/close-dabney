from flask import Flask, jsonify, request
from .redis_client import RedisClient
from datetime import datetime

app = Flask(__name__)
redis_client = RedisClient()

@app.route('/api/', defaults={'path': ''})
@app.route('/api/<path:path>')
def api_endpoints(path):
    """
    Handle all GET requests to /api/* paths.
    This simulates real API endpoints.
    """
    # Construct the full URL path
    url_path = f"/api/{path}" if path else "/api/"
    
    # Count this request
    redis_client.increment_url_count(url_path)
    
    # Return a simple response (simulating an API endpoint)
    return jsonify({
        "message": f"API endpoint: {url_path}",
        "timestamp": str(datetime.now())
    })

@app.route('/stats/')
def get_stats():
    """
    Return JSON report of URL request statistics.
    Ordered from most requested to least requested.
    """
    stats = redis_client.get_url_stats()
    return jsonify(stats)

@app.route('/test/<int:num_requests>/', methods=['POST'])
def test_endpoint(num_requests):
    """
    Generate fake requests to test the system.
    Creates random URLs with 1-6 path segments using 3 random strings.
    """
    import random
    import string
    
    # Generate 3 random strings for this test run
    random_strings = [
        ''.join(random.choices(string.ascii_lowercase, k=5)) 
        for _ in range(3)
    ]
    
    generated_urls = []
    
    for _ in range(num_requests):
        # Random number of path segments (1-6)
        num_segments = random.randint(1, 6)
        
        # Build path using random strings
        segments = [random.choice(random_strings) for _ in range(num_segments)]
        url_path = "/api/" + "/".join(segments) + "/"
        
        # Count this simulated request
        redis_client.increment_url_count(url_path)
        generated_urls.append(url_path)
    
    return jsonify({
        "message": f"Generated {num_requests} fake requests",
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