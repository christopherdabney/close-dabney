import redis
import os
import json

NAMESPACE = "url_count"
NAMESPACE_TEST = "test"
METADATA_KEY = "test_metadata"

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
    
    def store_test_metadata(self, metadata, namespace=NAMESPACE_TEST):
        """
        Store test execution metadata in Redis.
        
        Args:
            metadata: Dict containing test execution results
            namespace: Redis namespace for the metadata
        """
        key = f"{namespace}:{METADATA_KEY}"
        
        try:
            return self.client.set(key, json.dumps(metadata))
        except (redis.ConnectionError, redis.TimeoutError, redis.RedisError) as e:
            print(f"Warning: Redis operation failed storing metadata: {e}")
            raise RedisOperationError(f"Failed to store test metadata: {e}")
        except Exception as e:
            print(f"Error: Unexpected error storing metadata: {e}")
            raise
    
    def get_test_metadata(self, namespace=NAMESPACE_TEST):
        """
        Retrieve test execution metadata from Redis.
        
        Args:
            namespace: Redis namespace to query
            
        Returns:
            dict: Test metadata or empty dict if not found
        """
        key = f"{namespace}:{METADATA_KEY}"
        
        try:
            metadata_json = self.client.get(key)
            if metadata_json:
                return json.loads(metadata_json)
            return {}
        except (redis.ConnectionError, redis.TimeoutError, redis.RedisError) as e:
            print(f"Warning: Redis operation failed getting metadata: {e}")
            raise RedisOperationError(f"Failed to get test metadata: {e}")
        except Exception as e:
            print(f"Error: Unexpected error getting metadata: {e}")
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

    def get_url_stats(self, namespace=NAMESPACE, page=0, page_size=25):
        """
        Get paginated URL request statistics with test metadata.
        
        Args:
            namespace: Redis namespace to query
            page: Page number (0-based, defaults to 0 for most impactful URLs)
            page_size: Number of results per page (defaults to 25)
            
        Returns:
            dict: {
                'stats': [{'url': str, 'count': int}, ...],
                'pagination': {
                    'page': int,
                    'page_size': int, 
                    'total_items': int,
                    'total_pages': int,
                    'has_prev': bool,
                    'has_next': bool,
                    'prev_page': int|None,
                    'next_page': int|None
                },
                'metadata': {
                    'successful_requests': int,
                    'failed_requests': int,
                    'completion_rate': float,
                    'circuit_breaker_triggered': bool,
                    'random_strings_used': list,
                    ...
                }
            }
        """
        try:
            # Get all keys matching our URL pattern (exclude metadata key)
            all_keys = self.client.keys(f"{namespace}:*")
            metadata_key = f"{namespace}:{METADATA_KEY}"
            url_keys = [key for key in all_keys if key != metadata_key]
            
            # Build complete stats list
            all_stats = []
            for key in url_keys:
                # Extract URL path from key (remove namespace prefix)
                url_path = key[len(namespace) + 1:]  # +1 for the colon
                count = int(self.client.get(key))
                all_stats.append({"url": url_path, "count": count})
            
            # Sort by count (highest first) - most impactful URLs at page 0
            sorted_stats = sorted(all_stats, key=lambda x: x['count'], reverse=True)
            
            # Calculate pagination
            total_items = len(sorted_stats)
            total_pages = (total_items + page_size - 1) // page_size  # Ceiling division
            
            # Validate page number
            if page < 0:
                page = 0
            elif total_pages > 0 and page >= total_pages:
                page = total_pages - 1
            
            # Calculate slice indices
            start_index = page * page_size
            end_index = start_index + page_size
            
            # Get page slice
            page_stats = sorted_stats[start_index:end_index]
            
            # Build pagination metadata
            pagination = {
                'page': page,
                'page_size': page_size,
                'total_items': total_items,
                'total_pages': total_pages,
                'has_prev': page > 0,
                'has_next': page < total_pages - 1,
                'prev_page': page - 1 if page > 0 else None,
                'next_page': page + 1 if page < total_pages - 1 else None
            }
            
            # Get test metadata
            metadata = self.get_test_metadata(namespace)
            
            return {
                'stats': page_stats,
                'pagination': pagination,
                'metadata': metadata
            }
            
        except (redis.ConnectionError, redis.TimeoutError, redis.RedisError) as e:
            print(f"Warning: Redis operation failed getting stats for namespace {namespace}: {e}")
            raise RedisOperationError(f"Failed to get stats for namespace {namespace}: {e}")
        except Exception as e:
            print(f"Error: Unexpected error getting stats for namespace {namespace}: {e}")
            raise