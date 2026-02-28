# Implementation Plan: Tag-Driven Automated Release Pipeline

## Phase 1: Local Automation (The Release Script) [checkpoint: 9e71760]
- [x] Task: Create `scripts/release.sh` to encapsulate versioning and tagging logic. d023ea3
- [x] Task: In the script, bump the semantic version using `uvx hatch version <bump_rule>` and capture the new version. d023ea3
- [x] Task: In the script, query Git for the most recent semantic version tag to use as the baseline. d023ea3
- [x] Task: In the script, extract `git notes` from baseline to HEAD and format them as Markdown bullet points. d023ea3
- [x] Task: In the script, prepend the formatted notes to `CHANGELOG.md` under a new version header. d023ea3
- [x] Task: In the script, stage `pyproject.toml` and `CHANGELOG.md`, create a `chore(release)` commit, and create an annotated Git tag. d023ea3
- [x] Task: Conductor - User Manual Verification 'Phase 1: Local Automation (The Release Script)' (Protocol in workflow.md) 9e71760

## Phase 2: CI/CD Pipeline Modernization (GitHub Actions) [checkpoint: e1aa97f]
- [x] Task: Modify `.github/workflows/release.yml`'s event trigger to listen exclusively for pushed Git tags (e.g., `v*`). 7895daa
- [x] Task: Add a `build-python` job to the workflow to set up the `uv` environment and execute Python build (`uv build`) to compile `.whl` and `.tar.gz` artifacts. a70496e
- [x] Task: Modify the Docker build job to extract the version string from the tag and apply both semantic and `latest` tags before pushing to GHCR. 11e3b78
- [x] Task: Add a `publish-release` job dependent on artifact builds. Extract git notes for the pushed tag, create a formal GitHub Release, and attach the compiled Python assets. 11e3b78
- [x] Task: Conductor - User Manual Verification 'Phase 2: CI/CD Pipeline Modernization' (Protocol in workflow.md) e1aa97f
