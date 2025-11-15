import asyncio
import aiohttp
import random
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type
from .paths import generate_segment, generate_random_url_path
from .redis_client import NAMESPACE_TEST
from .circuit_breaker import CircuitBreaker


class RequestClient:
    """
    Async HTTP client for making concurrent requests with circuit breaker protection
    and configurable concurrency limits.
    """
    
    def __init__(self, 
                 base_url="http://localhost:5000",
                 max_concurrent_requests=50,
                 failure_threshold=0.20,
                 min_sample_size=20,
                 max_retry_attempts=3,
                 request_timeout_seconds=10,
                 backoff_base_seconds=1):
        """
        Initialize RequestClient with configurable parameters.
        
        Args:
            base_url: Target server URL
            max_concurrent_requests: Maximum concurrent requests to prevent server overload
            failure_threshold: Circuit breaker failure rate threshold (0.0-1.0)
            min_sample_size: Minimum requests before checking circuit breaker threshold
            max_retry_attempts: Maximum retry attempts per request (1 initial + N retries)
            request_timeout_seconds: Per-request timeout
            backoff_base_seconds: Base backoff time for exponential backoff
        """
        self.base_url = base_url
        self.max_concurrent_requests = max_concurrent_requests
        self.failure_threshold = failure_threshold
        self.min_sample_size = min_sample_size
        self.max_retry_attempts = max_retry_attempts
        self.request_timeout_seconds = request_timeout_seconds
        self.backoff_base_seconds = backoff_base_seconds
        
        # Runtime state (initialized in __aenter__)
        self.session = None
        self.semaphore = None
        self.circuit_breaker = None
    
    async def __aenter__(self):
        """Async context manager entry - initialize session and runtime state."""
        self.session = aiohttp.ClientSession()
        self.semaphore = asyncio.Semaphore(self.max_concurrent_requests)
        self.circuit_breaker = CircuitBreaker(
            failure_threshold=self.failure_threshold,
            min_sample_size=self.min_sample_size
        )
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit - cleanup session."""
        if self.session:
            await self.session.close()
    
    async def execute_test(self, num_requests):
        """
        Execute a test run with specified number of concurrent requests.
        
        Args:
            num_requests: Total number of requests to generate
            
        Returns:
            dict: Test results with success/failure statistics and circuit breaker info
        """
        if not self.session:
            raise RuntimeError("RequestClient must be used as async context manager")
        
        # Generate 3 random strings for this test run
        random_strings = [
            generate_segment(random.randint(3, 12)) 
            for _ in range(3)
        ]
        
        # Create all tasks upfront with semaphore protection
        tasks = []
        for _ in range(num_requests):
            url_path = generate_random_url_path(random_strings)
            task = asyncio.create_task(self._make_request_with_semaphore(url_path))
            tasks.append(task)
        
        # Process tasks in batches with circuit breaker monitoring
        await self._execute_batches(tasks)
        
        # Calculate cancelled requests
        total_cancelled = num_requests - self.circuit_breaker.total_requests
        
        return self.circuit_breaker.get_stats(
            total_requested=num_requests,
            total_cancelled=total_cancelled,
            random_strings=random_strings
        )
    
    async def _execute_batches(self, tasks):
        """
        Execute tasks in batches with circuit breaker monitoring.
        
        Args:
            tasks: List of asyncio tasks to execute
        """
        for i in range(0, len(tasks), self.min_sample_size):
            batch_end = min(i + self.min_sample_size, len(tasks))
            batch_tasks = tasks[i:batch_end]
            
            # Execute current batch
            batch_results = await asyncio.gather(*batch_tasks, return_exceptions=True)
            
            # Record results in circuit breaker
            for result in batch_results:
                if isinstance(result, Exception):
                    self.circuit_breaker.record_failure(str(result))
                elif result is True:
                    self.circuit_breaker.record_success()
                else:  # HTTP error
                    self.circuit_breaker.record_failure("HTTP error")
            
            # Check if circuit breaker should trip
            if self.circuit_breaker.should_trip():
                # Cancel remaining tasks
                remaining_tasks = tasks[batch_end:]
                for task in remaining_tasks:
                    if not task.done():
                        task.cancel()
                break
    
    async def _make_request_with_semaphore(self, url_path):
        """
        Wrapper function that applies semaphore-based concurrency limiting
        to individual HTTP requests.
        
        Args:
            url_path: URL path to request
            
        Returns:
            bool: True for success, False for failure
        """
        async with self.semaphore:
            return await self._make_request(url_path)
    
    @retry(
        stop=stop_after_attempt(3),  # Will be dynamically set in __init__
        wait=wait_exponential(multiplier=1, max=8),  # Will be dynamically set
        retry=retry_if_exception_type((aiohttp.ClientError, asyncio.TimeoutError))
    )
    async def _make_request(self, url_path):
        """
        Make a single HTTP request to an API endpoint with retry logic.
        
        Args:
            url_path: URL path to request
            
        Returns:
            bool: True for success, False for failure after all retries exhausted
            
        Raises:
            aiohttp.ClientError: For connection/network errors (triggers retry)
            asyncio.TimeoutError: For request timeouts (triggers retry)
        """
        try:
            async with self.session.get(
                f"{self.base_url}{url_path}",
                headers={'X-Request-Source': NAMESPACE_TEST},
                timeout=aiohttp.ClientTimeout(total=self.request_timeout_seconds)
            ) as response:
                if 400 <= response.status < 500:
                    # Client error - don't retry, fail immediately
                    return False
                elif response.status >= 500:
                    # Server error - raise exception to trigger retry
                    raise aiohttp.ClientResponseError(
                        request_info=response.request_info,
                        history=response.history,
                        status=response.status
                    )
                else:
                    # Success (2xx, 3xx)
                    return True
        except (aiohttp.ClientError, asyncio.TimeoutError) as e:
            # These exceptions will trigger retry via tenacity
            raise


# Convenience function to maintain backward compatibility
async def make_concurrent_requests(num_requests):
    """
    Backward compatibility function for existing code.
    
    Args:
        num_requests: Number of requests to make
        
    Returns:
        dict: Test results from RequestClient.execute_test()
    """
    async with RequestClient() as client:
        return await client.execute_test(num_requests)


# Legacy function aliases (to be removed after updating callers)
async def make_single_request_with_semaphore(session, url_path, semaphore):
    """Deprecated: Use RequestClient class instead."""
    raise DeprecationWarning("Use RequestClient class instead")


async def make_single_request(session, url_path):
    """Deprecated: Use RequestClient class instead."""
    raise DeprecationWarning("Use RequestClient class instead")