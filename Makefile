.PHONY: default build clean start stop logs test stats unit-test test-coverage tree

# Default target - build everything needed
default: build

# Build the project and install dependencies
build:
	docker-compose build
	python3 -m venv venv || true
	. venv/bin/activate && pip install -r requirements.txt

# Clean everything - Docker containers, volumes, virtual environment, cruft
clean:
	docker-compose down --volumes --remove-orphans
	docker system prune -f
	rm -rf venv/
	rm -rf __pycache__/ app/__pycache__/ tests/__pycache__/
	rm -rf *.pyc app/*.pyc tests/*.pyc
	rm -rf .pytest_cache/
	rm -rf htmlcov/
	rm -rf .coverage

# Start the application using Docker Compose
start:
	docker-compose up --build

# Stop the application
stop:
	docker-compose down

# View application logs
logs:
	docker-compose logs -f

# Run synthetic traffic test (use: make test NUM=50)
test:
	@NUM=${NUM:-10}; \
	echo "Running test with $NUM requests..."; \
	curl -X POST http://localhost:5000/test/$NUM/ || echo "Error: Make sure server is running (make start)"

# Display current statistics
stats:
	@echo "Current request statistics:"; \
	curl -s http://localhost:5000/stats/ | python3 -m json.tool || echo "Error: Make sure server is running (make start)"

# Run unit tests
unit-test:
	@echo "Running unit tests..."
	. venv/bin/activate && python3 -m pytest tests/ --tb=short

# Run a single test file (use: make unit-test-file FILE=test_redis_client.py)
unit-test-file:
	@echo "Running unit test file: $(FILE)..."
	. venv/bin/activate && python3 -m pytest tests/$(FILE) -v

# Run unit tests with coverage report
test-coverage:
	@echo "Running unit tests with coverage..."
	. venv/bin/activate && python3 -m pytest tests/ -v --cov=app --cov-report=html --cov-report=term-missing

# Show clean project structure
tree:
	tree -I 'node_modules|venv|__pycache__|*.pyc|*.db'