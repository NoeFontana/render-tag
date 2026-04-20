#!/bin/bash
# DEPRECATED — replaced by the benchmarks × resolution Campaign YAML.
#
# The bash-driven glob over `configs/benchmarks/` was implicit-discovery and
# produced variants that weren't preset-stamped, weren't named by job_id,
# and weren't exercised by `test_experiment_config_validity`. The Campaign
# path fixes all three.
#
# Use instead:
#
#     uv run render-tag experiment run \
#         --config configs/benchmarks/_campaign_v1.yaml \
#         --output output/benchmarks

echo "generate_benchmarks.sh is deprecated." >&2
echo "" >&2
echo "Use:" >&2
echo "    uv run render-tag experiment run \\" >&2
echo "        --config configs/benchmarks/_campaign_v1.yaml \\" >&2
echo "        --output output/benchmarks" >&2
echo "" >&2
echo "New benchmark YAMLs are added to configs/benchmarks/_campaign_v1.yaml" >&2
echo "explicitly (no more glob-based auto-enrollment)." >&2
exit 2
