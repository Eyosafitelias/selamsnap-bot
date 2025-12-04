# Dockerfile for SelamSnap Bot with pre-downloaded model
FROM python:3.11-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    wget \
    curl \
    gcc \
    g++ \
    && rm -rf /var/lib/apt/lists/* \
    && apt-get clean

# Download the u2netp model during build (smaller: 54MB)
RUN mkdir -p /root/.u2net \
    && echo "📥 Downloading u2netp model (smaller, 54MB)..." \
    && wget -q --show-progress --progress=bar:force \
       https://github.com/danielgatis/rembg/releases/download/v0.0.0/u2netp.onnx \
       -O /root/.u2net/u2netp.onnx \
    && echo "✅ Model downloaded successfully during build!"

# Copy requirements first for better caching
COPY requirements.txt .
RUN pip install --no-cache-dir --upgrade pip \
    && pip install --no-cache-dir -r requirements.txt

# Copy application files
COPY . .

# Create necessary directories
RUN mkdir -p templates temp

# Verify the model exists
RUN echo "🔍 Checking model file..." \
    && ls -lh /root/.u2net/ \
    && echo "📊 Model size: $(du -h /root/.u2net/u2netp.onnx | cut -f1)"

# Run the bot
CMD ["python", "koyeb_bot.py"]
