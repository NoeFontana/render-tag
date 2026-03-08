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
