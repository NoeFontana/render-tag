# v0.8.1 (2026-04-20)

- Add --workers to experiment run

# v0.8.0 (2026-04-20)

**Breaking change.** Completes the v0.2 subject migration started in v0.7.

Removed deprecated Pydantic fields that were dual-sourced with `scenario.subject`:

- `TagConfig.family` → `scenario.subject.tag_families`
- `TagConfig.size_meters` → `scenario.subject.size_mm`
- `DatasetConfig.intent` → `dataset.evaluation_scopes`
- `ScenarioConfig.tag_families` → `scenario.subject.tag_families`
- `ScenarioConfig.tags_per_scene` → `scenario.subject.tags_per_scene`

The wire format (schema version `0.2`) is unchanged. Legacy YAML/JSON still loads
through the Anti-Corruption Layer, but the in-memory schema no longer exposes
these fields. Imperative constructors (`TagConfig(family=...)`) now raise
`ValidationError`.

### Migrating

Run `render-tag config migrate path/to/config.yaml` to preview a diff, then
`--write` to rewrite in place. `load_config` no longer auto-rewrites files on
disk — in-memory migration still happens silently via the ACL.

Example:
```yaml
# Before
tag:
  family: tag36h11
  size_meters: 0.1
scenario:
  tag_families: [tag36h11]
  tags_per_scene: 3

# After
scenario:
  subject:
    type: TAGS
    tag_families: [tag36h11]
    size_mm: 100.0
    tags_per_scene: 3
```

# v0.7.0 (2026-03-29)

- Spacing and corners (#60)
- Refactor to image-centric schema with Sequences to avoid image duplication
- Add AprilGrid Golden baseline (v1)
- Add charuco_golden_v1 reference dataset (#58)
- Remove debug-logs
- Remove noisy render debug logs
- Fix board family validation and AprilGrid consistency
- Add board calibration support to FiftyOne visualization
- Formalize BoardDefinition and add RenderTagDataset reader
- Board_definition metadata and keypoint index stability
- Strict frustum culling for board sub-tags and saddle points
- Integer-aligned grid resolution and zero-interpolation compositing
- Chore/maintainability (#44)
- Enforce Top-Left CW keypoint contract across pipeline (#43)
- Reprojection sanity checks + ChArUco saddle Y fix
- Parametrize Kalibr corner ratio with sub-pixel symmetry (#42)
- Sub-pixel compositing and 5x higher default resolution (#41)
- Kill orphaned blender processes on shutdown (#40)
- Cleanup/misc (#39)
- Documentation Cleanup and Standardization (#38)
- Standardize on WXYZ (scalar-first) throughout p… (#37)

# v0.6.1 (2026-03-13)

- Fixup! chore(release): v0.6.0

# v0.6.0 (2026-03-13)

- Fixup! fix(lint): clean up stale XYZW comments and type-narrow corners guard
- Fixup! fix(lint): clean up stale XYZW comments and type-narrow corners guard
- Clean up stale XYZW comments and type-narrow corners guard
- Standardize on WXYZ (scalar-first) throughout pipeline
- Update bbox, viz, and docs to match center pose anchor
- Standardize pose origin to tag center (Center-Origin)
- Eliminate schema drift via dynamic model_dump serialization
- Derive black_border_size from keypoints_3d instead of legacy corner_coords
- SSOT and simplify - CW convention
- Fix zoomed-in tag issue and half-pixel projection shift: properly scale physical planes and counteract BlenderProc's automatic sensor shift (#32)
- Rectify 3D mesh boundary shift to OpenCV continuous coordinates (#31)
- Rectify sub-pixel intrinsic shift and align with OpenCV continuous coordinates (#30)

# v0.5.0 (2026-03-12)

- **BREAKING CHANGE**: Rectified sub-pixel intrinsic shift in camera model.
  - Aligned principal point calculation with strictly continuous OpenCV coordinates: `cx = width / 2.0`, `cy = height / 2.0`.
  - Removed legacy `(W-1)/2` and `(H-1)/2` centering logic to eliminate 0.5-pixel projection bias.
  - Updated all unit and integration tests to enforce the new standard.
  - Previous datasets are considered invalid and should be re-rendered to maintain consistency.

# v0.4.0 (2026-03-11)

- Align coordinate system and pose anchoring with OpenCV 4.6+ (#28)
- Fix/accuracy (#27)
- Fix/multi board (#26)
- Resolve false positive non-uniform scale error on calibration boards (#25)
- Benches/board (#24)
- Fix/math scaling annotation (#23)
- Fix/scramble 2 (#22)
- Robust/math 2 (#21)
- Add provenance.json to hub push/pull metadata (#20)
- Robust/math (#19)

# v0.3.0 (2026-03-08)

- Aligned FiftyOne Z-axis projection with OpenCV convention by pointing it towards the tag and removed a duplicate quaternion conversion.
- Clean up `test_geometry_invariants.py` by removing an unused `pytest` import and applying minor formatting adjustments.
- Add inverse-transpose normal transformation and rigid-body affine matrix sanitization with new unit tests.
- Qol/doc (#18)
- Enhance projection math robustness with invariant checks and orthogonalization, add new quaternion conversion utility, and introduce comprehensive unit tests. (#17)
- Add tag_size_mm to ground truth for PnP stability (#16)
- Qol/name and viz (#15)
- Config/resolution matrix (#14)
- Parallelize ci tasks for quick visual feedback (#13)
- Viz/validate annotations (#12)
- Fix/scramble (#11)
- Resolve double-scaling of ground truth keypoints using SVD
- Resolve issue where release.sh fails to extract changelog notes
- Explicitly use the latest unreachable tag as the changelog baseline and update the warning message.
- Prevent double-scaling of ground truth coordinates by stripping scale from Blender object matrices, add a test for board scale independence.

# v0.2.0 (2026-03-06)

- Resolve issue where release.sh fails to extract changelog notes
- Explicitly use the latest unreachable tag as the changelog baseline and update the warning message.
- Prevent double-scaling of ground truth coordinates by stripping scale from Blender object matrices, add a test for board scale independence.
- Skip build provenance attestation for private repositories

# v0.1.2 (2026-02-28)

- Fix double-scaling in tag projection using normalized local coordinates (+/- 1.0)
- Implement polymorphic fallback in get_corner_world_coords for unit tags and physical boards
- Implement project hygiene safeguard to prevent accidental root directory generation
- Cleanup misplaced shard files and images from project root
- Update .gitignore and .geminiignore to handle shard artifacts and dataset metadata
- Resolve line length linting errors in hygiene check (Ruff E501)
- Fix build provenance attestation for private repositories in CI/CD pipeline

# v0.1.1 (2026-02-28)

- Phase 2: CI/CD Pipeline Modernization (GitHub Actions)
  - Added OIDC permissions for GitHub Actions (attestations and id-token)
  - Integrated artifact build and publish jobs to release pipeline
  - Enabled semantic version tagging and latest tag for Docker images
- Phase 1: Local Automation (The Release Script)
  - Created scripts/release.sh for encapsulated versioning and tagging
  - Implemented hatch-based version bumping and automated changelog generation
- Static Quality Gates
  - Integrated Ruff (format/check), Ty (types), and Import Linter into CI
  - Automated architectural layer enforcement

# v0.1.0 (2026-02-11)

- Initial release of render-tag
- Procedural 3D data generation for fiducial markers
- Support for AprilTag and ArUco families
- Parallel rendering orchestration via ZMQ
- Unified rendering engine with BlenderProc integration
