import unittest
from unittest.mock import Mock, patch, MagicMock
import redis
import os
import sys
sys.path.append('app')

from app.redis_client import RedisClient, RedisOperationError, NAMESPACE, NAMESPACE_TEST


class TestRedisClient(unittest.TestCase):
    
    def setUp(self):
        """Set up test fixtures before each test method."""
        with patch('redis.Redis'):
            self.client = RedisClient()
        self.mock_redis = Mock()
        self.client.client = self.mock_redis
    
    @patch.dict(os.environ, {'REDIS_HOST': 'test-host', 'REDIS_PORT': '1234'})
    @patch('redis.Redis')
    def test_init_with_environment_variables(self, mock_redis_class):
        """Test RedisClient initialization with environment variables."""
        RedisClient()
        mock_redis_class.assert_called_once_with(
            host='test-host',
            port=1234,
            decode_responses=True
        )
    
    @patch.dict(os.environ, {}, clear=True)
    @patch('redis.Redis')
    def test_init_with_defaults(self, mock_redis_class):
        """Test RedisClient initialization with default values."""
        RedisClient()
        mock_redis_class.assert_called_once_with(
            host='localhost',
            port=6379,
            decode_responses=True
        )
    
    def test_increment_url_count_success(self):
        """Test successful URL count increment."""
        self.mock_redis.incr.return_value = 5
        
        result = self.client.increment_url_count('/api/test/', NAMESPACE)
        
        self.mock_redis.incr.assert_called_once_with('url_count:/api/test/')
        self.assertEqual(result, 5)
    
    def test_increment_url_count_with_custom_namespace(self):
        """Test URL count increment with custom namespace."""
        self.mock_redis.incr.return_value = 3
        
        result = self.client.increment_url_count('/api/test/', NAMESPACE_TEST)
        
        self.mock_redis.incr.assert_called_once_with('test:/api/test/')
        self.assertEqual(result, 3)
    
    @patch('builtins.print')
    def test_increment_url_count_connection_error(self, mock_print):
        """Test URL count increment with Redis connection error."""
        self.mock_redis.incr.side_effect = redis.ConnectionError("Connection failed")
        
        with self.assertRaises(RedisOperationError) as context:
            self.client.increment_url_count('/api/test/')
        
        self.assertIn("Failed to increment count", str(context.exception))
        mock_print.assert_called_once()
        self.assertIn("Warning: Redis operation failed", mock_print.call_args[0][0])
    
    @patch('builtins.print')
    def test_increment_url_count_timeout_error(self, mock_print):
        """Test URL count increment with Redis timeout error."""
        self.mock_redis.incr.side_effect = redis.TimeoutError("Timeout")
        
        with self.assertRaises(RedisOperationError):
            self.client.increment_url_count('/api/test/')
        
        mock_print.assert_called_once()
    
    @patch('builtins.print')
    def test_increment_url_count_redis_error(self, mock_print):
        """Test URL count increment with generic Redis error."""
        self.mock_redis.incr.side_effect = redis.RedisError("Generic error")
        
        with self.assertRaises(RedisOperationError):
            self.client.increment_url_count('/api/test/')
        
        mock_print.assert_called_once()
    
    @patch('builtins.print')
    def test_increment_url_count_unexpected_error(self, mock_print):
        """Test URL count increment with unexpected error."""
        self.mock_redis.incr.side_effect = ValueError("Unexpected error")
        
        with self.assertRaises(ValueError):
            self.client.increment_url_count('/api/test/')
        
        mock_print.assert_called_once()
        self.assertIn("Error: Unexpected error", mock_print.call_args[0][0])
    
    def test_clear_namespace_success_with_keys(self):
        """Test successful namespace clearing with existing keys."""
        self.mock_redis.keys.return_value = ['url_count:/api/test1/', 'url_count:/api/test2/']
        self.mock_redis.delete.return_value = 2
        
        result = self.client.clear_namespace(NAMESPACE)
        
        self.mock_redis.keys.assert_called_once_with('url_count:*')
        self.mock_redis.delete.assert_called_once_with('url_count:/api/test1/', 'url_count:/api/test2/')
        self.assertEqual(result, 2)
    
    def test_clear_namespace_success_no_keys(self):
        """Test successful namespace clearing with no existing keys."""
        self.mock_redis.keys.return_value = []
        
        result = self.client.clear_namespace(NAMESPACE)
        
        self.mock_redis.keys.assert_called_once_with('url_count:*')
        self.mock_redis.delete.assert_not_called()
        self.assertEqual(result, 0)
    
    @patch('builtins.print')
    def test_clear_namespace_redis_error(self, mock_print):
        """Test namespace clearing with Redis error."""
        self.mock_redis.keys.side_effect = redis.ConnectionError("Connection failed")
        
        with self.assertRaises(RedisOperationError):
            self.client.clear_namespace(NAMESPACE)
        
        mock_print.assert_called_once()
    
    def test_get_url_stats_success(self):
        """Test successful URL stats retrieval."""
        self.mock_redis.keys.return_value = ['url_count:/api/test1/', 'url_count:/api/test2/']
        self.mock_redis.get.side_effect = ['5', '3']
        
        result = self.client.get_url_stats(NAMESPACE)
        
        expected = [
            {'url': '/api/test1/', 'count': 5},
            {'url': '/api/test2/', 'count': 3}
        ]
        self.assertEqual(result, expected)
        self.mock_redis.keys.assert_called_once_with('url_count:*')
    
    def test_get_url_stats_empty(self):
        """Test URL stats retrieval with no keys."""
        self.mock_redis.keys.return_value = []
        
        result = self.client.get_url_stats(NAMESPACE)
        
        self.assertEqual(result, [])
    
    def test_get_url_stats_sorted_by_count(self):
        """Test URL stats are properly sorted by count (descending)."""
        self.mock_redis.keys.return_value = ['url_count:/api/low/', 'url_count:/api/high/', 'url_count:/api/mid/']
        self.mock_redis.get.side_effect = ['2', '10', '5']
        
        result = self.client.get_url_stats(NAMESPACE)
        
        expected = [
            {'url': '/api/high/', 'count': 10},
            {'url': '/api/mid/', 'count': 5},
            {'url': '/api/low/', 'count': 2}
        ]
        self.assertEqual(result, expected)
    
    @patch('builtins.print')
    def test_get_url_stats_redis_error(self, mock_print):
        """Test URL stats retrieval with Redis error."""
        self.mock_redis.keys.side_effect = redis.ConnectionError("Connection failed")
        
        with self.assertRaises(RedisOperationError):
            self.client.get_url_stats(NAMESPACE)
        
        mock_print.assert_called_once()


if __name__ == '__main__':
    unittest.main()