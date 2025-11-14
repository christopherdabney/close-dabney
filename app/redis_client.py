import redis
import os

NAMESPACE = "url_count"
NAMESPACE_TEST = "test"

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
    
    def increment_url_count(self, url_path, namespace=NAMESPACE):
        """
        Increment request count for a URL path with specified namespace.
        Default namespace is 'url_count' for real traffic.
        """
        key = f"{namespace}:{url_path}"
        return self.client.incr(key)
    
    def clear_namespace(self, namespace=NAMESPACE):
        """
        Delete all keys in the specified namespace.
        """
        keys = self.client.keys(f"{namespace}:*")
        if keys:
            self.client.delete(*keys)
        return len(keys)  # Return count of deleted keys

    def get_url_stats(self, namespace=NAMESPACE):

        """
        Get all URL request statistics ordered from most to least requested.
        Returns list of dictionaries with 'url' and 'count' keys.
        """
        # Get all keys matching our pattern
        keys = self.client.keys(f"{namespace}:*")
        
        stats = []
        for key in keys:
            # Extract URL path from key (remove "url_count:" prefix)
            url_path = key[10:]  # len("url_count:") = 10
            count = int(self.client.get(key))
            stats.append({"url": url_path, "count": count})
        
        # Sort by count (highest first)
        return sorted(stats, key=lambda x: x['count'], reverse=True)