#!/usr/bin/env bash
set -e

# Default to patch bump if no argument is provided
BUMP=${1:-patch}

echo "Bumping version ($BUMP)..."
uvx hatch version $BUMP

# Get new version
NEW_VERSION=$(uvx hatch version)
NEW_TAG="v${NEW_VERSION}"
echo "New version is $NEW_VERSION"

# Identify baseline tag (latest reachable tag)
BASELINE_TAG=$(git describe --tags --abbrev=0 2>/dev/null || echo "")

if [ -z "$BASELINE_TAG" ]; then
    # Fallback: check if ANY tags exist, even if unreachable
    LATEST_ANY_TAG=$(git tag --sort=-v:refname | head -n 1)
    if [ -n "$LATEST_ANY_TAG" ]; then
        echo "Warning: Latest tag $LATEST_ANY_TAG is not reachable from current HEAD."
        echo "Changelog might contain duplicate entries."
    fi
fi

echo "Extracting git notes..."
if [ -z "$BASELINE_TAG" ]; then
    echo "No reachable baseline tag found. Collecting notes from all commits."
    COMMITS=$(git log --format="%H")
else
    echo "Baseline tag is $BASELINE_TAG. Collecting notes since then."
    COMMITS=$(git log ${BASELINE_TAG}..HEAD --format="%H")
fi

NOTES=""
for COMMIT in $COMMITS; do
    NOTE=$(git notes show $COMMIT 2>/dev/null || echo "")
    if [ -n "$NOTE" ]; then
        # Format the note, perhaps indent lines
        # First line is bulleted, subsequent lines are indented
        FORMATTED_NOTE=$(echo "$NOTE" | awk 'NR==1{print "- " $0} NR>1{print "  " $0}')
        NOTES="${NOTES}${FORMATTED_NOTE}

"
    fi
done

if [ -z "$NOTES" ]; then
    NOTES="- No notable changes.

"
fi

CHANGELOG="CHANGELOG.md"
TMP_CHANGELOG=$(mktemp)

# Write header and notes
echo "# $NEW_TAG ($(date +%Y-%m-%d))" > $TMP_CHANGELOG
echo "" >> $TMP_CHANGELOG
echo -e "$NOTES" >> $TMP_CHANGELOG

# Append existing changelog if it exists
if [ -f "$CHANGELOG" ]; then
    cat "$CHANGELOG" >> $TMP_CHANGELOG
fi

mv $TMP_CHANGELOG "$CHANGELOG"
echo "Updated $CHANGELOG"

echo "Staging files..."
git add pyproject.toml $CHANGELOG

echo "Creating release commit..."
git commit -m "chore(release): $NEW_TAG"

echo "Creating annotated tag..."
git tag -a "$NEW_TAG" -m "Release $NEW_TAG"

echo "Release $NEW_TAG created successfully!"
