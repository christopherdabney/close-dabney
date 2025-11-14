import asyncio
import aiohttp
import random
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type
from .paths import generate_segment, generate_random_url_path
from .redis_client import NAMESPACE_TEST
from .circuit_breaker import CircuitBreaker

# Retry configuration constants
MAX_RETRY_ATTEMPTS = 3  # 1 initial + 2 retries
REQUEST_TIMEOUT_SECONDS = 10  # Per-request timeout
BACKOFF_BASE_SECONDS = 1  # Base backoff time: 1, 2, 4 seconds

# Circuit breaker configuration
FAILURE_RATE_THRESHOLD = 0.20  # 20% failure rate threshold
BATCH_SIZE_FOR_MONITORING = 20  # Check failure rate every N requests

LOCAL_HOST_URL = "http://localhost:5000"


async def make_concurrent_requests(num_requests):
    """
    Make concurrent HTTP requests to /api/* endpoints with circuit breaker protection.
    Returns test results with success/failure statistics.
    Creates random URLs with 1-6 path segments using 3 random strings.
    """
    # Initialize circuit breaker
    circuit_breaker = CircuitBreaker(
        failure_threshold=FAILURE_RATE_THRESHOLD,
        min_sample_size=BATCH_SIZE_FOR_MONITORING
    )
    
    # Generate 3 random strings for this test run
    random_strings = [
        generate_segment(random.randint(3, 12)) 
        for _ in range(3)
    ]

    # Execute requests with circuit breaker monitoring
    async with aiohttp.ClientSession() as session:
        tasks = []
        
        # Create all tasks upfront
        for _ in range(num_requests):
            url_path = generate_random_url_path(random_strings)
            task = make_single_request(session, url_path)
            tasks.append(task)

        # Process tasks in batches with circuit breaker monitoring
        for i in range(0, len(tasks), BATCH_SIZE_FOR_MONITORING):
            batch_end = min(i + BATCH_SIZE_FOR_MONITORING, len(tasks))
            batch_tasks = tasks[i:batch_end]
            
            # Execute current batch
            batch_results = await asyncio.gather(*batch_tasks, return_exceptions=True)
            
            # Record results in circuit breaker
            for result in batch_results:
                if isinstance(result, Exception):
                    circuit_breaker.record_failure(str(result))
                elif result is True:
                    circuit_breaker.record_success()
                else:  # HTTP error
                    circuit_breaker.record_failure("HTTP error")
            
            # Check if circuit breaker should trip
            if circuit_breaker.should_trip():
                # Cancel remaining tasks
                remaining_tasks = tasks[batch_end:]
                for task in remaining_tasks:
                    if not task.done():
                        task.cancel()
                break
    
    # Calculate cancelled requests
    total_cancelled = num_requests - circuit_breaker.total_requests
    
    return circuit_breaker.get_stats(
        total_requested=num_requests,
        total_cancelled=total_cancelled,
        random_strings=random_strings
    )


@retry(
    stop=stop_after_attempt(MAX_RETRY_ATTEMPTS),
    wait=wait_exponential(multiplier=BACKOFF_BASE_SECONDS, max=8),  # 1, 2, 4, 8 seconds max
    retry=retry_if_exception_type((aiohttp.ClientError, asyncio.TimeoutError))
)
async def make_single_request(session, url_path):
    """
    Make a single HTTP request to an API endpoint with retry logic.
    Retries on: 500s, timeouts, connection errors
    No retry on: 400s (client errors)
    Returns True for success, False for failure after all retries exhausted.
    """
    try:
        async with session.get(
            f"{LOCAL_HOST_URL}{url_path}",
            headers={'X-Request-Source': NAMESPACE_TEST},
            timeout=aiohttp.ClientTimeout(total=REQUEST_TIMEOUT_SECONDS)
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