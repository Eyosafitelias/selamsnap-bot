# Dockerfile for SelamSnap Bot with Remove.bg API
FROM python:3.11-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    wget \
    curl \
    && rm -rf /var/lib/apt/lists/* \
    && apt-get clean

# Create necessary directories
RUN mkdir -p templates temp

# Copy requirements
COPY requirements.txt .
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

# Copy application
COPY . .

# Set environment variables to prevent Python from downloading models
ENV U2NET_HOME=/tmp
ENV U2NETP_HOME=/tmp
ENV IS_DOCKER=true

# Run the bot
CMD ["python", "main.py"]
