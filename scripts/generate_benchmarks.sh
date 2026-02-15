#!/bin/bash
set -e

# Generate locus_v1/std41h12
echo "Generating locus_v1/std41h12..."
uv run render-tag generate --config configs/benchmarks/locus_v1_std41h12.yaml --output output/locus_v1/std41h12 --workers 2

# Generate locus_v1/tag16h5
echo "Generating locus_v1/tag16h5..."
uv run render-tag generate --config configs/benchmarks/locus_v1_tag16h5.yaml --output output/locus_v1/tag16h5 --workers 2

echo "Benchmark generation complete!"
