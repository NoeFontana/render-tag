# Implementation Plan: Local Automation Release Script

## Phase 1: Script Scaffolding and Version Bumping
- [ ] Task: Create `scripts/release.sh` with `set -e` and make it executable.
- [ ] Task: Add argument parsing to accept the bump type (`patch`, `minor`, `major`).
- [ ] Task: Implement a check to ensure the working directory is clean before proceeding.
- [ ] Task: Integrate `uvx hatch version <bump_type>` to update `pyproject.toml` and capture the new version.
- [ ] Task: Conductor - User Manual Verification 'Phase 1: Script Scaffolding and Version Bumping' (Protocol in workflow.md)

## Phase 2: Git History and Changelog Generation
- [ ] Task: Implement logic to find the most recent Git tag (`git describe --tags --abbrev=0`).
- [ ] Task: Create logic to extract `git notes` between the last tag and HEAD.
- [ ] Task: Write an awk/sed or bash loop to parse the extracted notes and format them as Markdown bullet points (extracting "Summary:" if present).
- [ ] Task: Prepend the new version header and formatted notes to `CHANGELOG.md` (creating it if it doesn't exist).
- [ ] Task: Conductor - User Manual Verification 'Phase 2: Git History and Changelog Generation' (Protocol in workflow.md)

## Phase 3: Git Operations and Finalization
- [ ] Task: Add logic to `git add` both `pyproject.toml` and `CHANGELOG.md`.
- [ ] Task: Add logic to `git commit -m "chore(release): v<new_version>"`.
- [ ] Task: Add logic to `git tag -a v<new_version> -m "Release v<new_version>"`.
- [ ] Task: Conductor - User Manual Verification 'Phase 3: Git Operations and Finalization' (Protocol in workflow.md)
