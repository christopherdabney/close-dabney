import random
import string

def generate_random_url_path(random_strings):
    """
    Generate a random URL path using the provided random strings.
    Returns a path like '/api/string1/string2/string3/'
    """
    # Random number of path segments (1-6)
    num_segments = random.randint(1, 6)
    
    # Build path using random strings
    segments = [random.choice(random_strings) for _ in range(num_segments)]
    return "/api/" + "/".join(segments) + "/"

def generate_segment(length):
    """
    Generate a realistic URI path segment.
    Ensures segments don't start or end with special characters.
    """
    # First and last chars: letters/digits only
    safe_chars = string.ascii_letters + string.digits
    # Middle chars: include hyphens, underscores, periods
    all_chars = safe_chars + '-_.'
    
    if length == 1:
        return random.choice(safe_chars)
    else:
        first = random.choice(safe_chars)
        middle = ''.join(random.choices(all_chars, k=length-2)) if length > 2 else ''
        last = random.choice(safe_chars)
        return first + middle + last
