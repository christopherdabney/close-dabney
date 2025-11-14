.PHONY: default clean run stop logs test stats

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
	rm -rf __pycache__/ app/__pycache__/
	rm -rf *.pyc app/*.pyc

# Run the application using Docker Compose
run:
	docker-compose up --build

# Stop the application
stop:
	docker-compose down

# View application logs
logs:
	docker-compose logs -f

# Run synthetic traffic test (use: make test NUM=50)
test:
	@NUM=$${NUM:-10}; \
	echo "Running test with $$NUM requests..."; \
	curl -X POST http://localhost:5000/test/$$NUM/ || echo "Error: Make sure server is running (make run)"

# Display current statistics
stats:
	@echo "Current request statistics:"; \
	curl -s http://localhost:5000/stats/ | python3 -m json.tool || echo "Error: Make sure server is running (make run)"