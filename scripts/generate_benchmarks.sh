#!/bin/bash
set -e

# Generate locus_v1/std41h12
echo "Generating locus_v1/std41h12..."
uv run render-tag generate --config configs/benchmarks/single_tag/locus_v1_std41h12.yaml --output output/locus_v1/std41h12 --workers 2

# Generate locus_v1/tag16h5
echo "Generating locus_v1/tag16h5..."
uv run render-tag generate --config configs/benchmarks/single_tag/locus_v1_tag16h5.yaml --output output/locus_v1/tag16h5 --workers 2

# Generate locus_v1/tag36h11
echo "Generating locus_v1/tag36h11..."
uv run render-tag generate --config configs/benchmarks/single_tag/locus_v1_tag36h11.yaml --output output/locus_v1/tag36h11 --workers 2

echo "Benchmark generation complete!"
