# Implementation Plan: Tag-Driven Automated Release Pipeline

## Phase 1: Local Automation (The Release Script) [checkpoint: 9e71760]
- [x] Task: Create `scripts/release.sh` to encapsulate versioning and tagging logic. d023ea3
- [x] Task: In the script, bump the semantic version using `uvx hatch version <bump_rule>` and capture the new version. d023ea3
- [x] Task: In the script, query Git for the most recent semantic version tag to use as the baseline. d023ea3
- [x] Task: In the script, extract `git notes` from baseline to HEAD and format them as Markdown bullet points. d023ea3
- [x] Task: In the script, prepend the formatted notes to `CHANGELOG.md` under a new version header. d023ea3
- [x] Task: In the script, stage `pyproject.toml` and `CHANGELOG.md`, create a `chore(release)` commit, and create an annotated Git tag. d023ea3
- [x] Task: Conductor - User Manual Verification 'Phase 1: Local Automation (The Release Script)' (Protocol in workflow.md) 9e71760

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
