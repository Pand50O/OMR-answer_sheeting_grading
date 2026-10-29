#!/usr/bin/env bash
set -euo pipefail

PROJECT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
REMOTE_URL="${1:-}"
COMMIT_MESSAGE="${2:-Update project}"

cd "$PROJECT_DIR"

# Create a repository here if needed, even if a parent folder has another repo.
if [[ ! -e "$PROJECT_DIR/.git" ]]; then
  git init -b main "$PROJECT_DIR"
fi

REPO_ROOT="$(git rev-parse --show-toplevel)"
if [[ "$REPO_ROOT" != "$PROJECT_DIR" ]]; then
  echo "Error: Git root is $REPO_ROOT, not this project folder." >&2
  exit 1
fi

if ! git remote get-url origin >/dev/null 2>&1; then
  if [[ -z "$REMOTE_URL" ]]; then
    read -r -p "GitHub repository URL (HTTPS or SSH): " REMOTE_URL
  fi
  if [[ -z "$REMOTE_URL" ]]; then
    echo "Error: a GitHub repository URL is required." >&2
    exit 1
  fi
  git remote add origin "$REMOTE_URL"
elif [[ -n "$REMOTE_URL" ]] && [[ "$(git remote get-url origin)" != "$REMOTE_URL" ]]; then
  echo "Error: origin already points to $(git remote get-url origin)." >&2
  echo "Remove or update origin manually if you intend to use another repository." >&2
  exit 1
fi

BRANCH="$(git branch --show-current)"
if [[ -z "$BRANCH" ]]; then
  BRANCH=main
  git checkout -b "$BRANCH"
fi

# Keep student records, generated results, and local artifacts out. Images are
# added separately below, with a maximum of 10 from each image folder.
# Rebuild the index so an earlier `git add .` cannot leave extra files staged.
git reset -- .

git add -A -- . \
  ':(exclude)answersheet-scan/**' \
  ':(exclude)answersheet_scan/**' \
  ':(exclude)debug-images/**' \
  ':(exclude)student_file/**' \
  ':(exclude)omr-result/**' \
  ':(exclude)graded-results/**' \
  ':(exclude)__pycache__/**' \
  ':(exclude).DS_Store' \
  ':(exclude)fail.py'

# Keep the blank CSV template while excluding other student files.
if [[ -f student_file/template.csv ]]; then
  git add -- student_file/template.csv
fi

for IMAGE_DIR in debug-images answersheet-scan answersheet_scan; do
  [[ -d "$IMAGE_DIR" ]] || continue
  while IFS= read -r IMAGE_FILE; do
    git add -- "$IMAGE_FILE"
  done < <(
    find "$IMAGE_DIR" -type f \( \
      -iname '*.jpg' -o -iname '*.jpeg' -o -iname '*.png' -o \
      -iname '*.webp' -o -iname '*.tif' -o -iname '*.tiff' \
    \) -print | LC_ALL=C sort | head -n 10
  )
done

echo
echo "Files staged for $BRANCH on $(git remote get-url origin):"
git status --short
echo
read -r -p "Commit and push these files? [y/N] " CONFIRM
if [[ ! "$CONFIRM" =~ ^[Yy]$ ]]; then
  echo "Cancelled. Staged changes are still available in Git."
  exit 0
fi

if ! git diff --cached --quiet; then
  git commit -m "$COMMIT_MESSAGE"
fi

git push -u origin "$BRANCH"
