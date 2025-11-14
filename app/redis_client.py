import redis
import os

NAMESPACE = "url_count"
NAMESPACE_TEST = "test"

class RedisOperationError(Exception):
    """Raised when any Redis operation fails."""
    pass

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
        Increment request count for a URL path with error handling.
        Returns count on success, None on failure (errors are logged).
        """
        key = f"{namespace}:{url_path}"
        
        try:
            return self.client.incr(key)
        except (redis.ConnectionError, redis.TimeoutError, redis.RedisError) as e:
            print(f"Warning: Redis operation failed for {url_path}: {e}")
            raise RedisOperationError(f"Failed to increment count for {url_path}: {e}")
        except Exception as e:
            print(f"Error: Unexpected error counting request for {url_path}: {e}")
            raise
    
    def clear_namespace(self, namespace=NAMESPACE):
        """
        Delete all keys in the specified namespace.
        Returns count of deleted keys, raises RedisOperationError on failure.
        """
        try:
            keys = self.client.keys(f"{namespace}:*")
            if keys:
                return self.client.delete(*keys)
            return 0
        except (redis.ConnectionError, redis.TimeoutError, redis.RedisError) as e:
            print(f"Warning: Redis operation failed clearing namespace {namespace}: {e}")
            raise RedisOperationError(f"Failed to clear namespace {namespace}: {e}")
        except Exception as e:
            print(f"Error: Unexpected error clearing namespace {namespace}: {e}")
            raise

    def get_url_stats(self, namespace=NAMESPACE):
        """
        Get all URL request statistics ordered from most to least requested.
        Returns list of dictionaries with 'url' and 'count' keys.
        """
        try:
            # Get all keys matching our pattern
            keys = self.client.keys(f"{namespace}:*")
            
            stats = []
            for key in keys:
                # Extract URL path from key (remove namespace prefix)
                url_path = key[len(namespace) + 1:]  # +1 for the colon
                count = int(self.client.get(key))
                stats.append({"url": url_path, "count": count})
            
            # Sort by count (highest first)
            return sorted(stats, key=lambda x: x['count'], reverse=True)
        except (redis.ConnectionError, redis.TimeoutError, redis.RedisError) as e:
            print(f"Warning: Redis operation failed getting stats for namespace {namespace}: {e}")
            raise RedisOperationError(f"Failed to get stats for namespace {namespace}: {e}")
        except Exception as e:
            print(f"Error: Unexpected error getting stats for namespace {namespace}: {e}")
            raise