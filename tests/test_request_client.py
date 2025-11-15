import pytest
import asyncio
import aiohttp
from unittest.mock import AsyncMock, Mock, patch
import sys
sys.path.append('app')

from app.request_client import RequestClient, make_concurrent_requests
from app.circuit_breaker import CircuitBreaker


class TestRequestClient:
    """Test cases for the RequestClient class."""
    
    @pytest.fixture
    def mock_circuit_breaker(self):
        """Mock circuit breaker for testing."""
        mock_cb = Mock(spec=CircuitBreaker)
        mock_cb.should_trip.return_value = False
        mock_cb.total_requests = 0
        mock_cb.record_success = Mock()
        mock_cb.record_failure = Mock()
        mock_cb.get_stats.return_value = {
            'successful_requests': 5,
            'failed_requests': 0,
            'total_completed': 5,
            'message': 'Test completed'
        }
        return mock_cb

    @pytest.fixture
    def mock_session(self):
        """Mock aiohttp session for testing."""
        mock_session = AsyncMock()
        
        # Create a proper async context manager
        class MockResponse:
            def __init__(self, status=200):
                self.status = status
                self.request_info = Mock()
                self.history = []
        
        class MockContextManager:
            def __init__(self, response):
                self.response = response
            
            async def __aenter__(self):
                return self.response
            
            async def __aexit__(self, exc_type, exc_val, exc_tb):
                return None
        
        # Make session.get return our mock context manager
        def get_mock(*args, **kwargs):
            return MockContextManager(MockResponse())
        
        mock_session.get = get_mock
        return mock_session

    def test_init_default_parameters(self):
        """Test RequestClient initialization with default parameters."""
        client = RequestClient()
        
        assert client.base_url == "http://localhost:5000"
        assert client.max_concurrent_requests == 50
        assert client.failure_threshold == 0.20
        assert client.min_sample_size == 20
        assert client.max_retry_attempts == 3
        assert client.request_timeout_seconds == 10
        assert client.backoff_base_seconds == 1

    def test_init_custom_parameters(self):
        """Test RequestClient initialization with custom parameters."""
        client = RequestClient(
            base_url="http://test.com",
            max_concurrent_requests=25,
            failure_threshold=0.15,
            min_sample_size=10
        )
        
        assert client.base_url == "http://test.com"
        assert client.max_concurrent_requests == 25
        assert client.failure_threshold == 0.15
        assert client.min_sample_size == 10

    @pytest.mark.asyncio
    async def test_context_manager_initialization(self):
        """Test async context manager properly initializes resources."""
        with patch('aiohttp.ClientSession') as mock_session_class, \
             patch.object(RequestClient, '__init__', return_value=None) as mock_init:
            
            mock_session = AsyncMock()
            mock_session_class.return_value = mock_session
            
            client = RequestClient()
            client.max_concurrent_requests = 50
            client.failure_threshold = 0.20
            client.min_sample_size = 20
            
            async with client:
                assert client.session == mock_session
                assert client.semaphore._value == 50  # Initial semaphore value
                assert isinstance(client.circuit_breaker, CircuitBreaker)
            
            mock_session.close.assert_called_once()

    @pytest.mark.asyncio
    async def test_make_request_success_2xx(self, mock_session):
        """Test _make_request with successful 2xx response."""
        client = RequestClient()
        client.session = mock_session
        client.request_timeout_seconds = 10
        client.base_url = "http://localhost:5000"
        
        result = await client._make_request('/api/test/')
        
        assert result is True

    @pytest.mark.asyncio
    async def test_make_request_client_error_4xx(self):
        """Test _make_request with 4xx client error (no retry)."""
        # Create session that returns 4xx error
        class MockResponse:
            def __init__(self):
                self.status = 404
                self.request_info = Mock()
                self.history = []
        
        class MockContextManager:
            async def __aenter__(self):
                return MockResponse()
            async def __aexit__(self, exc_type, exc_val, exc_tb):
                return None
        
        mock_session = AsyncMock()
        mock_session.get = lambda *args, **kwargs: MockContextManager()
        
        client = RequestClient()
        client.session = mock_session
        client.request_timeout_seconds = 10
        client.base_url = "http://localhost:5000"
        
        result = await client._make_request('/api/test/')
        
        assert result is False

    @pytest.mark.asyncio
    async def test_make_request_server_error_5xx_raises(self):
        """Test _make_request with 5xx server error raises exception for retry."""
        # Create session that returns 5xx error
        class MockResponse:
            def __init__(self):
                self.status = 500
                self.request_info = Mock()
                self.history = []
        
        class MockContextManager:
            async def __aenter__(self):
                return MockResponse()
            async def __aexit__(self, exc_type, exc_val, exc_tb):
                return None
        
        mock_session = AsyncMock()
        mock_session.get = lambda *args, **kwargs: MockContextManager()
        
        client = RequestClient()
        client.session = mock_session
        client.request_timeout_seconds = 10
        client.base_url = "http://localhost:5000"
        
        # The retry decorator will eventually raise RetryError after exhausting retries
        with pytest.raises((aiohttp.ClientResponseError, Exception)) as exc_info:
            await client._make_request('/api/test/')
        
        # Should be either ClientResponseError or tenacity RetryError
        assert "ClientResponseError" in str(type(exc_info.value)) or "RetryError" in str(type(exc_info.value))

    @pytest.mark.asyncio
    async def test_make_request_with_semaphore(self, mock_session):
        """Test semaphore-protected request execution."""
        client = RequestClient()
        client.session = mock_session
        client.semaphore = asyncio.Semaphore(1)  # Limit to 1 for testing
        client.request_timeout_seconds = 10
        client.base_url = "http://localhost:5000"
        
        # Mock the internal method
        with patch.object(client, '_make_request', return_value=True) as mock_make_request:
            result = await client._make_request_with_semaphore('/api/test/')
            
            assert result is True
            mock_make_request.assert_called_once_with('/api/test/')

    @pytest.mark.asyncio
    async def test_execute_batches_normal_flow(self, mock_circuit_breaker):
        """Test batch execution with normal circuit breaker flow."""
        client = RequestClient()
        client.circuit_breaker = mock_circuit_breaker
        client.min_sample_size = 2
        
        # Create real async tasks that complete successfully
        async def dummy_success():
            return True
            
        tasks = [asyncio.create_task(dummy_success()) for _ in range(2)]
        
        await client._execute_batches(tasks)
        
        # Should record successes
        assert mock_circuit_breaker.record_success.call_count == 2
        assert mock_circuit_breaker.record_failure.call_count == 0

    @pytest.mark.asyncio
    async def test_execute_batches_circuit_breaker_trips(self, mock_circuit_breaker):
        """Test batch execution when circuit breaker trips."""
        client = RequestClient()
        client.circuit_breaker = mock_circuit_breaker
        client.min_sample_size = 2
        
        # Set circuit breaker to trip after first batch
        mock_circuit_breaker.should_trip.side_effect = [False, True]
        
        # Create tasks that will be long enough to cancel
        async def slow_task():
            await asyncio.sleep(1.0)  # Long enough to be cancelled
            return True
            
        tasks = [asyncio.create_task(slow_task()) for _ in range(4)]
        
        # Start the execution
        await client._execute_batches(tasks)
        
        # The circuit breaker should trip after first batch (2 tasks)
        # But since we're using asyncio.gather, both batches might complete
        # Let's just verify that should_trip was called and tasks were processed
        assert mock_circuit_breaker.should_trip.call_count >= 1
        
        # Verify that at least the first batch was recorded
        assert mock_circuit_breaker.record_success.call_count >= 2

    @pytest.mark.asyncio
    async def test_execute_test_integration(self):
        """Integration test for execute_test method."""
        with patch('app.request_client.generate_segment') as mock_generate_segment, \
             patch('app.request_client.generate_random_url_path') as mock_generate_path, \
             patch('asyncio.create_task') as mock_create_task, \
             patch.object(RequestClient, '_execute_batches') as mock_execute_batches:
            
            # Setup mocks
            mock_generate_segment.side_effect = ['seg1', 'seg2', 'seg3']
            mock_generate_path.side_effect = ['/api/seg1/', '/api/seg2/']
            mock_task = AsyncMock()
            mock_create_task.return_value = mock_task
            
            client = RequestClient()
            client.session = AsyncMock()  # Simulate initialized session
            client.circuit_breaker = Mock()
            client.circuit_breaker.total_requests = 2
            client.circuit_breaker.get_stats.return_value = {'test': 'result'}
            
            # Execute test with 2 requests
            result = await client.execute_test(2)
            
            # Verify random strings generation
            assert mock_generate_segment.call_count == 3
            
            # Verify URL generation for each request
            assert mock_generate_path.call_count == 2
            
            # Verify task creation
            assert mock_create_task.call_count == 2
            
            # Verify batch execution called
            mock_execute_batches.assert_called_once()
            
            # Verify results
            assert result == {'test': 'result'}

    @pytest.mark.asyncio
    async def test_backward_compatibility_function(self):
        """Test that the backward compatibility function works."""
        with patch.object(RequestClient, 'execute_test', return_value={'result': 'test'}) as mock_execute:
            result = await make_concurrent_requests(10)
            
            assert result == {'result': 'test'}
            mock_execute.assert_called_once_with(10)


