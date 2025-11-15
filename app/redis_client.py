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

    def get_url_stats(self, namespace=NAMESPACE, page=0, page_size=25):
        """
        Get paginated URL request statistics ordered from most to least requested.
        
        Args:
            namespace: Redis namespace to query
            page: Page number (0-based, defaults to 0 for most impactful URLs)
            page_size: Number of results per page (defaults to 25)
            
        Returns:
            dict: {
                'url_stats': [{'url': str, 'count': int}, ...],
                'pagination': {
                    'page': int,
                    'page_size': int, 
                    'total_items': int,
                    'total_pages': int,
                    'has_prev': bool,
                    'has_next': bool,
                    'prev_page': int|None,
                    'next_page': int|None
                }
            }
        """
        try:
            # Get all keys matching our pattern
            keys = self.client.keys(f"{namespace}:*")
            
            # Build complete stats list
            all_stats = []
            for key in keys:
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
            
            return {
                'url_stats': page_stats,
                'pagination': pagination
            }
            
        except (redis.ConnectionError, redis.TimeoutError, redis.RedisError) as e:
            print(f"Warning: Redis operation failed getting stats for namespace {namespace}: {e}")
            raise RedisOperationError(f"Failed to get stats for namespace {namespace}: {e}")
        except Exception as e:
            print(f"Error: Unexpected error getting stats for namespace {namespace}: {e}")
            raise