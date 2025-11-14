import unittest
from unittest.mock import patch
import string
import sys
sys.path.append('app')

from app.paths import generate_random_url_path, generate_segment


class TestPaths(unittest.TestCase):
    
    def test_generate_segment_length_one(self):
        """Test generating segment of length 1."""
        with patch('random.choice') as mock_choice:
            mock_choice.return_value = 'a'
            result = generate_segment(1)
            self.assertEqual(result, 'a')
            # Should only call random.choice once for single character
            self.assertEqual(mock_choice.call_count, 1)
    
    def test_generate_segment_length_two(self):
        """Test generating segment of length 2."""
        with patch('random.choice') as mock_choice:
            mock_choice.side_effect = ['a', 'z']
            result = generate_segment(2)
            self.assertEqual(result, 'az')
            # Should call random.choice twice (first and last char)
            self.assertEqual(mock_choice.call_count, 2)
    
    def test_generate_segment_length_five(self):
        """Test generating segment of length 5."""
        with patch('random.choice') as mock_choice, \
             patch('random.choices') as mock_choices:
            mock_choice.side_effect = ['a', 'z']  # first and last
            mock_choices.return_value = ['b', 'c', 'd']  # middle chars
            
            result = generate_segment(5)
            self.assertEqual(result, 'abcdz')
            
            # Verify first and last are safe chars only
            safe_chars = string.ascii_letters + string.digits
            first_call_args = mock_choice.call_args_list[0][0][0]
            last_call_args = mock_choice.call_args_list[1][0][0]
            self.assertEqual(first_call_args, safe_chars)
            self.assertEqual(last_call_args, safe_chars)
            
            # Verify middle chars function was called
            mock_choices.assert_called_once()
            # Verify it was called with the expanded character set and correct count
            call_args, call_kwargs = mock_choices.call_args
            all_chars = safe_chars + '-_.'
            self.assertEqual(call_args[0], all_chars)
            self.assertEqual(call_kwargs['k'], 3)  # length-2 = 3
    
    def test_generate_segment_character_sets(self):
        """Test that generate_segment uses correct character sets."""
        # Generate many segments to test character distribution
        for _ in range(100):
            segment = generate_segment(5)
            
            # First and last chars should be alphanumeric
            self.assertTrue(segment[0].isalnum(), f"First char '{segment[0]}' not alphanumeric")
            self.assertTrue(segment[-1].isalnum(), f"Last char '{segment[-1]}' not alphanumeric")
            
            # Middle chars can include special characters
            valid_chars = string.ascii_letters + string.digits + '-_.'
            for char in segment[1:-1]:
                self.assertIn(char, valid_chars, f"Middle char '{char}' not in valid set")
    
    def test_generate_random_url_path_structure(self):
        """Test basic structure of generated URL paths."""
        random_strings = ['abc', 'def', 'ghi']
        
        for _ in range(100):
            path = generate_random_url_path(random_strings)
            
            # Should start with /api/ and end with /
            self.assertTrue(path.startswith('/api/'), f"Path '{path}' doesn't start with /api/")
            self.assertTrue(path.endswith('/'), f"Path '{path}' doesn't end with /")
            
            # Should have reasonable structure
            segments = path[5:-1].split('/')  # Remove /api/ prefix and / suffix
            self.assertGreaterEqual(len(segments), 1, f"Path '{path}' has no segments")
            self.assertLessEqual(len(segments), 6, f"Path '{path}' has too many segments")
    
    @patch('random.randint')
    @patch('random.choice')
    def test_generate_random_url_path_one_segment(self, mock_choice, mock_randint):
        """Test URL generation with exactly 1 segment."""
        mock_randint.return_value = 1
        mock_choice.return_value = 'test'
        
        random_strings = ['test', 'demo', 'example']
        result = generate_random_url_path(random_strings)
        
        self.assertEqual(result, '/api/test/')
        mock_randint.assert_called_once_with(1, 6)
        mock_choice.assert_called_once_with(random_strings)
    
    @patch('random.randint')
    @patch('random.choice')
    def test_generate_random_url_path_six_segments(self, mock_choice, mock_randint):
        """Test URL generation with exactly 6 segments."""
        mock_randint.return_value = 6
        mock_choice.side_effect = ['a', 'b', 'c', 'a', 'b', 'c']
        
        random_strings = ['a', 'b', 'c']
        result = generate_random_url_path(random_strings)
        
        self.assertEqual(result, '/api/a/b/c/a/b/c/')
        mock_randint.assert_called_once_with(1, 6)
        self.assertEqual(mock_choice.call_count, 6)
    
    def test_generate_random_url_path_uses_only_provided_strings(self):
        """Test that URL generation only uses the provided random strings."""
        random_strings = ['unique1', 'unique2', 'unique3']
        
        for _ in range(50):
            path = generate_random_url_path(random_strings)
            
            # Extract segments from path
            segments = path[5:-1].split('/')  # Remove /api/ prefix and / suffix
            
            # All segments should be from our provided strings
            for segment in segments:
                self.assertIn(segment, random_strings, 
                             f"Segment '{segment}' not in provided strings {random_strings}")
    
    def test_generate_random_url_path_segment_count_distribution(self):
        """Test that segment count follows expected distribution."""
        random_strings = ['a', 'b', 'c']
        segment_counts = {}
        
        # Generate many paths and count segment distributions
        for _ in range(1000):
            path = generate_random_url_path(random_strings)
            segments = path[5:-1].split('/')  # Remove /api/ prefix and / suffix
            count = len(segments)
            segment_counts[count] = segment_counts.get(count, 0) + 1
        
        # Should have generated paths with 1-6 segments
        for i in range(1, 7):
            self.assertIn(i, segment_counts, f"No paths generated with {i} segments")
            self.assertGreater(segment_counts[i], 0, f"No paths with {i} segments")
        
        # Should not have paths with 0 or >6 segments
        for invalid_count in [0, 7, 8, 9, 10]:
            self.assertNotIn(invalid_count, segment_counts, 
                           f"Invalid segment count {invalid_count} found")
    
    def test_generate_random_url_path_empty_random_strings(self):
        """Test behavior with empty random strings list."""
        # This should raise an IndexError when random.choice is called
        with self.assertRaises(IndexError):
            generate_random_url_path([])
    
    def test_generate_random_url_path_single_random_string(self):
        """Test URL generation with only one random string."""
        random_strings = ['only']
        
        for _ in range(20):
            path = generate_random_url_path(random_strings)
            
            # All segments should be 'only'
            segments = path[5:-1].split('/')
            for segment in segments:
                self.assertEqual(segment, 'only')
    
    def test_integration_generate_segment_in_url_path(self):
        """Integration test: segments generated should be valid URI components."""
        for length in range(1, 13):
            segment = generate_segment(length)
            
            # Test that segment works in URL path
            path = f"/api/{segment}/"
            self.assertTrue(path.startswith('/api/'))
            self.assertTrue(path.endswith('/'))
            
            # Segment should not contain problematic characters for URLs
            problematic_chars = ' \t\n\r/?#[]@!$&\'()*+,;='
            for char in problematic_chars:
                self.assertNotIn(char, segment, 
                               f"Segment '{segment}' contains problematic char '{char}'")


if __name__ == '__main__':
    unittest.main()