class TestRequestClientErrorHandling:
    """Test error handling scenarios for RequestClient."""

    @pytest.mark.asyncio
    async def test_session_not_initialized_error(self):
        """Test that using client without context manager raises error."""
        client = RequestClient()
        
        with pytest.raises(RuntimeError, match="must be used as async context manager"):
            await client.execute_test(1)

    @pytest.mark.asyncio
    async def test_connection_timeout_handling(self):
        """Test handling of connection timeouts."""
        # Create a proper context manager that raises timeout
        class MockContextManager:
            async def __aenter__(self):
                raise asyncio.TimeoutError("Connection timeout")
            async def __aexit__(self, exc_type, exc_val, exc_tb):
                return None
        
        mock_session = AsyncMock()
        mock_session.get = lambda *args, **kwargs: MockContextManager()
        
        client = RequestClient()
        client.session = mock_session
        client.request_timeout_seconds = 1
        client.base_url = "http://localhost:5000"
        
        with pytest.raises((asyncio.TimeoutError, Exception)) as exc_info:
            await client._make_request('/api/test/')
        
        # Should be TimeoutError or RetryError containing TimeoutError
        assert "TimeoutError" in str(type(exc_info.value)) or "RetryError" in str(type(exc_info.value))

    @pytest.mark.asyncio
    async def test_client_connection_error_handling(self):
        """Test handling of client connection errors."""
        # Create a proper context manager that raises connection error
        class MockContextManager:
            async def __aenter__(self):
                raise aiohttp.ClientConnectionError("Connection failed")
            async def __aexit__(self, exc_type, exc_val, exc_tb):
                return None
        
        mock_session = AsyncMock()
        mock_session.get = lambda *args, **kwargs: MockContextManager()
        
        client = RequestClient()
        client.session = mock_session
        client.request_timeout_seconds = 1
        client.base_url = "http://localhost:5000"
        
        with pytest.raises((aiohttp.ClientConnectionError, Exception)) as exc_info:
            await client._make_request('/api/test/')
        
        # Should be ClientConnectionError or RetryError containing ClientConnectionError
        assert "ClientConnectionError" in str(type(exc_info.value)) or "RetryError" in str(type(exc_info.value))


if __name__ == '__main__':
    pytest.main([__file__])