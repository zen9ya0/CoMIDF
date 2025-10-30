FROM python:3.11-slim

WORKDIR /app

# Install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application
COPY . .

# Set environment variables
ENV PYTHONUNBUFFERED=1
ENV TZ=UTC

# Expose ports
EXPOSE 8080 9090

# Run ingress service
CMD ["python", "-m", "flask", "--app", "services/ingress", "run", "--host=0.0.0.0", "--port=8080"]

