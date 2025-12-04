# Dockerfile for SelamSnap Bot - Download ALL models
FROM python:3.11-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    wget \
    curl \
    && rm -rf /var/lib/apt/lists/* \
    && apt-get clean

# Create directory for ALL models
RUN mkdir -p /root/.u2net /root/.u2net_human_seg /root/.silueta

# Download ALL models during build
RUN echo "📥 Downloading ALL models during build..." && \
    # u2netp (small, 54MB)
    wget -q https://github.com/danielgatis/rembg/releases/download/v0.0.0/u2netp.onnx \
         -O /root/.u2net/u2netp.onnx && \
    echo "✅ u2netp downloaded" && \
    # u2net (large, 176MB) 
    wget -q https://github.com/danielgatis/rembg/releases/download/v0.0.0/u2net.onnx \
         -O /root/.u2net/u2net.onnx && \
    echo "✅ u2net downloaded" && \
    # u2net_human_seg
    wget -q https://github.com/danielgatis/rembg/releases/download/v0.0.0/u2net_human_seg.onnx \
         -O /root/.u2net_human_seg/u2net_human_seg.onnx && \
    echo "✅ u2net_human_seg downloaded" && \
    # silueta
    wget -q https://github.com/danielgatis/rembg/releases/download/v0.0.0/silueta.onnx \
         -O /root/.silueta/silueta.onnx && \
    echo "✅ silueta downloaded"

# Verify downloads
RUN echo "🔍 Checking downloaded models..." && \
    echo "u2netp: $(du -h /root/.u2net/u2netp.onnx | cut -f1)" && \
    echo "u2net: $(du -h /root/.u2net/u2net.onnx | cut -f1)" && \
    echo "Total models size: $(du -sh /root/.u2net /root/.u2net_human_seg /root/.silueta 2>/dev/null | tail -1 | cut -f1)"

# Copy requirements
COPY requirements.txt .
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

# Copy application
COPY . .
RUN mkdir -p templates temp

# Run the bot
CMD ["python", "koyeb_bot.py"]
