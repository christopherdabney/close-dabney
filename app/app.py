from flask import Flask, jsonify, request
from .redis_client import RedisClient
from datetime import datetime

app = Flask(__name__)
redis_client = RedisClient()

@app.route('/users', methods=['GET'])
def get_users():
    users = redis_client.get_all_users()
    return jsonify(users)

@app.route('/users', methods=['POST'])
def create_user():
    data = request.get_json()
    user_id = redis_client.create_user(data)
    return jsonify({'id': user_id, 'status': 'created'}), 201

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
