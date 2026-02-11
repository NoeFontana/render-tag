# Benchmarking

`render-tag` includes utilities to track the performance of the generation pipeline.

## Usage

The `Benchmarker` utility is used internally to measure the duration of different pipeline stages.

```python
from render_tag.common.benchmarking import Benchmarker

bench = Benchmarker("My Generation Run")
with bench.measure("Scene Generation"):
    # ... logic ...
    pass

bench.report.log_summary()
```

## Performance Report

The summary includes time spent in:
- Scene recipe generation
- Blender startup/cleanup
- Rendering (per frame)
- Sidecar metadata calculation
- Disk I/O (writing images and CSVs)

## Optimizations

`render-tag` implements several performance optimizations:
- **Lazy HDRI Loading**: Backgrounds are only reloaded if the path changes.
- **Mesh Pooling**: Blender mesh objects are reused across scenes to avoid overhead.
- **Parallel Sharding**: Datasets can be split into independent shards and rendered in parallel.
