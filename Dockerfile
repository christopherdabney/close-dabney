FROM python:3.9-slim

WORKDIR /app

# Copy requirements first for better Docker layer caching
COPY requirements.txt .

# Install Python dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY app/ ./app/

# Expose Flask port
EXPOSE 5000

# Run the application
CMD ["python", "-m", "app.app"]
