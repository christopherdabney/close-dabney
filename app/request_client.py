import asyncio
import aiohttp
import requests
import random
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type
from .paths import generate_segment, generate_random_url_path
from .redis_client import NAMESPACE_TEST

# Retry configuration constants
MAX_RETRY_ATTEMPTS = 3  # 1 initial + 2 retries
REQUEST_TIMEOUT_SECONDS = 10  # Per-request timeout
BACKOFF_BASE_SECONDS = 1  # Base backoff time: 1, 2, 4 seconds

LOCAL_HOST_URL = "http://localhost:5000"

async def make_concurrent_requests(num_requests):
    """
    Make concurrent HTTP requests to /api/* endpoints.
    Returns test results with success/failure statistics.
    Creates random URLs with 1-6 path segments using 3 random strings.
    """
    successful_requests = 0
    failed_requests = 0
    
    # Generate 3 random strings for this test run
    random_strings = [
        generate_segment(random.randint(3, 12)) 
        for _ in range(3)
    ]

    # Make concurrent HTTP requests
    async with aiohttp.ClientSession() as session:
        tasks = []
        for _ in range(num_requests):
            url_path = generate_random_url_path(random_strings)
            task = make_single_request(session, url_path)
            tasks.append(task)

        # Execute all requests concurrently
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # Process results
        for result in results:
            if isinstance(result, Exception):
                failed_requests += 1
                print(f"Request failed: {result}")
            elif result is True:  # Success
                successful_requests += 1
            else:  # HTTP error
                failed_requests += 1
                print(f"Request failed: HTTP error")
    
    return {
        "message": f"Generated {num_requests} fake requests",
        "successful_requests": successful_requests,
        "failed_requests": failed_requests,
        "completion_rate": successful_requests / num_requests if num_requests > 0 else 0,
        "random_strings_used": random_strings,
    }

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
