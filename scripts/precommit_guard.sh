#!/bin/bash
# Pre-commit guard to prevent accidental edits to legacy dashboard files
#
# This script blocks commits that modify dashboard.html or dashboard.js
# unless the commit message contains [legacy-ok]

LEGACY_FILES=("dashboard.html" "dashboard.js")
COMMIT_MSG_FILE="$1"

# Check if any legacy files are staged
STAGED_LEGACY_FILES=()
for file in "${LEGACY_FILES[@]}"; do
    if git diff --cached --name-only | grep -q "^${file}$"; then
        STAGED_LEGACY_FILES+=("$file")
    fi
done

# If no legacy files changed, allow commit
if [ ${#STAGED_LEGACY_FILES[@]} -eq 0 ]; then
    exit 0
fi

# Check if commit message contains [legacy-ok]
if grep -q "\[legacy-ok\]" "$COMMIT_MSG_FILE" 2>/dev/null; then
    echo "⚠️  Legacy files modified with [legacy-ok] flag - allowing commit"
    exit 0
fi

# Block the commit
echo ""
echo "❌ ERROR: Attempted to commit changes to legacy dashboard files!"
echo ""
echo "Modified files:"
for file in "${STAGED_LEGACY_FILES[@]}"; do
    echo "  - $file"
done
echo ""
echo "⚠️  These files are LEGACY and should NOT receive product UI changes."
echo ""
echo "✅ Real dashboard UI is in: dashboard/"
echo ""
echo "To fix:"
echo "  1. Revert the changes:"
echo "     git checkout -- dashboard.html dashboard.js"
echo ""
echo "  2. Edit the correct files in dashboard/"
echo ""
echo "If this is a legitimate legacy fix, add [legacy-ok] to your commit message:"
echo "  git commit -m 'fix: legacy compatibility [legacy-ok]'"
echo ""
exit 1

