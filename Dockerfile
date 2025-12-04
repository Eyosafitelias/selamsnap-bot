# Dockerfile with CPU-only onnxruntime
FROM python:3.11-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    wget \
    curl \
    && rm -rf /var/lib/apt/lists/* \
    && apt-get clean

# Download model
RUN mkdir -p /root/.u2net \
    && wget -q https://github.com/danielgatis/rembg/releases/download/v0.0.0/u2netp.onnx \
       -O /root/.u2net/u2netp.onnx \
    && echo "✅ Model downloaded"

# Copy requirements
COPY requirements.txt .
RUN pip install --no-cache-dir --upgrade pip

# Install CPU-only onnxruntime first (smaller)
RUN pip install --no-cache-dir onnxruntime==1.16.3

# Then install other packages
RUN pip install --no-cache-dir -r requirements.txt

# Copy app
COPY . .
RUN mkdir -p templates temp

# Verify
RUN python -c "import onnxruntime; print('onnxruntime:', onnxruntime.__version__)"

CMD ["python", "koyeb_bot.py"]
