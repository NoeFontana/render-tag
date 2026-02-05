# Implementation Plan: Dataset Auditing & Quality Gates

This plan implements a high-performance auditing system to verify the quality and integrity of generated datasets, providing a "Contract of Trust" for downstream users.

## Phase 1: Foundation & Data Ingestion [checkpoint: 28d0fc1]
**Goal:** Establish the core data structures and high-speed ingestion layer using Polars.

- [x] Task: Define Audit Data Models and Polars Ingestion f57e14a
    - [x] Write unit tests for parsing `tags.csv` and `metadata.json` into Polars DataFrames.
    - [x] Implement `DatasetReader` in `src/render_tag/data_io/auditor.py` with schema validation.
- [x] Task: CLI Skeleton for Audit Command 14c884c
    - [x] Write integration tests for `render-tag audit` argument parsing and path validation.
    - [x] Implement basic `audit` command in `src/render_tag/cli.py` that lists dataset statistics (count).
- [x] Task: Conductor - User Manual Verification 'Foundation & Data Ingestion' (Protocol in workflow.md) 28d0fc1

## Phase 2: Core KPI Engine
**Goal:** Implement the vectorized math for geometric and environmental metrics.

- [ ] Task: Geometric Metric Calculations
    - [ ] Write unit tests for incidence angle (vector dot product) and distance calculations.
    - [ ] Implement `GeometryAuditor` to calculate angles, distances, and 2D frame coverage.
- [ ] Task: Environmental & Integrity Metrics
    - [ ] Write unit tests for lighting variance and impossible pose detection (z < 0).
    - [ ] Implement `IntegrityAuditor` to flag corrupted frames and orphaned tags.
- [ ] Task: Conductor - User Manual Verification 'Core KPI Engine' (Protocol in workflow.md)

## Phase 3: Quality Gates & Outlier Identification
**Goal:** Implement the enforcement layer for CI/CD and the visual outlier system.

- [ ] Task: Quality Gate Logic
    - [ ] Write unit tests for `quality_gate.yaml` parsing and threshold evaluation.
    - [ ] Implement `GateEnforcer` that maps audit results to exit codes based on critical/warning rules.
- [ ] Task: Outlier Management System
    - [ ] Write unit tests for identifying statistical outliers (e.g., tags < 5px from border).
    - [ ] Implement `OutlierExporter` to generate the `outliers/` directory with symlinks.
- [ ] Task: Conductor - User Manual Verification 'Quality Gates & Outlier Identification' (Protocol in workflow.md)

## Phase 4: Reporting & Visualization
**Goal:** Generate machine-readable JSON and human-readable HTML dashboards.

- [ ] Task: JSON and Console Reporting
    - [ ] Write tests for `audit_report.json` schema consistency.
    - [ ] Implement Rich-based console tables and JSON serialization of audit results.
- [ ] Task: Interactive HTML Dashboard
    - [ ] Write unit tests for HTML template rendering with Plotly/Altair data structures.
    - [ ] Implement `DashboardGenerator` using a standalone HTML template for offline viewing.
- [ ] Task: Conductor - User Manual Verification 'Reporting & Visualization' (Protocol in workflow.md)

## Phase 5: Comparative Analysis (Drift Detection)
**Goal:** Enable comparing two datasets to detect statistical regressions.

- [ ] Task: Audit Diff Command
    - [ ] Write integration tests for `render-tag audit diff` comparing two known datasets.
    - [ ] Implement `AuditDiff` logic to calculate deltas in variance and coverage.
- [ ] Task: Conductor - User Manual Verification 'Comparative Analysis (Drift Detection)' (Protocol in workflow.md)
