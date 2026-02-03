# 1. Base Image: Python 3.12 Slim (Debian-based)
# Matches pyproject.toml requirement and keeps image size reasonable
FROM python:3.12-slim

# 2. System Setup
ENV PYTHONUNBUFFERED=1 \
    DEBIAN_FRONTEND=noninteractive

# Install system dependencies required by Blender and BlenderProc
RUN apt-get update && apt-get install -y --no-install-recommends \
    git \
    libgl1 \
    libxrender1 \
    libxi6 \
    libxkbcommon0 \
    libsm6 \
    libxext6 \
    libglib2.0-0 \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# 3. Dependency Caching
COPY pyproject.toml README.md ./

# Install python dependencies including blenderproc
RUN pip install --no-cache-dir .

# 4. Bake Blender into the image
# We run a simple blenderproc command to force it to download the Blender binary
# This prevents downloading it effectively every time the user runs the container
RUN blenderproc debug --list_blender_installations || true

# 5. Source Code Layer
COPY src/ ./src/
COPY assets/ ./assets/
COPY configs/ ./configs/

# Re-install to link source
RUN pip install --no-cache-dir .

# 6. Runtime Configuration
# We verify blenderproc is working
RUN blenderproc --version

ENTRYPOINT ["render-tag"]
CMD ["--help"]
