FROM python:3.11-slim

# System dependencies for OpenCV headless
RUN apt-get update && apt-get install -y --no-install-recommends \
        libglib2.0-0 \
        libsm6 \
        libxext6 \
        libxrender1 \
        ffmpeg \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY pyproject.toml .
COPY config.py main.py ./
COPY domain/       domain/
COPY application/  application/
COPY infrastructure/ infrastructure/

# 1. PyTorch CUDA primero — así pip lo ve como satisfecho cuando lee pyproject.toml
#    RTX 50xx (Blackwell, sm_120) requiere nightly cu130
RUN pip install --no-cache-dir \
        --pre torch torchvision \
        --index-url https://download.pytorch.org/whl/nightly/cu130

# 2. Instalar todo desde pyproject.toml — torch ya está, opencv-python se instala aquí
RUN pip install --no-cache-dir -e .

# 3. Reemplazar opencv-python por headless (sin dependencias de display)
RUN pip install --no-cache-dir --force-reinstall opencv-python-headless

# Runtime data directory — overridden by named volume at container start
RUN mkdir -p data/clips

COPY entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh

ENTRYPOINT ["/entrypoint.sh"]
