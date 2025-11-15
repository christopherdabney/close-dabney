"""
Input validation utilities for API endpoints.

Provides security validation for user-supplied path parameters
to prevent injection attacks, path traversal, and malformed input.
"""

import re


def validate_api_path(path):
    """
    Validate API path for security and sanity.
    
    Args:
        path: URL path component to validate
        
    Returns:
        tuple: (is_valid: bool, error_message: str|None)
        
    Security Features:
        - Prevents directory traversal attacks (..)
        - Blocks control characters and null bytes
        - Limits path length to prevent memory exhaustion
        - Restricts to safe character set for API patterns
        - Prevents excessive nesting depth
    """
    if not path:
        return True, None
    
    # Length check - prevent memory exhaustion
    if len(path) > 1000:
        return False, "Path too long (max 1000 characters)"
    
    # Directory traversal prevention
    if '..' in path:
        return False, "Path traversal not allowed"
    
    # Check for null bytes and other control characters
    if any(ord(c) < 32 for c in path if c != '/'):
        return False, "Invalid characters in path"
    
    # Allow only safe characters: alphanumeric, hyphens, underscores, slashes, dots, periods
    # This covers realistic API patterns like /users/123/posts/abc-def/
    safe_pattern = re.compile(r'^[a-zA-Z0-9/_.-]+$')
    if not safe_pattern.match(path):
        return False, "Path contains invalid characters"
    
    # Prevent excessive nesting (more than 20 segments)
    segments = [seg for seg in path.split('/') if seg]  # Remove empty segments
    if len(segments) > 20:
        return False, "Path too deeply nested (max 20 segments)"
    
    # Prevent very long individual segments
    if any(len(segment) > 100 for segment in segments):
        return False, "Path segment too long (max 100 characters per segment)"
    
    return True, None


def validate_pagination_params(page, page_size):
    """
    Validate pagination parameters for stats endpoints.
    
    Args:
        page: Page number (should be non-negative integer)
        page_size: Results per page (should be positive, max 1000)
        
    Returns:
        tuple: (is_valid: bool, error_message: str|None)
    """
    if page < 0:
        return False, "Page number must be non-negative"
        
    if page_size < 1:
        return False, "Page size must be positive"
        
    if page_size > 1000:
        return False, "Page size cannot exceed 1000"
        
    return True, None


def validate_test_request_count(num_requests):
    """
    Validate number of test requests parameter.
    
    Args:
        num_requests: Number of requests to generate
        
    Returns:
        tuple: (is_valid: bool, error_message: str|None)
    """
    if num_requests <= 0:
        return False, "Number of requests must be positive"
        
    # Optional: Add upper limit for resource protection
    # if num_requests > 1000000:
    #     return False, "Number of requests too large (max 1,000,000)"
        
    return True, None
