#!/usr/bin/env bash
set -uo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="${REPO_ROOT:-$(dirname "$SCRIPT_DIR")}"
SKILL_SOURCE="$REPO_ROOT/skill"

CLAUDE_SKILLS_ROOT="${CLAUDE_SKILLS_ROOT:-$HOME/.claude/skills}"
AGENTS_SKILLS_ROOT="${AGENTS_SKILLS_ROOT:-$HOME/.agents/skills}"

install_to() {
  local label="$1" dest="$2"

  if ! mkdir -p "$dest"; then
    echo "RESULT $label copy FAILED mkdir $dest"
    return 1
  fi
  if cp -r "$SKILL_SOURCE"/. "$dest"/; then
    echo "RESULT $label copy OK"
    return 0
  fi
  echo "RESULT $label copy FAILED cp"
  return 1
}

verify_frontmatter() {
  local label="$1" dest="$2" skill_md="$2/SKILL.md"

  if [ ! -f "$skill_md" ]; then
    echo "RESULT $label verify:frontmatter FAILED missing SKILL.md"
    return 1
  fi
  if grep -q '^name:' "$skill_md" && grep -q '^description:' "$skill_md"; then
    echo "RESULT $label verify:frontmatter OK"
    return 0
  fi
  echo "RESULT $label verify:frontmatter FAILED missing name/description"
  return 1
}

verify_cli() {
  local label="$1" dest="$2"

  if ! command -v python >/dev/null 2>&1; then
    echo "RESULT $label verify:cli FAILED python not on PATH"
    return 1
  fi
  if python "$dest/scripts/video.py" probe --help >/dev/null 2>&1; then
    echo "RESULT $label verify:cli OK"
    return 0
  fi
  echo "RESULT $label verify:cli FAILED non-zero exit"
  return 1
}

any_ok=0

for pair in "claude $CLAUDE_SKILLS_ROOT" "agents $AGENTS_SKILLS_ROOT"; do
  label="${pair%% *}"
  root="${pair#* }"
  dest="$root/read-video"
  if install_to "$label" "$dest"; then
    any_ok=1
    verify_frontmatter "$label" "$dest" || true
    verify_cli "$label" "$dest" || true
  fi
done

if [ "$any_ok" -eq 0 ]; then
  echo "SUMMARY all targets FAILED"
  exit 1
fi
echo "SUMMARY install complete"
exit 0
