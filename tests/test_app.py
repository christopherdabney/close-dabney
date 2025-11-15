import pytest
import json
from unittest.mock import Mock, patch, AsyncMock
import sys
sys.path.append('app')

from app.app import app
from app.redis_client import RedisOperationError, NAMESPACE, NAMESPACE_TEST


class TestFlaskApp:
    """Test cases for the Flask application endpoints."""
    
    @pytest.fixture
    def client(self):
        """Create a test client for the Flask application."""
        app.config['TESTING'] = True
        with app.test_client() as client:
            yield client

    @pytest.fixture
    def mock_redis_client(self):
        """Mock Redis client for testing."""
        with patch('app.app.redis_client') as mock_redis:
            mock_redis.increment_url_count = Mock()
            mock_redis.clear_namespace = Mock()
            mock_redis.get_url_stats = Mock(return_value=[])
            mock_redis.client.ping = Mock()
            yield mock_redis


class TestAPIEndpoints(TestFlaskApp):
    """Test the /api/* endpoints."""

    def test_api_root_endpoint(self, client, mock_redis_client):
        """Test GET /api/ endpoint."""
        response = client.get('/api/')
        
        assert response.status_code == 200
        assert response.data == b''
        
        # Verify Redis counting was called with correct namespace
        mock_redis_client.increment_url_count.assert_called_once_with('/api/', NAMESPACE)

    def test_api_with_path_segments(self, client, mock_redis_client):
        """Test GET /api/products/123/ endpoint."""
        response = client.get('/api/products/123/')
        
        assert response.status_code == 200
        assert response.data == b''
        
        # Verify Redis counting was called
        mock_redis_client.increment_url_count.assert_called_once_with('/api/products/123/', NAMESPACE)

    def test_api_path_normalization(self, client, mock_redis_client):
        """Test that API paths are normalized with trailing slashes."""
        response = client.get('/api/products/123')
        
        assert response.status_code == 200
        
        # Should normalize to include trailing slash
        mock_redis_client.increment_url_count.assert_called_once_with('/api/products/123/', NAMESPACE)

    def test_api_with_test_header(self, client, mock_redis_client):
        """Test API endpoint with X-Request-Source header for test traffic."""
        headers = {'X-Request-Source': NAMESPACE_TEST}
        response = client.get('/api/test/', headers=headers)
        
        assert response.status_code == 200
        
        # Should use test namespace
        mock_redis_client.increment_url_count.assert_called_once_with('/api/test/', NAMESPACE_TEST)

    def test_api_redis_failure_real_traffic(self, client, mock_redis_client):
        """Test API endpoint continues working when Redis fails for real traffic."""
        mock_redis_client.increment_url_count.side_effect = RedisOperationError("Redis down")
        
        response = client.get('/api/products/')
        
        # Should still return 200 for real traffic even if Redis fails
        assert response.status_code == 200

    def test_api_redis_failure_test_traffic(self, client, mock_redis_client):
        """Test API endpoint fails when Redis fails for test traffic."""
        mock_redis_client.increment_url_count.side_effect = RedisOperationError("Redis down")
        headers = {'X-Request-Source': NAMESPACE_TEST}
        
        response = client.get('/api/products/', headers=headers)
        
        # Should return 500 for test traffic if Redis fails
        assert response.status_code == 500
        data = json.loads(response.data)
        assert 'error' in data
        assert 'Redis counting failed' in data['error']


class TestStatsEndpoint(TestFlaskApp):
    """Test the /stats/ endpoint."""

    def test_stats_empty(self, client, mock_redis_client):
        """Test /stats/ endpoint with no data."""
        mock_redis_client.get_url_stats.return_value = []
        
        response = client.get('/stats/')
        
        assert response.status_code == 200
        data = json.loads(response.data)
        assert data == []
        
        # Should request test namespace stats
        mock_redis_client.get_url_stats.assert_called_once_with(namespace=NAMESPACE_TEST)

    def test_stats_with_data(self, client, mock_redis_client):
        """Test /stats/ endpoint with statistics data."""
        mock_stats = [
            {'url': '/api/products/', 'count': 5},
            {'url': '/api/users/', 'count': 3}
        ]
        mock_redis_client.get_url_stats.return_value = mock_stats
        
        response = client.get('/stats/')
        
        assert response.status_code == 200
        data = json.loads(response.data)
        assert data == mock_stats

    def test_stats_content_type(self, client, mock_redis_client):
        """Test /stats/ endpoint returns proper JSON content type."""
        mock_redis_client.get_url_stats.return_value = []
        
        response = client.get('/stats/')
        
        assert response.content_type == 'application/json'


