import unittest
from unittest.mock import Mock, patch, AsyncMock
import json
import sys
sys.path.append('app')

from app.app import app
from app.redis_client import RedisOperationError, NAMESPACE, NAMESPACE_TEST


class TestFlaskApp(unittest.TestCase):
    
    def setUp(self):
        """Set up test fixtures before each test method."""
        app.config['TESTING'] = True
        self.client = app.test_client()
        self.app_context = app.app_context()
        self.app_context.push()
    
    def tearDown(self):
        """Clean up after each test method."""
        self.app_context.pop()
    
    @patch('app.app.redis_client')
    def test_api_endpoints_default_path(self, mock_redis_client):
        """Test /api/ endpoint with default empty path."""
        mock_redis_client.increment_url_count.return_value = 1
        
        response = self.client.get('/api/')
        
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data, b'')
        mock_redis_client.increment_url_count.assert_called_once_with('/api/', NAMESPACE)
    
    @patch('app.app.redis_client')
    def test_api_endpoints_with_path(self, mock_redis_client):
        """Test /api/* endpoint with specific path."""
        mock_redis_client.increment_url_count.return_value = 2
        
        response = self.client.get('/api/users/123')
        
        self.assertEqual(response.status_code, 200)
        mock_redis_client.increment_url_count.assert_called_once_with('/api/users/123/', NAMESPACE)
    
    @patch('app.app.redis_client')
    def test_api_endpoints_path_normalization(self, mock_redis_client):
        """Test that paths are normalized with trailing slash."""
        mock_redis_client.increment_url_count.return_value = 1
        
        # Path without trailing slash should be normalized
        response = self.client.get('/api/products/456')
        
        self.assertEqual(response.status_code, 200)
        mock_redis_client.increment_url_count.assert_called_once_with('/api/products/456/', NAMESPACE)
    
    @patch('app.app.redis_client')
    def test_api_endpoints_with_test_header(self, mock_redis_client):
        """Test /api/* endpoint with X-Request-Source header for test traffic."""
        mock_redis_client.increment_url_count.return_value = 3
        
        response = self.client.get('/api/test/', headers={'X-Request-Source': NAMESPACE_TEST})
        
        self.assertEqual(response.status_code, 200)
        mock_redis_client.increment_url_count.assert_called_once_with('/api/test/', NAMESPACE_TEST)
    
    @patch('app.app.redis_client')
    def test_api_endpoints_redis_error_real_traffic(self, mock_redis_client):
        """Test /api/* endpoint handles Redis errors gracefully for real traffic."""
        mock_redis_client.increment_url_count.side_effect = RedisOperationError("Redis down")
        
        response = self.client.get('/api/users/789/')
        
        # Should still return 200 for real traffic even when Redis fails
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data, b'')
    
    @patch('app.app.redis_client')
    def test_api_endpoints_redis_error_test_traffic(self, mock_redis_client):
        """Test /api/* endpoint returns 500 for test traffic when Redis fails."""
        mock_redis_client.increment_url_count.side_effect = RedisOperationError("Redis down")
        
        response = self.client.get('/api/test/', headers={'X-Request-Source': NAMESPACE_TEST})
        
        # Should return 500 for test traffic when Redis fails
        self.assertEqual(response.status_code, 500)
        response_data = json.loads(response.data)
        self.assertEqual(response_data['error'], 'Redis counting failed during test')
    
    @patch('app.app.redis_client')
    def test_get_stats_success(self, mock_redis_client):
        """Test /stats/ endpoint returns statistics successfully."""
        mock_stats = [
            {'url': '/api/users/', 'count': 10},
            {'url': '/api/products/', 'count': 5}
        ]
        mock_redis_client.get_url_stats.return_value = mock_stats
        
        response = self.client.get('/stats/')
        
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.content_type, 'application/json')
        
        response_data = json.loads(response.data)
        self.assertEqual(response_data, mock_stats)
        mock_redis_client.get_url_stats.assert_called_once_with(namespace=NAMESPACE_TEST)
    
    @patch('app.app.redis_client')
    def test_get_stats_empty(self, mock_redis_client):
        """Test /stats/ endpoint with no statistics."""
        mock_redis_client.get_url_stats.return_value = []
        
        response = self.client.get('/stats/')
        
        self.assertEqual(response.status_code, 200)
        response_data = json.loads(response.data)
        self.assertEqual(response_data, [])
    
    @patch('app.app.make_concurrent_requests')
    @patch('app.app.redis_client')
    def test_test_endpoint_success(self, mock_redis_client, mock_make_requests):
        """Test /test/<num>/ endpoint executes successfully."""
        mock_redis_client.clear_namespace.return_value = 3
        mock_make_requests.return_value = {
            'message': 'Generated 10 fake requests',
            'successful_requests': 8,
            'failed_requests': 2
        }
        
        response = self.client.post('/test/10/')
        
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.content_type, 'application/json')
        
        # Verify Redis namespace was cleared
        mock_redis_client.clear_namespace.assert_called_once_with(NAMESPACE_TEST)
        
        # Verify concurrent requests were made
        mock_make_requests.assert_called_once_with(10)
        
        # Check response content
        response_data = json.loads(response.data)
        self.assertEqual(response_data['message'], 'Generated 10 fake requests')
        self.assertEqual(response_data['successful_requests'], 8)
        self.assertEqual(response_data['failed_requests'], 2)
    
    def test_test_endpoint_invalid_number_zero(self):
        """Test /test/<num>/ endpoint rejects zero requests."""
        response = self.client.post('/test/0/')
        
        self.assertEqual(response.status_code, 400)
        response_data = json.loads(response.data)
        self.assertEqual(response_data['error'], 'Number of requests must be positive')
    
    def test_test_endpoint_invalid_number_negative(self):
        """Test /test/<num>/ endpoint rejects negative requests."""
        # Flask <int:num> route converter returns 404 for negative numbers
        # This is expected behavior since negative numbers don't match int converter
        response = self.client.post('/test/-5/')
        
        self.assertEqual(response.status_code, 404)  # Flask returns 404 for route mismatch
    
    @patch('app.app.make_concurrent_requests')
    @patch('app.app.redis_client')
    def test_test_endpoint_valid_large_number(self, mock_redis_client, mock_make_requests):
        """Test /test/<num>/ endpoint accepts large numbers."""
        mock_redis_client.clear_namespace.return_value = 0
        mock_make_requests.return_value = {'message': 'Generated 10000 fake requests'}
        
        response = self.client.post('/test/10000/')
        
        self.assertEqual(response.status_code, 200)
        mock_make_requests.assert_called_once_with(10000)
    
    @patch('app.app.redis_client')
    def test_health_check_success(self, mock_redis_client):
        """Test /health endpoint when Redis is healthy."""
        mock_redis_client.client.ping.return_value = True
        
        response = self.client.get('/health')
        
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.content_type, 'application/json')
        
        response_data = json.loads(response.data)
        self.assertEqual(response_data['status'], 'healthy')
        self.assertEqual(response_data['redis'], 'connected')
        self.assertIn('timestamp', response_data)
        
        mock_redis_client.client.ping.assert_called_once()
    
    @patch('app.app.redis_client')
    def test_health_check_redis_failure(self, mock_redis_client):
        """Test /health endpoint when Redis is unhealthy."""
        mock_redis_client.client.ping.side_effect = Exception("Redis connection failed")
        
        response = self.client.get('/health')
        
        self.assertEqual(response.status_code, 500)
        self.assertEqual(response.content_type, 'application/json')
        
        response_data = json.loads(response.data)
        self.assertEqual(response_data['status'], 'unhealthy')
        self.assertEqual(response_data['redis'], 'disconnected')
        self.assertIn('error', response_data)
        self.assertIn('timestamp', response_data)
        self.assertEqual(response_data['error'], 'Redis connection failed')
    
    @patch('app.app.redis_client')
    def test_api_endpoints_various_http_methods(self, mock_redis_client):
        """Test that /api/* only responds to GET requests."""
        # GET should work
        response = self.client.get('/api/test/')
        self.assertEqual(response.status_code, 200)
        
        # Other methods should return 405 Method Not Allowed
        response = self.client.post('/api/test/')
        self.assertEqual(response.status_code, 405)
        
        response = self.client.put('/api/test/')
        self.assertEqual(response.status_code, 405)
        
        response = self.client.delete('/api/test/')
        self.assertEqual(response.status_code, 405)
    
    @patch('app.app.make_concurrent_requests')
    @patch('app.app.redis_client')
    def test_test_endpoint_only_post(self, mock_redis_client, mock_make_requests):
        """Test that /test/<num>/ only responds to POST requests."""
        mock_redis_client.clear_namespace.return_value = 0
        mock_make_requests.return_value = {'message': 'test'}
        
        # POST should work
        response = self.client.post('/test/5/')
        self.assertIn(response.status_code, [200, 400])  # Either success or validation error
        
        # Other methods should return 405 Method Not Allowed
        response = self.client.get('/test/5/')
        self.assertEqual(response.status_code, 405)
        
        response = self.client.put('/test/5/')
        self.assertEqual(response.status_code, 405)
        
        response = self.client.delete('/test/5/')
        self.assertEqual(response.status_code, 405)
    
    @patch('app.app.redis_client')
    def test_stats_endpoint_only_get(self, mock_redis_client):
        """Test that /stats/ only responds to GET requests."""
        mock_redis_client.get_url_stats.return_value = []
        
        # GET should work
        response = self.client.get('/stats/')
        self.assertEqual(response.status_code, 200)
        
        # Other methods should return 405 Method Not Allowed
        response = self.client.post('/stats/')
        self.assertEqual(response.status_code, 405)
        
        response = self.client.put('/stats/')
        self.assertEqual(response.status_code, 405)
        
        response = self.client.delete('/stats/')
        self.assertEqual(response.status_code, 405)
    
    @patch('app.app.make_concurrent_requests')
    @patch('app.app.redis_client')
    def test_test_endpoint_integration(self, mock_redis_client, mock_make_requests):
        """Test that /test/ endpoint properly integrates with request generation."""
        mock_redis_client.clear_namespace.return_value = 0
        
        # Mock a comprehensive result that would come from make_concurrent_requests
        mock_result = {
            'message': 'Generated 25 fake requests',
            'successful_requests': 20,
            'failed_requests': 5,
            'completion_rate': 0.8,
            'circuit_breaker_triggered': False,
            'random_strings_used': ['abc', 'def', 'ghi']
        }
        mock_make_requests.return_value = mock_result
        
        response = self.client.post('/test/25/')
        
        self.assertEqual(response.status_code, 200)
        response_data = json.loads(response.data)
        
        # Verify all expected fields are present
        self.assertEqual(response_data['message'], 'Generated 25 fake requests')
        self.assertEqual(response_data['successful_requests'], 20)
        self.assertEqual(response_data['failed_requests'], 5)
        self.assertEqual(response_data['completion_rate'], 0.8)
        self.assertEqual(response_data['circuit_breaker_triggered'], False)
        self.assertEqual(response_data['random_strings_used'], ['abc', 'def', 'ghi'])


if __name__ == '__main__':
    unittest.main()