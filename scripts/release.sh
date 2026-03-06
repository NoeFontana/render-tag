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
        echo "Using it as baseline anyway. Changelog might contain duplicate entries."
        BASELINE_TAG=$LATEST_ANY_TAG
    fi
fi

echo "Extracting commit messages for changelog..."
if [ -z "$BASELINE_TAG" ]; then
    echo "No reachable baseline tag found. Collecting commits from all history."
    COMMITS=$(git log --no-merges --format="%H")
else
    echo "Baseline tag is $BASELINE_TAG. Collecting commits since then."
    COMMITS=$(git log ${BASELINE_TAG}..HEAD --no-merges --format="%H")
fi

NOTES=""
for COMMIT in $COMMITS; do
    # Extract commit subject instead of relying on git notes
    NOTE=$(git log -1 --format="%s" $COMMIT 2>/dev/null || echo "")
    
    # Filter out chore and docs commits from the changelog
    if [[ "$NOTE" == chore* ]] || [[ "$NOTE" == docs* ]]; then
        continue
    fi
    
    if [ -n "$NOTE" ]; then
        # Capitalize first letter of subject if it starts with a conventional commit type
        FORMATTED_NOTE=$(echo "$NOTE" | sed 's/^[a-z]*\(([^)]*)\)*: //i' | awk '{print toupper(substr($0,1,1)) substr($0,2)}')
        NOTES="${NOTES}- ${FORMATTED_NOTE}
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
