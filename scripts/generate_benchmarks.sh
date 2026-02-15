#!/bin/bash
set -e

# Configuration
BENCHMARK_DIR="configs/benchmarks/single_tag"
OUTPUT_BASE="output/benchmarks"
WORKERS=2

# Help/Dry-run support
DRY_RUN=false
if [[ "$1" == "--dry-run" ]]; then
    DRY_RUN=true
    echo "--- DRY RUN MODE ---"
fi

echo "Discovering benchmarks in ${BENCHMARK_DIR}..."

# Dynamic Discovery Loop
for config_path in "${BENCHMARK_DIR}"/*.yaml; do
    [ -e "$config_path" ] || continue
    
    # Derive identifier from filename (e.g., locus_v1_std41h12)
    filename=$(basename -- "$config_path")
    identifier="${filename%.*}"
    output_dir="${OUTPUT_BASE}/${identifier}"
    
    echo "----------------------------------------------------------------"
    echo "Benchmark: ${identifier}"
    echo "Config:    ${config_path}"
    echo "Output:    ${output_dir}"
    echo "----------------------------------------------------------------"
    
    if [ "$DRY_RUN" = true ]; then
        echo "[DRY-RUN] uv run render-tag generate --config ${config_path} --output ${output_dir} --workers ${WORKERS}"
    else
        uv run render-tag generate --config "${config_path}" --output "${output_dir}" --workers ${WORKERS}
    fi
done

echo ""
echo "Benchmark generation process complete!"
