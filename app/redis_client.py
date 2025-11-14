import redis
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
    
    def increment_url_count(self, url_path):
        """
        Increment the request count for a given URL path.
        Uses Redis INCR which atomically increments the counter.
        """
        key = f"url_count:{url_path}"
        return self.client.incr(key)
    
    def get_url_stats(self):
        """
        Get all URL request statistics ordered from most to least requested.
        Returns list of dictionaries with 'url' and 'count' keys.
        """
        # Get all keys matching our pattern
        keys = self.client.keys("url_count:*")
        
        stats = []
        for key in keys:
            # Extract URL path from key (remove "url_count:" prefix)
            url_path = key[10:]  # len("url_count:") = 10
            count = int(self.client.get(key))
            stats.append({"url": url_path, "count": count})
        
        # Sort by count (highest first)
        return sorted(stats, key=lambda x: x['count'], reverse=True)