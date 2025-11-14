import redis
import json
import uuid
import os

class RedisClient:
    def __init__(self):
        # Use environment variable for Redis host (Docker vs local)
        redis_host = os.getenv('REDIS_HOST', 'localhost')
        redis_port = int(os.getenv('REDIS_PORT', 6379))
        
        self.client = redis.Redis(
            host=redis_host, 
            port=redis_port, 
            decode_responses=True
        )
    
    def create_user(self, user_data):
        user_id = str(uuid.uuid4())
        user_data['id'] = user_id
        
        # Store user as JSON string in Redis
        self.client.set(f"user:{user_id}", json.dumps(user_data))
        
        # Add to users list for easy retrieval
        self.client.sadd("users", user_id)
        
        return user_id
    
    def get_all_users(self):
        user_ids = self.client.smembers("users")
        users = []
        
        for user_id in user_ids:
            user_data = self.client.get(f"user:{user_id}")
            if user_data:
                users.append(json.loads(user_data))
        
        return users
