#!/bin/bash
set -e
set -o pipefail

# Default Configuration
BENCHMARK_DIR="configs/benchmarks"
OUTPUT_BASE="output/benchmarks"
WORKERS=2
DRY_RUN=false
EXTRA_ARGS=()

# Resolution Matrix
RESOLUTIONS=(
    "640x480"
    "1280x720"
    "1920x1080"
    "3840x2160"
)

# Argument Parsing
if [[ $# -gt 0 ]] && [[ ! "$1" =~ ^- ]]; then
    BENCHMARK_DIR="$1"
    shift
fi

while [[ "$#" -gt 0 ]]; do
    case $1 in
        --dry-run) DRY_RUN=true; shift ;;
        -w|--workers) WORKERS="$2"; shift 2 ;;
        -h|--help)
            echo "Usage: $0 [BENCHMARK_DIR] [--dry-run] [--workers N] [EXTRA_ARGS]"
            exit 0
            ;;
        *) EXTRA_ARGS+=("$1"); shift ;;
    esac
done

if [[ "$DRY_RUN" == "true" ]]; then
    echo "--- DRY RUN MODE ---"
fi

echo "Synchronizing binary assets from Hub..."
uv run render-tag hub pull-assets

echo "Discovering benchmarks in ${BENCHMARK_DIR}..."

# Recursive Dynamic Discovery Loop
find "${BENCHMARK_DIR}" -name "*.yaml" -print0 | while IFS= read -r -d '' config_path; do
    # Derive identifier from path relative to BENCHMARK_DIR
    rel_path=$(realpath --relative-to="${BENCHMARK_DIR}" "$config_path")
    identifier="${rel_path%.*}"
    identifier="${identifier//\//_}" # Replace slashes with underscores for folder naming
    
    echo "================================================================"
    echo "Benchmark Root: ${identifier}"
    echo "Config:         ${config_path}"
    echo "================================================================"
    
    # Iterate over standard resolution matrix
    for res in "${RESOLUTIONS[@]}"; do
        # Extract width and height
        IFS='x' read -r width height <<< "$res"
        
        # Taxonomy: output/benchmarks/<benchmark_identifier>/<resolution>/
        output_dir="${OUTPUT_BASE}/${identifier}/${res}"
        
        echo "----------------------------------------------------------------"
        echo "Resolution: ${res}"
        echo "Output:     ${output_dir}"
        echo "----------------------------------------------------------------"
        
        if [ "$DRY_RUN" = true ]; then
            echo "[DRY-RUN] uv run render-tag generate --config ${config_path} --output ${output_dir} --workers ${WORKERS} --override camera.resolution=[${width},${height}] ${EXTRA_ARGS[*]}"
        else
            uv run render-tag generate --config "${config_path}" --output "${output_dir}" --workers "${WORKERS}" --override "camera.resolution=[${width},${height}]" "${EXTRA_ARGS[@]}"
        fi
    done
done

echo ""
echo "Benchmark generation process complete!"
