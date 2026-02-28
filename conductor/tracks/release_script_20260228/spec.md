# Specification: Local Automation Release Script

## Overview
Implement a local automation release script (`scripts/release.sh`) to streamline the versioning and tagging logic into a single executable pipeline. This script will automate version bumping, changelog generation from git notes, and git tagging, ensuring a "hassle-free" release process that minimizes human error.

## Functional Requirements
- **Version Resolution:**
  - The script must accept an argument for the bump type (e.g., `patch`, `minor`, `major`).
  - It will use `uvx hatch version <bump_type>` to automatically update the semantic version in `pyproject.toml`.
- **Boundary Detection:**
  - The script must query Git to identify the most recent semantic version tag to establish the baseline for the changelog.
- **Note Extraction & Formatting:**
  - Extract all git notes attached to commits between the baseline tag and the current HEAD.
  - Format these notes into structured Markdown bullet points. Following modern best practices, it should parse the structured notes created by Conductor (e.g., extracting the "Summary" or "Task" fields) to create a clean, readable changelog entry.
- **Changelog Assembly:**
  - Prepend the newly formatted notes to the top of `CHANGELOG.md` under a new version header corresponding to the bumped version.
- **Git Operations:**
  - Stage both `pyproject.toml` and `CHANGELOG.md`.
  - Automatically generate a Conductor-compliant commit message: `chore(release): <new_version>`.
  - Create an annotated Git tag matching the new version.

## Non-Functional Requirements
- **Language:** Bash/Shell.
- **Reliability:** The script should fail fast if any step encounters an error (e.g., uncommitted changes before starting, `hatch` failure).

## Acceptance Criteria
- [ ] `scripts/release.sh` is created and executable.
- [ ] Running the script successfully bumps the version in `pyproject.toml`.
- [ ] `CHANGELOG.md` is updated with correctly formatted notes from the current release cycle.
- [ ] A new commit and annotated tag are created with the correct version.

## Out of Scope
- Remote CI/CD deployment or publishing (this track focuses solely on local automation).