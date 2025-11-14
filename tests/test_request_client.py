import pytest
from unittest.mock import Mock, patch, AsyncMock, MagicMock
import asyncio
import aiohttp
import sys
sys.path.append('app')

from app.request_client import (
    make_concurrent_requests, 
    make_single_request, 
    FAILURE_RATE_THRESHOLD,
    BATCH_SIZE_FOR_MONITORING,
    LOCAL_HOST_URL
)


@pytest.mark.asyncio
async def test_make_single_request_success_2xx():
    """Test make_single_request with successful 2xx response."""
    mock_session = MagicMock()
    mock_response = MagicMock()
    mock_response.status = 200
    
    # Setup async context manager properly
    mock_session.get.return_value.__aenter__.return_value = mock_response
    mock_session.get.return_value.__aexit__.return_value = None
    
    result = await make_single_request(mock_session, '/api/test/')
    
    assert result == True
    mock_session.get.assert_called_once_with(
        f"{LOCAL_HOST_URL}/api/test/",
        headers={'X-Request-Source': 'test'},
        timeout=aiohttp.ClientTimeout(total=10)
    )


@pytest.mark.asyncio
async def test_make_single_request_success_3xx():
    """Test make_single_request with successful 3xx response."""
    mock_session = MagicMock()
    mock_response = MagicMock()
    mock_response.status = 301
    
    mock_session.get.return_value.__aenter__.return_value = mock_response
    mock_session.get.return_value.__aexit__.return_value = None
    
    result = await make_single_request(mock_session, '/api/test/')
    
    assert result == True


@pytest.mark.asyncio
async def test_make_single_request_client_error_4xx():
    """Test make_single_request with 4xx client error (no retry)."""
    mock_session = MagicMock()
    mock_response = MagicMock()
    mock_response.status = 404
    
    mock_session.get.return_value.__aenter__.return_value = mock_response
    mock_session.get.return_value.__aexit__.return_value = None
    
    result = await make_single_request(mock_session, '/api/test/')
    
    assert result == False


@pytest.mark.asyncio
async def test_make_single_request_server_error_5xx():
    """Test make_single_request with 5xx server error (should retry)."""
    from tenacity import RetryError
    
    mock_session = MagicMock()
    mock_response = MagicMock()
    mock_response.status = 500
    mock_response.request_info = Mock()
    mock_response.history = []
    
    mock_session.get.return_value.__aenter__.return_value = mock_response
    mock_session.get.return_value.__aexit__.return_value = None
    
    # Should retry and then raise RetryError after exhausting attempts
    with pytest.raises(RetryError):
        await make_single_request(mock_session, '/api/test/')


@pytest.mark.asyncio
async def test_make_single_request_connection_error():
    """Test make_single_request with connection error (should retry)."""
    from tenacity import RetryError
    
    mock_session = MagicMock()
    mock_session.get.side_effect = aiohttp.ClientConnectionError("Connection failed")
    
    # Should retry and then raise RetryError after exhausting attempts
    with pytest.raises(RetryError):
        await make_single_request(mock_session, '/api/test/')


@pytest.mark.asyncio
async def test_make_concurrent_requests_basic():
    """Test basic concurrent requests functionality."""
    with patch('app.request_client.generate_segment') as mock_generate_segment, \
         patch('app.request_client.CircuitBreaker') as mock_circuit_breaker_class, \
         patch('aiohttp.ClientSession') as mock_session_class:
        
        # Setup mocks
        mock_generate_segment.return_value = 'test_string'
        mock_circuit_breaker = Mock()
        mock_circuit_breaker_class.return_value = mock_circuit_breaker
        mock_circuit_breaker.should_trip.return_value = False
        mock_circuit_breaker.total_requests = 5
        mock_circuit_breaker.get_stats.return_value = {
            'message': 'Generated 5 fake requests',
            'successful_requests': 5,
            'failed_requests': 0
        }
        
        mock_session = AsyncMock()
        mock_session_class.return_value.__aenter__.return_value = mock_session
        
        # Mock make_single_request to return success
        with patch('app.request_client.make_single_request') as mock_single_request:
            mock_single_request.return_value = True
            
            result = await make_concurrent_requests(5)
            
            assert result['message'] == 'Generated 5 fake requests'


if __name__ == '__main__':
    pytest.main([__file__])