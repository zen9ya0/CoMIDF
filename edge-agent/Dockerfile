FROM python:3.11-slim

WORKDIR /app

# Install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application
COPY . .

# Create directories
RUN mkdir -p /var/lib/edge-agent /etc/agent

# Set environment variables
ENV PYTHONUNBUFFERED=1
ENV TZ=Asia/Taipei

# Expose local API port
EXPOSE 8600

# Run agent
CMD ["python", "cmd/agentd/main.py", "--config", "/etc/agent/agent.yaml"]

