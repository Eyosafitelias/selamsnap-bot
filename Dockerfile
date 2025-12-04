# Dockerfile for SelamSnap Bot with all dependencies
FROM python:3.11-slim

WORKDIR /app

# Install system dependencies including libgomp for onnxruntime
RUN apt-get update && apt-get install -y \
    wget \
    curl \
    gcc \
    g++ \
    libgomp1 \
    && rm -rf /var/lib/apt/lists/* \
    && apt-get clean

# Download the u2netp model during build (smaller: 54MB)
RUN mkdir -p /root/.u2net \
    && echo "📥 Downloading u2netp model (54MB)..." \
    && wget -q --show-progress --progress=bar:force \
       https://github.com/danielgatis/rembg/releases/download/v0.0.0/u2netp.onnx \
       -O /root/.u2net/u2netp.onnx \
    && echo "✅ Model downloaded successfully!"

# Copy requirements first for better caching
COPY requirements.txt .
RUN pip install --no-cache-dir --upgrade pip \
    && pip install --no-cache-dir -r requirements.txt

# Copy application files
COPY . .

# Create necessary directories
RUN mkdir -p templates temp

# Verify the model and dependencies
RUN echo "🔍 Checking dependencies..." \
    && python -c "import onnxruntime; print('✅ onnxruntime:', onnxruntime.__version__)" \
    && python -c "import rembg; print('✅ rembg loaded')" \
    && echo "📊 Model size: $(du -h /root/.u2net/u2netp.onnx | cut -f1)"

# Run the bot
CMD ["python", "koyeb_bot.py"]