class TestTestEndpoint(TestFlaskApp):
    """Test the /test/ endpoint."""

    def test_test_endpoint_success(self, client, mock_redis_client):
        """Test POST /test/10/ with valid request."""
        mock_result = {
            'successful_requests': 10,
            'failed_requests': 0,
            'message': 'Test completed'
        }
        
        with patch('app.app.RequestClient') as mock_request_client_class:
            # Mock the async context manager and execute_test method
            mock_client_instance = AsyncMock()
            mock_client_instance.execute_test.return_value = mock_result
            mock_request_client_class.return_value.__aenter__.return_value = mock_client_instance
            mock_request_client_class.return_value.__aexit__.return_value = None
            
            response = client.post('/test/10/')
            
            assert response.status_code == 200
            data = json.loads(response.data)
            assert data == mock_result
            
            # Verify Redis namespace was cleared
            mock_redis_client.clear_namespace.assert_called_once_with(NAMESPACE_TEST)

    def test_test_endpoint_zero_requests(self, client, mock_redis_client):
        """Test POST /test/0/ with invalid zero requests."""
        response = client.post('/test/0/')
        
        assert response.status_code == 400
        data = json.loads(response.data)
        assert 'error' in data
        assert 'must be positive' in data['error']

    def test_test_endpoint_negative_requests(self, client, mock_redis_client):
        """Test POST /test/-5/ with invalid negative requests."""
        response = client.post('/test/-5/')
        
        # Flask route <int:num_requests> doesn't match negative numbers, returns 404
        assert response.status_code == 404

    def test_test_endpoint_non_integer(self, client, mock_redis_client):
        """Test POST /test/abc/ with non-integer parameter."""
        response = client.post('/test/abc/')
        
        # Flask <int:> route parameter rejects non-integers with 404
        assert response.status_code == 404

    def test_test_endpoint_large_number(self, client, mock_redis_client):
        """Test POST /test/1000000/ with very large request count."""
        mock_result = {'message': 'Test completed'}
        
        with patch('app.app.RequestClient') as mock_request_client_class:
            mock_client_instance = AsyncMock()
            mock_client_instance.execute_test.return_value = mock_result
            mock_request_client_class.return_value.__aenter__.return_value = mock_client_instance
            mock_request_client_class.return_value.__aexit__.return_value = None
            
            response = client.post('/test/1000000/')
            
            # Should accept large numbers (no upper limit per spec)
            assert response.status_code == 200

    def test_test_endpoint_wrong_method(self, client, mock_redis_client):
        """Test GET /test/10/ with wrong HTTP method."""
        response = client.get('/test/10/')
        
        # Should return 405 Method Not Allowed
        assert response.status_code == 405

    def test_test_endpoint_integration(self, client, mock_redis_client):
        """Test that test endpoint properly uses RequestClient."""
        with patch('app.app.RequestClient') as mock_request_client_class:
            mock_client_instance = AsyncMock()
            mock_client_instance.execute_test.return_value = {'result': 'success'}
            mock_request_client_class.return_value.__aenter__.return_value = mock_client_instance
            mock_request_client_class.return_value.__aexit__.return_value = None
            
            response = client.post('/test/5/')
            
            assert response.status_code == 200
            data = json.loads(response.data)
            assert data == {'result': 'success'}


class TestHealthEndpoint(TestFlaskApp):
    """Test the /health endpoint."""

    def test_health_check_success(self, client, mock_redis_client):
        """Test health check with working Redis connection."""
        mock_redis_client.client.ping.return_value = True
        
        response = client.get('/health')
        
        assert response.status_code == 200
        data = json.loads(response.data)
        assert data['status'] == 'healthy'
        assert data['redis'] == 'connected'
        assert 'timestamp' in data

    def test_health_check_redis_failure(self, client, mock_redis_client):
        """Test health check with Redis connection failure."""
        mock_redis_client.client.ping.side_effect = Exception("Redis connection failed")
        
        response = client.get('/health')
        
        assert response.status_code == 500
        data = json.loads(response.data)
        assert data['status'] == 'unhealthy'
        assert data['redis'] == 'disconnected'
        assert 'Redis connection failed' in data['error']
        assert 'timestamp' in data

    def test_health_check_content_type(self, client, mock_redis_client):
        """Test health check returns proper JSON content type."""
        response = client.get('/health')
        
        assert response.content_type == 'application/json'


class TestRouteValidation(TestFlaskApp):
    """Test route validation and edge cases."""

    def test_nonexistent_route(self, client):
        """Test request to nonexistent route returns 404."""
        response = client.get('/nonexistent')
        
        assert response.status_code == 404

    def test_api_route_without_trailing_slash_redirect(self, client, mock_redis_client):
        """Test that /api route without trailing slash works."""
        response = client.get('/api')
        
        # Flask should handle this gracefully
        assert response.status_code in [200, 301, 308]  # 200 or redirect

    def test_stats_route_wrong_method(self, client):
        """Test /stats/ with wrong HTTP method."""
        response = client.post('/stats/')
        
        assert response.status_code == 405  # Method Not Allowed

    def test_api_route_deep_nesting(self, client, mock_redis_client):
        """Test API route with deep path nesting."""
        deep_path = '/api/level1/level2/level3/level4/level5/'
        response = client.get(deep_path)
        
        assert response.status_code == 200
        mock_redis_client.increment_url_count.assert_called_once_with(deep_path, NAMESPACE)


if __name__ == '__main__':
    pytest.main([__file__])