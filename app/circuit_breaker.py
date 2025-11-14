"""
Circuit breaker implementation for request failure monitoring and protection.

Provides automatic failure rate monitoring with configurable thresholds,
Redis cleanup on circuit breaker activation, and comprehensive statistics.
"""

from .redis_client import RedisClient, NAMESPACE_TEST


class CircuitBreaker:
    """
    Circuit breaker for monitoring request failure rates and stopping execution
    when failure threshold is exceeded.
    
    Features:
    - Configurable failure rate threshold and minimum sample size
    - Automatic Redis test data cleanup when circuit opens
    - Comprehensive statistics collection and formatting
    - Thread-safe operation for concurrent request monitoring
    """
    
    def __init__(self, failure_threshold=0.20, min_sample_size=20):
        """
        Initialize circuit breaker with configurable parameters.
        
        Args:
            failure_threshold (float): Maximum allowed failure rate (0.0-1.0)
            min_sample_size (int): Minimum requests before checking threshold
        """
        self.failure_threshold = failure_threshold
        self.min_sample_size = min_sample_size
        self.successful_requests = 0
        self.failed_requests = 0
        self.is_open = False
        self.redis_client = RedisClient()
    
    def record_success(self):
        """Record a successful request."""
        self.successful_requests += 1
    
    def record_failure(self, error_message=None):
        """
        Record a failed request with optional error logging.
        
        Args:
            error_message (str, optional): Error description for logging
        """
        self.failed_requests += 1
        if error_message:
            print(f"Request failed: {error_message}")
    
    def should_trip(self):
        """
        Check if circuit breaker should trip based on current failure rate.
        
        Returns:
            bool: True if circuit breaker should open (stop execution)
        """
        total_requests = self.total_requests
        
        # Don't trip before minimum sample size
        if total_requests < self.min_sample_size:
            return False
        
        failure_rate = self.failure_rate
        should_open = failure_rate > self.failure_threshold
        
        if should_open and not self.is_open:
            self.is_open = True
            print(f"Circuit breaker triggered: {failure_rate:.2%} failure rate "
                  f"exceeds {self.failure_threshold:.2%} threshold")
            self._clear_invalid_test_data()
        
        return should_open
    
    def _clear_invalid_test_data(self):
        """Clear test data from Redis when circuit breaker opens."""
        try:
            cleared_keys = self.redis_client.clear_namespace(NAMESPACE_TEST)
            print(f"Cleared {cleared_keys} test keys due to circuit breaker activation")
        except Exception as e:
            print(f"Warning: Failed to clear test data: {e}")
    
    @property
    def total_requests(self):
        """Total number of completed requests."""
        return self.successful_requests + self.failed_requests
    
    @property
    def failure_rate(self):
        """Current failure rate as decimal (0.0-1.0)."""
        total = self.total_requests
        return self.failed_requests / total if total > 0 else 0.0
    
    @property
    def completion_rate(self):
        """Current success rate as decimal (0.0-1.0)."""
        total = self.total_requests
        return self.successful_requests / total if total > 0 else 0.0
    
    def get_stats(self, total_requested=None, total_cancelled=0, random_strings=None):
        """
        Get comprehensive statistics for response formatting.
        
        Args:
            total_requested (int, optional): Total number of requests originally requested
            total_cancelled (int): Number of requests cancelled due to circuit breaker
            random_strings (list, optional): Random strings used for URL generation
            
        Returns:
            dict: Statistics including circuit breaker status and metrics
        """
        stats = {
            "successful_requests": self.successful_requests,
            "failed_requests": self.failed_requests,
            "total_completed": self.total_requests,
            "total_cancelled": total_cancelled,
            "completion_rate": self.completion_rate,
            "failure_rate": self.failure_rate,
            "circuit_breaker_triggered": self.is_open,
            "message": self._generate_message(total_requested)
        }
        
        if random_strings:
            stats["random_strings_used"] = random_strings
            
        return stats
    
    def _generate_message(self, total_requested):
        """
        Generate descriptive message based on circuit breaker state.
        
        Args:
            total_requested (int, optional): Original request count
            
        Returns:
            str: Human-readable status message
        """
        if total_requested is None:
            return f"Completed {self.total_requests} requests"
        
        if self.is_open:
            return (f"Generated {self.total_requests} of {total_requested} "
                   f"requested fake requests (stopped by circuit breaker)")
        else:
            return f"Generated {total_requested} fake requests"
    
    def reset(self):
        """
        Reset circuit breaker state for new test runs.
        Useful for testing or when starting fresh execution cycles.
        """
        self.successful_requests = 0
        self.failed_requests = 0
        self.is_open = False
