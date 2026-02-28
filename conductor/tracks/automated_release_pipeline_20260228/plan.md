# Implementation Plan: Tag-Driven Automated Release Pipeline

## Phase 1: Workflow Triggers and Python Build
- [ ] Task: Modify `.github/workflows/docker_build.yml` (or rename to `release.yml`) to trigger exclusively on `push: tags: - 'v*'`.
- [ ] Task: Add a `build-python` job using `ubuntu-latest`.
- [ ] Task: In `build-python`, configure `astral-sh/setup-uv` and execute `uv build` to generate the `.whl` and `.tar.gz` artifacts.
- [ ] Task: Upload the generated artifacts using `actions/upload-artifact@v4` for subsequent jobs.
- [ ] Task: Conductor - User Manual Verification 'Phase 1: Workflow Triggers and Python Build' (Protocol in workflow.md)

## Phase 2: Docker Build and Multi-Tagging
- [ ] Task: Modify the existing Docker build job to depend on the `build-python` job if the Dockerfile requires the host artifacts (or set up parallel execution if independent).
- [ ] Task: Configure `docker/metadata-action` to automatically extract the version tag and generate both semantic (e.g., `1.2.3`) and `latest` tags.
- [ ] Task: Update the `docker/build-push-action` to push the image to `ghcr.io` using the extracted tags.
- [ ] Task: Conductor - User Manual Verification 'Phase 2: Docker Build and Multi-Tagging' (Protocol in workflow.md)

## Phase 3: GitHub Release Publication
- [ ] Task: Add a `publish-release` job that depends on both `build-python` and the Docker build job.
- [ ] Task: In `publish-release`, use `actions/download-artifact@v4` to retrieve the built Python wheel and source tarball.
- [ ] Task: Add a bash step to extract the git notes for the current tag `git notes show HEAD` (with a fallback mechanism).
- [ ] Task: Use `softprops/action-gh-release@v2` (or GitHub CLI `gh release create`) to publish the release, passing the extracted notes as the body and attaching the downloaded artifacts.
- [ ] Task: Conductor - User Manual Verification 'Phase 3: GitHub Release Publication' (Protocol in workflow.md)
