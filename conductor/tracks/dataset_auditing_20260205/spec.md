# Specification: Dataset Auditing & Quality Gates

## Overview
This track introduces a dedicated `audit` stage to the `render-tag` pipeline. It transforms the project from a generation tool into a trusted data platform by providing verifiable "Contracts of Trust" for generated datasets. The auditor evaluates datasets against statistical requirements (KPIs) and enforces "Quality Gates" to ensure data integrity and model-readiness.

## Functional Requirements

### 1. Audit Engine (Analysis Layer)
- **Library**: Use **Polars** for high-performance, vectorized data processing.
- **Input Ingestion**:
    - Parse `tags.csv` (Ground truth detections).
    - Parse `metadata.json` (Per-scene parameters like lighting, HDRI, camera).
    - Parse `manifest.json` (Generation intent/config).
- **KPI Calculations**:
    - **Geometric**: Incidence angles (dot product of tag normal vs. camera vector), distance distribution, and frame coverage heatmap (grid-based).
    - **Environmental**: Pixel contrast (signal-to-noise estimation) and lighting intensity variance.
    - **Integrity**: Detection of orphaned tags (rendered but not in CSV), impossible poses (z < 0), and corrupted frames.

### 2. CLI Interface
- `render-tag audit <path>`: Runs a full audit on a dataset directory.
- `render-tag audit diff <path_v1> <path_v2>`: Detects statistical drift between two datasets.
- Rich console output with tables and status indicators.

### 3. Quality Gates
- Implementation of `quality_gate.yaml` to define acceptance criteria.
- **Hard Failure Logic**: Command exits with non-zero code if any "critical" metric fails to meet the gate threshold, suitable for CI/CD integration.

### 4. Output Artifacts
- `audit_report.json`: Machine-readable summary for automation.
- `audit_dashboard.html`: Interactive single-file visualization (Plotly or Altair) for human review.
- `outliers/`: A directory containing symlinks to images flagged as statistical outliers for rapid visual inspection.

## Non-Functional Requirements
- **Decoupling**: The audit stage must be entirely independent of Blender/BlenderProc to allow execution on standard CPU environments.
- **Performance**: Capable of auditing 100k+ tag detections in seconds using Polars.

## Acceptance Criteria
- [ ] Successful calculation of incidence angles and distance metrics verified against ground truth.
- [ ] `audit` command returns non-zero exit code when a critical gate (e.g., min images) is not met.
- [ ] HTML dashboard correctly renders heatmaps and histograms.
- [ ] `audit diff` correctly identifies a reduction in lighting variance between two test datasets.

## Out of Scope
- Automatic "fixing" of datasets (e.g., re-rendering missing poses).
- Real-time auditing during the generation loop.
