import unittest
from unittest.mock import Mock, patch, MagicMock
import sys
sys.path.append('app')

from app.circuit_breaker import CircuitBreaker
from app.redis_client import NAMESPACE_TEST


class TestCircuitBreaker(unittest.TestCase):
    
    def setUp(self):
        """Set up test fixtures before each test method."""
        with patch('app.circuit_breaker.RedisClient'):
            self.circuit_breaker = CircuitBreaker(failure_threshold=0.20, min_sample_size=10)
        self.mock_redis_client = Mock()
        self.circuit_breaker.redis_client = self.mock_redis_client
    
    def test_init_default_values(self):
        """Test CircuitBreaker initialization with default values."""
        with patch('app.circuit_breaker.RedisClient'):
            cb = CircuitBreaker()
        self.assertEqual(cb.failure_threshold, 0.20)
        self.assertEqual(cb.min_sample_size, 20)
        self.assertEqual(cb.successful_requests, 0)
        self.assertEqual(cb.failed_requests, 0)
        self.assertFalse(cb.is_open)
    
    def test_init_custom_values(self):
        """Test CircuitBreaker initialization with custom values."""
        with patch('app.circuit_breaker.RedisClient'):
            cb = CircuitBreaker(failure_threshold=0.15, min_sample_size=5)
        self.assertEqual(cb.failure_threshold, 0.15)
        self.assertEqual(cb.min_sample_size, 5)
    
    def test_record_success(self):
        """Test recording successful requests."""
        self.circuit_breaker.record_success()
        self.circuit_breaker.record_success()
        
        self.assertEqual(self.circuit_breaker.successful_requests, 2)
        self.assertEqual(self.circuit_breaker.failed_requests, 0)
    
    @patch('builtins.print')
    def test_record_failure_without_message(self, mock_print):
        """Test recording failed requests without error message."""
        self.circuit_breaker.record_failure()
        self.circuit_breaker.record_failure()
        
        self.assertEqual(self.circuit_breaker.successful_requests, 0)
        self.assertEqual(self.circuit_breaker.failed_requests, 2)
        mock_print.assert_not_called()
    
    @patch('builtins.print')
    def test_record_failure_with_message(self, mock_print):
        """Test recording failed requests with error message."""
        self.circuit_breaker.record_failure("Connection timeout")
        
        self.assertEqual(self.circuit_breaker.failed_requests, 1)
        mock_print.assert_called_once_with("Request failed: Connection timeout")
    
    def test_total_requests_property(self):
        """Test total_requests property calculation."""
        self.circuit_breaker.record_success()
        self.circuit_breaker.record_success()
        self.circuit_breaker.record_failure()
        
        self.assertEqual(self.circuit_breaker.total_requests, 3)
    
    def test_failure_rate_property_with_requests(self):
        """Test failure_rate property calculation with requests."""
        self.circuit_breaker.record_success()
        self.circuit_breaker.record_failure()
        self.circuit_breaker.record_failure()
        
        self.assertEqual(self.circuit_breaker.failure_rate, 2/3)
    
    def test_failure_rate_property_no_requests(self):
        """Test failure_rate property with no requests."""
        self.assertEqual(self.circuit_breaker.failure_rate, 0.0)
    
    def test_completion_rate_property_with_requests(self):
        """Test completion_rate property calculation with requests."""
        self.circuit_breaker.record_success()
        self.circuit_breaker.record_success()
        self.circuit_breaker.record_failure()
        
        self.assertEqual(self.circuit_breaker.completion_rate, 2/3)
    
    def test_completion_rate_property_no_requests(self):
        """Test completion_rate property with no requests."""
        self.assertEqual(self.circuit_breaker.completion_rate, 0.0)
    
    def test_should_trip_below_min_sample_size(self):
        """Test circuit breaker doesn't trip below minimum sample size."""
        # Add failures that would exceed threshold, but below min sample
        for _ in range(5):
            self.circuit_breaker.record_failure()
        
        self.assertFalse(self.circuit_breaker.should_trip())
        self.assertFalse(self.circuit_breaker.is_open)
    
    def test_should_trip_below_threshold(self):
        """Test circuit breaker doesn't trip below failure threshold."""
        # Add requests with 10% failure rate (below 20% threshold)
        for _ in range(9):
            self.circuit_breaker.record_success()
        self.circuit_breaker.record_failure()
        
        self.assertFalse(self.circuit_breaker.should_trip())
        self.assertFalse(self.circuit_breaker.is_open)
    
    @patch('builtins.print')
    def test_should_trip_above_threshold(self, mock_print):
        """Test circuit breaker trips above failure threshold."""
        self.mock_redis_client.clear_namespace.return_value = 5
        
        # Add requests with 30% failure rate (above 20% threshold)
        for _ in range(7):
            self.circuit_breaker.record_success()
        for _ in range(3):
            self.circuit_breaker.record_failure()
        
        self.assertTrue(self.circuit_breaker.should_trip())
        self.assertTrue(self.circuit_breaker.is_open)
        
        # Check that warning message was printed
        mock_print.assert_any_call(
            "Circuit breaker triggered: 30.00% failure rate exceeds 20.00% threshold"
        )
        
        # Check that Redis cleanup was called
        self.mock_redis_client.clear_namespace.assert_called_once_with(NAMESPACE_TEST)
        mock_print.assert_any_call(
            "Cleared 5 test keys due to circuit breaker activation"
        )
    
    @patch('builtins.print')
    def test_should_trip_only_trips_once(self, mock_print):
        """Test circuit breaker only trips once and doesn't repeat actions."""
        self.mock_redis_client.clear_namespace.return_value = 3
        
        # Add requests with high failure rate
        for _ in range(7):
            self.circuit_breaker.record_success()
        for _ in range(3):
            self.circuit_breaker.record_failure()
        
        # First call should trip
        self.assertTrue(self.circuit_breaker.should_trip())
        self.assertTrue(self.circuit_breaker.is_open)
        
        # Reset mocks to verify second call doesn't repeat actions
        mock_print.reset_mock()
        self.mock_redis_client.reset_mock()
        
        # Second call should still return True but not repeat actions
        self.assertTrue(self.circuit_breaker.should_trip())
        mock_print.assert_not_called()
        self.mock_redis_client.clear_namespace.assert_not_called()
    
    @patch('builtins.print')
    def test_clear_invalid_test_data_redis_error(self, mock_print):
        """Test Redis cleanup error handling in circuit breaker."""
        self.mock_redis_client.clear_namespace.side_effect = Exception("Redis down")
        
        # Trigger circuit breaker
        for _ in range(7):
            self.circuit_breaker.record_success()
        for _ in range(3):
            self.circuit_breaker.record_failure()
        
        self.circuit_breaker.should_trip()
        
        # Verify error was logged
        mock_print.assert_any_call(
            "Warning: Failed to clear test data: Redis down"
        )
    
    def test_get_stats_basic(self):
        """Test get_stats with basic data."""
        self.circuit_breaker.record_success()
        self.circuit_breaker.record_failure()
        
        stats = self.circuit_breaker.get_stats(
            total_requested=10,
            total_cancelled=8,
            random_strings=['abc', 'def', 'ghi']
        )
        
        expected = {
            "successful_requests": 1,
            "failed_requests": 1,
            "total_completed": 2,
            "total_cancelled": 8,
            "completion_rate": 0.5,
            "failure_rate": 0.5,
            "circuit_breaker_triggered": False,
            "message": "Generated 10 fake requests",
            "random_strings_used": ['abc', 'def', 'ghi']
        }
        self.assertEqual(stats, expected)
    
    def test_get_stats_circuit_breaker_open(self):
        """Test get_stats when circuit breaker is open."""
        self.circuit_breaker.is_open = True
        
        stats = self.circuit_breaker.get_stats(total_requested=100)
        
        self.assertTrue(stats["circuit_breaker_triggered"])
        self.assertIn("stopped by circuit breaker", stats["message"])
    
    def test_get_stats_without_random_strings(self):
        """Test get_stats without random strings parameter."""
        stats = self.circuit_breaker.get_stats(total_requested=5)
        
        self.assertNotIn("random_strings_used", stats)
    
    def test_get_stats_no_total_requested(self):
        """Test get_stats without total_requested parameter."""
        self.circuit_breaker.record_success()
        
        stats = self.circuit_breaker.get_stats()
        
        self.assertEqual(stats["message"], "Completed 1 requests")
    
    def test_reset(self):
        """Test circuit breaker reset functionality."""
        # Set up some state
        self.circuit_breaker.record_success()
        self.circuit_breaker.record_failure()
        self.circuit_breaker.is_open = True
        
        # Reset and verify
        self.circuit_breaker.reset()
        
        self.assertEqual(self.circuit_breaker.successful_requests, 0)
        self.assertEqual(self.circuit_breaker.failed_requests, 0)
        self.assertFalse(self.circuit_breaker.is_open)


if __name__ == '__main__':
    unittest.main()