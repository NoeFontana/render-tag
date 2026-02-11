#!/bin/bash
set -e

# Image name
IMAGE_NAME="render-tag"

# Check if image exists, build if not
if [[ "$(docker images -q $IMAGE_NAME 2> /dev/null)" == "" ]]; then
    echo "[*] Building Docker image '$IMAGE_NAME'..."
    docker build -t $IMAGE_NAME .
fi

# Detect GPU capability
GPU_FLAG=""
if command -v nvidia-smi &> /dev/null; then
    GPU_FLAG="--gpus all"
fi

# Run the container
# -u $(id -u):$(id -g): Run as the current user so output files are not owned by root
# -v $(pwd):/workspace: Mount current dir to access output
# -w /workspace: Set working dir to the mount
echo "[*] Running $IMAGE_NAME..."
docker run --rm -it \
    $GPU_FLAG \
    -u "$(id -u):$(id -g)" \
    -v "$(pwd)/output:/app/output" \
    $IMAGE_NAME "$@"
