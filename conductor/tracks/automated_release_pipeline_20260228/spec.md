# Specification: Tag-Driven Automated Release Pipeline

## Overview
Shift the artifact generation process from manual to a tag-driven automated pipeline using GitHub Actions. By modifying the existing `.github/workflows/docker_build.yml` (or creating a new release workflow), the system will automatically compile the Python host logic into distributable assets, build and tag Docker images, and publish formal GitHub Releases triggered by semantic version tags.

## Functional Requirements
- **Event Trigger:**
  - The workflow must trigger exclusively on pushed Git tags matching the semantic versioning pattern (e.g., `v*`).
- **Python Asset Compilation (Host Build):**
  - Establish a discrete job utilizing `astral-sh/setup-uv` to execute the Python build process (`uv build`).
  - Compile the host CLI and orchestration logic into both a distributable Wheel (`.whl`) and a Source Tarball (`.tar.gz`).
- **Docker Multi-Tagging & Push:**
  - Extract the specific version string from the triggering Git tag.
  - Build the Docker image, incorporating the compiled Python assets if necessary.
  - Configure the Docker push step to apply both the specific semantic version tag (e.g., `v1.2.3`) and the mutable `latest` tag.
  - Push the resulting multi-tagged image to the GitHub Container Registry (GHCR).
- **GitHub Release Publication:**
  - Establish a final job dependent on the successful completion of the asset compilation and Docker build jobs.
  - Extract the git notes associated exclusively with the pushed tag.
  - Automatically create a formal GitHub Release.
  - Use the extracted git notes as the body (changelog) of the release. If git notes are unavailable, use GitHub's auto-generated release notes as a fallback.
  - Attach the compiled Python Wheel and Source Tarball to the GitHub release page.

## Non-Functional Requirements
- **Automation & Immutability:** The pipeline must run entirely without human intervention once the tag is pushed, ensuring artifacts are immutably tied to the specific git state.
- **Dependency:** The release publication job must strictly depend on the successful artifact compilation to prevent empty or broken releases.

## Acceptance Criteria
- [ ] Pushing a `v*` tag successfully triggers the release workflow.
- [ ] The workflow successfully builds a `.whl` and `.tar.gz` via `uv build`.
- [ ] A Docker image is built and pushed to GHCR with both the semantic tag and the `latest` tag.
- [ ] A GitHub Release is created containing the changelog from git notes (or fallback) and the attached Python assets.

## Out of Scope
- Modifications to the core rendering logic or subject strategies.
- Publishing to PyPI (this track focuses on GitHub Releases and GHCR).