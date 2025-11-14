# Request Statistics Tracker

## SUMMARY

A Flask-based web application that tracks and counts HTTP requests by URL path, storing metrics in Redis for analysis. The system provides real-time request statistics and includes a test harness for generating synthetic traffic patterns.

**Key Features:**
- Real-time request counting for all `/api/*` endpoints
- JSON statistics API ordered by request frequency
- Synthetic traffic generator for load testing
- Docker containerization with Redis persistence
- Production-ready health monitoring

## ARCHITECTURE

The application follows a microservices architecture with clear separation of concerns:

```
┌─────────────────┐    ┌─────────────────┐
│   Flask App     │────│   Redis Store   │
│   (Port 5000)   │    │   (Port 6379)   │
└─────────────────┘    └─────────────────┘
```

**Components:**
- **Flask Application**: HTTP server handling API requests and statistics
- **Redis Client**: Atomic request counting with O(1) increment operations
- **Request Middleware**: Automatic URL path tracking for all incoming requests
- **Test Generator**: Synthetic traffic creation following specification constraints

**Data Model:**
- Redis keys: `url_count:/api/path/segment/`
- Atomic increments ensure thread-safe counting
- Statistics sorted by frequency for performance monitoring

## DEPENDENCIES

**Runtime Requirements:**
- Python 3.9+
- Flask 2.3.3
- Redis 5.0.1
- python-dotenv 1.0.0

**Infrastructure:**
- Docker & Docker Compose
- Redis 7 Alpine (containerized)

**Development Tools:**
- Make (for build automation)
- curl (for API testing)

## INSTALLATION

**Prerequisites:**
- Docker Desktop or compatible Docker environment
- Git for cloning the repository

**Setup:**
```bash
# Clone repository
git clone <repository-url>
cd request-stats-app

# Build and start services
docker-compose up --build
```

**Local Development (Optional):**
```bash
# Create virtual environment
make setup

# Install dependencies
pip install -r requirements.txt

# Start Redis locally
redis-server --daemonize yes

# Run Flask application
make run-local
```

## RUNNING INSTRUCTIONS

**Start the Application:**
```bash
docker-compose up --build
```

**Verify Health:**
```bash
curl http://localhost:5000/health
# Expected: {"status": "healthy", "redis": "connected", ...}
```

**Test API Endpoints:**
```bash
# Check initial statistics (empty)
curl http://localhost:5000/stats/

# Make API requests
curl http://localhost:5000/api/products/123/
curl http://localhost:5000/api/users/456/
curl http://localhost:5000/api/products/123/  # Duplicate for counting

# View updated statistics
curl http://localhost:5000/stats/
# Expected: [{"count": 2, "url": "/api/products/123/"}, ...]
```

**Generate Test Traffic:**
```bash
# Create 50 synthetic requests
curl -X POST http://localhost:5000/test/50/

# Verify synthetic traffic in statistics
curl http://localhost:5000/stats/
```

**Stop Services:**
```bash
docker-compose down
```

## NOTES ABOUT DOCKER LIMITATIONS

**macOS Compatibility:**
- Tested with Docker Desktop 4.37.1 on macOS Monterey 12.7.6
- Newer Docker versions require macOS Sonoma 14.0+
- Alternative: Use Colima for lightweight container management

**Performance Considerations:**
- Redis container uses persistent storage via Docker volumes
- Flask development mode enabled for debugging (disable in production)
- Container networking may add ~1-2ms latency vs localhost

**Resource Usage:**
- Redis container: ~10-20MB memory baseline
- Flask container: ~50-100MB memory depending on traffic
- Disk usage: <100MB for images and data

**Port Conflicts:**
- Ensure local Redis (port 6379) is stopped before running Docker stack
- Flask application exposed on port 5000 (configurable via docker-compose.yml)

## AUTHOR AND CONTACT INFORMATION

**Backend Developer Challenge Submission**
- **Position**: Senior Software Engineer - Backend/Python
- **Company**: Close
- **Submitted**: November 2025

**Technical Implementation:**
- Request counting with atomic Redis operations
- URL pattern matching using Flask route parameters
- Synthetic traffic generation with constrained randomization
- Production-ready error handling and health monitoring

**Self-Critique & Future Iterations:**
- Add comprehensive logging with structured output
- Implement rate limiting to prevent abuse of test endpoint
- Add database migration scripts for Redis schema changes
- Include Prometheus metrics export for production monitoring
- Add comprehensive unit and integration test suite
- Implement graceful shutdown handling for container orchestration